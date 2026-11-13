"""SQL 执行器：三层护栏 + 结构化结果。

护栏分层（由软到硬）：
1. 关键词白名单 —— 拒绝非 SELECT 语句，报"友好错误"回喂修复循环（第 3 步用）
2. read_only 连接 —— DuckDB 引擎层拒绝一切写操作，提示词/白名单被绕过也写不进库
3. LIMIT 兜底 —— 没写 LIMIT 的查询自动包一层 LIMIT 200，防 10 万行打爆上下文
4. 超时熔断 —— 线程执行 + conn.interrupt()，防非预期全表扫描拖死服务

错误信息刻意写成"模型可读"格式（含建议），为第 3 步修复循环回喂做准备。
"""

import re
import threading
import time
from dataclasses import dataclass, field

from app.db.duck import get_conn

FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|replace|"
    r"copy|export|import|attach|detach|pragma|call|set)\b", re.I)
QUERY_TIMEOUT_S = 15
AUTO_LIMIT = 200


@dataclass
class ExecResult:
    ok: bool
    sql: str = ""
    columns: list[str] = field(default_factory=list)
    rows: list[tuple] = field(default_factory=list)
    row_count: int = 0
    elapsed_ms: int = 0
    error: str = ""


def _guard(sql: str) -> str | None:
    """SQL 安检（护栏第 1 层）：拦截非只读语句，返回"模型可读"的拒绝理由。

    三项检查，任一不过即拒绝：
      1. 首词必须是 select / with —— 拦 DROP/INSERT/UPDATE 等一切非查询
         （with 是放行 CTE 子查询）
      2. 禁写关键字正则扫描 —— 拦"SELECT 1; DROP TABLE"这种藏在中间的写操作
      3. 多分号拒绝 —— 只允许单条语句，防连环注入

    参数: sql 待检查的 SQL
    返回:  None=通过；字符串=拒绝原因（格式刻意写成模型可读，
           因为它会被 fix 节点回喂给模型当修正依据）
    """
    first = sql.lstrip("( \n").split(None, 1)[0].lower() if sql.strip() else ""
    if first not in ("select", "with"):
        return (f"[SQL被拒绝] 只允许 SELECT 查询，当前语句以 '{first}' 开头。"
                f"请重写为一条只读 SELECT。")
    m = FORBIDDEN.findall(sql)
    if m:
        return (f"[SQL被拒绝] 检测到写操作关键字 {sorted(set(w.lower() for w in m))}，"
                f"只允许只读 SELECT。")
    if ";" in sql:
        return "[SQL被拒绝] 只允许单条语句（检测到多个分号）。"
    return None


def _auto_limit(sql: str) -> str:
    """LIMIT 兜底（护栏第 3 层）：没写 LIMIT 的查询自动包一层 LIMIT 200。

    防两种事故：用户要"所有订单"时 10 万行打爆前端渲染、打爆呈现层
    LLM 的上下文。只兜"模型忘了写"的情况——SQL 自带 LIMIT 则尊重原意
    （用户明确要 10000 行就给 10000 行，由下游各出口再分层截断）。
    """
    if re.search(r"\blimit\s+\d+", sql, re.I):
        return sql
    return f"SELECT * FROM ({sql}) AS _auto_limited LIMIT {AUTO_LIMIT}"


def run_sql(sql: str) -> ExecResult:
    """执行一条 SQL，全程四层防护（execute 节点的内核）。

    流程：_guard 安检 → _auto_limit 包 LIMIT → read_only 连接（护栏第 2 层，
    引擎级物理只读，白名单被绕过也写不进库）→ 工作线程执行 → join 超时
    15s 则 conn.interrupt() 掐断（护栏第 4 层，Python 线程杀不掉但 DuckDB
    提供中断接口）。

    参数: sql 单条 SELECT（已过安检或即将过）
    返回:  ExecResult{ok, columns, rows, row_count, elapsed_ms, error}
           —— 错误同样格式化为模型可读文本，供修复循环回喂
    """
    err = _guard(sql)
    if err:
        return ExecResult(ok=False, sql=sql, error=err)

    final_sql = _auto_limit(sql)
    conn = get_conn(read_only=True)
    box: dict = {}

    def _worker() -> None:
        try:
            cur = conn.execute(final_sql)
            box["columns"] = [d[0] for d in cur.description]
            box["rows"] = cur.fetchall()
        except Exception as exc:  # noqa: BLE001 —— 错误信息要回喂模型自纠，不能吞
            box["error"] = f"[执行出错] {exc}"

    t0 = time.perf_counter()
    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    t.join(QUERY_TIMEOUT_S)
    elapsed = int((time.perf_counter() - t0) * 1000)

    try:
        if t.is_alive():
            conn.interrupt()
            return ExecResult(ok=False, sql=final_sql, elapsed_ms=elapsed,
                              error=f"[执行超时] 超过 {QUERY_TIMEOUT_S}s 未完成，"
                                    f"请检查是否缺 WHERE 过滤或 join 笛卡尔积。")
        if "error" in box:
            return ExecResult(ok=False, sql=final_sql, elapsed_ms=elapsed,
                              error=box["error"])
        rows = box["rows"]
        return ExecResult(ok=True, sql=final_sql, columns=box["columns"],
                          rows=rows, row_count=len(rows), elapsed_ms=elapsed)
    finally:
        conn.close()
