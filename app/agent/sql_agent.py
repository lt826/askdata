"""SQL 修复循环（项目灵魂）：生成 → 执行 → 失败则错误回喂 → 重生成 → ... → 熔断。

对应六层架构第④层。与 FitPilot 的 FC 工具循环同构，但反馈对象从"工具结果"换成
"执行错误 + 上一版 SQL"——本质是 ReAct 在代码生成上的应用：
模型看到自己的错误信息，修正再试，而不是人类贴身改 prompt。

错误分类（供观测与展示；宽分类，不追求精确）：
- 拒绝    guard 拦截（写操作/多语句）——通常不该重试同类
- 语法    Parser Error
- 列名/表 Binder/Catalog Error（歧义、不存在）——修复成功率最高的一类
- 超时    性能问题，提示加过滤
熔断：超过 max_fix_rounds 轮仍失败 → 如实报告，不编造结果。
"""

import re
from dataclasses import dataclass, field
from datetime import date

from app.agent.sql_gen import SYSTEM_TEMPLATE, extract_sql
from app.core.config import get_settings
from app.core.llm import chat
from app.db.executor import run_sql
from app.db.schema_doc import get_schema_doc

FIX_HINT = """常见修法：
- 列名歧义(Ambiguous reference)→ 给列加上表别名前缀，如 u.user_id
- 列/表不存在(Binder/Catalog)→ 对照 schema 卡片核对真实列名，禁止编造列
- 语法(Parser)→ 检查 DuckDB 方言语法
- 超时→ 给大表加 WHERE 日期/状态过滤"""


def classify_error(error: str) -> str:
    if error.startswith("[SQL被拒绝]"):
        return "拒绝"
    if "Parser" in error:
        return "语法"
    if "Binder" in error or "Catalog" in error:
        return "列名/表"
    if "超时" in error:
        return "超时"
    return "其他"


@dataclass
class RoundTrace:
    round_no: int
    sql: str
    ok: bool
    error: str = ""
    error_class: str = ""
    elapsed_ms: int = 0


@dataclass
class AgentResult:
    question: str
    success: bool
    rounds: list[RoundTrace] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    rows: list[tuple] = field(default_factory=list)
    final_error: str = ""

    @property
    def fix_rounds_used(self) -> int:
        return max(0, len(self.rounds) - 1)  # 首轮是生成不是修复


def run_agent(question: str, on_event=None) -> AgentResult:
    """on_event(evt: dict) 供 SSE/CLI 实时展示每轮执行过程。"""
    s = get_settings()
    messages = [
        {"role": "system",
         "content": SYSTEM_TEMPLATE.format(today=date.today().isoformat(),
                                           schema=get_schema_doc())},
        {"role": "user", "content": f"问：{question}"},
    ]
    result = AgentResult(question=question, success=False)
    last_sql, last_error = "", ""

    for round_no in range(1, s.max_fix_rounds + 2):  # 1 轮生成 + max 轮修复
        if round_no == 1:
            sql = extract_sql(chat(messages, temperature=0))
        else:
            messages.append({"role": "assistant", "content": f"```sql\n{last_sql}\n```"})
            messages.append({"role": "user", "content": (
                f"你生成的 SQL 执行失败：\n{last_error}\n\n{FIX_HINT}\n"
                f"请修正后重新输出 SQL（只输出 ```sql 代码块）。")})
            sql = extract_sql(chat(messages, temperature=0))

        r = run_sql(sql)
        trace = RoundTrace(round_no, sql, r.ok, r.error,
                           classify_error(r.error) if not r.ok else "", r.elapsed_ms)
        result.rounds.append(trace)
        if on_event:
            on_event({"type": "round", **vars(trace)})

        if r.ok:
            result.success = True
            result.columns, result.rows = r.columns, r.rows
            return result
        last_sql, last_error = sql, r.error

    result.final_error = last_error
    return result
