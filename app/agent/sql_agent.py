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
    """把执行错误粗分为五类，供路由决策与观测统计使用。

    分类→用途的映射：
      拒绝    → 路由据此熔断修复循环（badcase 6：拒绝后重试会被模型"绕道"）
      语法/列名/表/超时 → 可修复类，进 fix 节点；FIX_HINT 四条与之对应
      其他    → 兜底类，同样进修复循环
    注意这是宽分类（关键词匹配），不求精确，够路由用即可。
    """
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
    """黑板（全图共享状态）。每个字段标注：它是什么、谁写 → 谁读。

    规则：节点 return 什么字段就是改什么字段（部分更新），
    不 return 的字段原样保留；要历史的字段用追加，要现状的用覆盖。
    """

    question: str      # 用户原始问题。invoke 入口写入一次，此后全程只读
    messages: list     # 完整对话现场（system提示+问题+每轮SQL/报错）。
                       # generate 新建 → fix 追加。fix 的 LLM 上下文就靠它
    traces: list       # 每轮执行轨迹（RoundTrace 对象）。execute 累加；
                       # 不参与路由，出图后供评测算首过率/修复轮数、前端画轨迹
    round_no: int      # 当前第几轮。generate 置 1 → fix 每次 +1。
                       # execute 据此判断"轮数耗尽"（>= max_fix_rounds+1）
    sql: str           # 当前版本的 SQL。generate 写第一版 → fix 覆盖成修正版。
                       # 黑板上永远只有"当前版"，历史在 messages/traces 里
    ok: bool           # 本轮执行成败。execute 写；路由不直接看它——看暗号
    error: str         # 本轮执行错误原文（"模型可读"格式）。execute 写 → fix 当教材回喂
    columns: list      # 查询结果的列名。仅剧本A（成功）时 execute 写 → present/前端用
    rows: list         # 查询结果的数据行。同上，仅成功时写入
    success: bool      # 暗号①"考完了，过"——execute 成功时写；路由见它走 done
    final_error: str   # 暗号②"别修了，结案"——拒绝熔断或轮数耗尽时写；路由见它走 stop


def _build_graph(on_event=None):
    s = get_settings()

    def system_msg() -> dict:
        return {"role": "system",
                "content": SYSTEM_TEMPLATE.format(today=date.today().isoformat(),
                                                  schema=get_schema_doc())}

    def node_generate(state: AgentState) -> AgentState:
        """图节点①生成：问题 → 第一版 SQL。

        组装四件套（规则+今天日期+Schema白话+few-shot）调一次 LLM，
        返回黑板增量：messages（完整对话现场，fix 节点要用）、sql、round_no=1。
        """
        sql = extract_sql(chat([system_msg(),
                                {"role": "user", "content": f"问：{state['question']}"}],
                               temperature=0))
        return {"messages": [system_msg(), {"role": "user", "content": f"问：{state['question']}"}],
                "sql": sql, "round_no": 1}

    def node_fix(state: AgentState) -> AgentState:
        """图节点③修复：看着报错改作业（修复循环的核心，全手写无框架魔法）。

        在原对话现场追加两条消息——assistant 回填上一版 SQL（模型要知道
        自己在改谁）+ user 写入报错原文与 FIX_HINT 对症提示——再调一次
        LLM。返回：messages（追加后）、sql（覆盖成修正版）、round_no+1。
        """
        messages = list(state["messages"])
        messages.append({"role": "assistant", "content": f"```sql\n{state['sql']}\n```"})
        messages.append({"role": "user", "content": (
            f"你生成的 SQL 执行失败：\n{state['error']}\n\n{FIX_HINT}\n"
            f"请修正后重新输出 SQL（只输出 ```sql 代码块）。")})
        sql = extract_sql(chat(messages, temperature=0))
        return {"messages": messages, "sql": sql, "round_no": state["round_no"] + 1}

    @obs("sql_execute", capture_input=False)
    def node_execute(state: AgentState) -> AgentState:
        """图节点②执行：过四层护栏跑 SQL，按三种剧本写黑板。

        剧本A 成功   → 写 ok/success/columns/rows，路由见 success 走 done
        剧本B 可修复 → 只写 ok/error（两个暗号都不设，留给 fix）
        剧本C 拒绝/弹尽 → 额外写 final_error，路由据此熔断出图
        traces 每次累加一条（评测的首过率/修复轮数指标来源）。
        """
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
        """条件边的路由函数（纯函数，只读黑板返回下一站）。

        三个判断对应三种命运：success 有值→done（成功出图）；
        final_error 有值→stop（拒绝熔断或轮数耗尽）；两者皆无→fix
        （报错可修，进修复节点）。
        """
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
    """对外唯一入口：一句话进，执行结果+全过程轨迹出。

    流程：invoke 问题进图 → 引擎按边走节点直到 END → 读黑板翻译成
    AgentResult（rounds 即每轮轨迹，fix_rounds=len-1 是核心质量指标）。
    on_event 不为 None 时按需重编译图（节点是闭包要捕获回调，编译毫秒级），
    供 SSE 实时推送每轮执行过程。

    参数: question 用户问题；on_event 可选回调，每轮执行后被调用
    返回:  AgentResult{success, rounds, columns, rows, final_error}
    """
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
