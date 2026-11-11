"""SQL 修复循环（项目灵魂）——LangGraph StateGraph 编排版。

图结构：
  generate ──> execute ──┬── ok ──────> END
                          ├── 拒绝 ───> END（安全拒绝熔断，final_error 已置）
                          ├── 轮数尽 ─> END（final_error 已置）
                          └── else ──> fix ──> execute（错误回喂重生成）

与手写循环等价（行为、RoundTrace、AgentResult 完全一致），对外 run_agent 接口不变
——server / 评测脚本零改动，回归评测可直接对比。
为什么上 LangGraph：条件路由/熔断/重试这类"控制流即图"，声明式边取代嵌套循环，
后续加节点（如呈现、审核）只是 add_node + add_edge。
"""

from dataclasses import dataclass, field
from datetime import date
from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.agent.sql_gen import SYSTEM_TEMPLATE, extract_sql
from app.core.config import get_settings
from app.core.llm import chat
from app.core.observability import note_metadata, obs
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
        return max(0, len(self.rounds) - 1)


class AgentState(TypedDict, total=False):
    question: str
    messages: list
    traces: list          # 每轮 RoundTrace（评测的 rounds/首过率指标来源）
    round_no: int
    sql: str
    ok: bool
    error: str
    columns: list
    rows: list
    success: bool
    final_error: str


def _build_graph(on_event=None):
    s = get_settings()

    def system_msg() -> dict:
        return {"role": "system",
                "content": SYSTEM_TEMPLATE.format(today=date.today().isoformat(),
                                                  schema=get_schema_doc())}

    def node_generate(state: AgentState) -> AgentState:
        sql = extract_sql(chat([system_msg(),
                                {"role": "user", "content": f"问：{state['question']}"}],
                               temperature=0))
        return {"messages": [system_msg(), {"role": "user", "content": f"问：{state['question']}"}],
                "sql": sql, "round_no": 1}

    def node_fix(state: AgentState) -> AgentState:
        messages = list(state["messages"])
        messages.append({"role": "assistant", "content": f"```sql\n{state['sql']}\n```"})
        messages.append({"role": "user", "content": (
            f"你生成的 SQL 执行失败：\n{state['error']}\n\n{FIX_HINT}\n"
            f"请修正后重新输出 SQL（只输出 ```sql 代码块）。")})
        sql = extract_sql(chat(messages, temperature=0))
        return {"messages": messages, "sql": sql, "round_no": state["round_no"] + 1}

    @obs("sql_execute", capture_input=False)
    def node_execute(state: AgentState) -> AgentState:
        r = run_sql(state["sql"])
        cls = classify_error(r.error) if not r.ok else ""
        trace = RoundTrace(state["round_no"], state["sql"], r.ok,
                           r.error if not r.ok else "", cls, r.elapsed_ms)
        note_metadata(round_no=state["round_no"], ok=r.ok, error_class=cls,
                      elapsed_ms=r.elapsed_ms)
        if on_event:
            on_event({"type": "round", **vars(trace)})
        out: AgentState = {"ok": r.ok, "error": r.error if not r.ok else "",
                           "traces": state.get("traces", []) + [trace]}
        if r.ok:
            out.update(success=True, columns=r.columns, rows=r.rows)
            return out
        # 安全拒绝必须熔断循环——实测若继续走修复回填，模型会"绕道"：
        # 生成一条 SELECT 'Table has been dropped' 假装删表成功（badcase 6）
        if cls == "拒绝":
            out["final_error"] = ("该请求要求删除/修改数据。AskData 是只读分析系统，"
                                  "已拒绝执行——不会真的动库，也不会假装执行。")
            return out
        if state["round_no"] >= s.max_fix_rounds + 1:
            out["final_error"] = r.error
        return out

    def route_after_execute(state: AgentState) -> str:
        if state.get("success"):
            return "done"
        if state.get("final_error"):       # 拒绝熔断 或 轮数耗尽
            return "stop"
        return "fix"

    builder = StateGraph(AgentState)
    builder.add_node("generate", node_generate)
    builder.add_node("execute", node_execute)
    builder.add_node("fix", node_fix)
    builder.set_entry_point("generate")
    builder.add_edge("generate", "execute")
    builder.add_edge("fix", "execute")
    builder.add_conditional_edges(
        "execute", route_after_execute,
        {"done": END, "stop": END, "fix": "fix"})
    return builder.compile()


# 评测/前端复用同一张编译图；带自定义 on_event 时按需重编译（compile 开销毫秒级）
_GRAPH = _build_graph()


def run_agent(question: str, on_event=None) -> AgentResult:
    graph = _build_graph(on_event) if on_event else _GRAPH
    final = graph.invoke({"question": question})

    result = AgentResult(question=question, success=bool(final.get("success")))
    result.rounds = final.get("traces", [])
    if result.success:
        result.columns = final.get("columns", [])
        result.rows = final.get("rows", [])
    else:
        result.final_error = final.get("final_error") or final.get("error") or "未知错误"
    return result
