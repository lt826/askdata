"""CLI 验收：问一句话 → 生成 SQL → 护栏执行 → 打印结果表。

用法: uv run scripts/ask.py "上个月销售额最高的五个品类"
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agent.sql_gen import generate_sql  # noqa: E402
from app.db.executor import run_sql  # noqa: E402


def ask(question: str) -> None:
    print(f"\n❓ {question}")
    sql = generate_sql(question)
    print(f"📝 SQL:\n{sql}\n")
    r = run_sql(sql)
    if not r.ok:
        print(f"❌ {r.error}")
        return
    df = pd.DataFrame(r.rows, columns=r.columns)
    print(df.head(15).to_string(index=False))
    extra = f"（仅展示前 15 行，共 {r.row_count} 行）" if r.row_count > 15 else ""
    print(f"✅ {r.row_count} 行 · {r.elapsed_ms}ms {extra}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        ask(" ".join(sys.argv[1:]))
    else:
        for q in [
            "上个月销售额最高的五个品类",
            "各会员等级的用户数和平均客单价",
            "2026年6月18日当天的订单量和销售额是多少",
            "把 orders 表删了",
        ]:
            ask(q)
