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
    """返回 None 表示通过，否则返回给模型看的错误说明。"""
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
    if re.search(r"\blimit\s+\d+", sql, re.I):
        return sql
    return f"SELECT * FROM ({sql}) AS _auto_limited LIMIT {AUTO_LIMIT}"


def run_sql(sql: str) -> ExecResult:
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
