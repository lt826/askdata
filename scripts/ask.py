"""CLI 验收：问一句话 → 生成 SQL → 护栏执行 → 打印结果表。

用法: uv run scripts/ask.py "上个月销售额最高的五个品类"
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agent.sql_agent import run_agent  # noqa: E402


def ask(question: str) -> None:
    print(f"\n❓ {question}")
    r = run_agent(question)
    for t in r.rounds:
        mark = "✅" if t.ok else f"❌[{t.error_class}]"
        print(f"  第{t.round_no}轮 {mark} {t.elapsed_ms}ms  {t.sql[:70]}...")
        if not t.ok:
            print(f"        ↳ {t.error[:100]}")
    if r.success:
        df = pd.DataFrame(r.rows, columns=r.columns)
        print(df.head(15).to_string(index=False))
        extra = f"（仅展示前 15 行，共 {len(r.rows)} 行）" if len(r.rows) > 15 else ""
        print(f"✅ 共 {len(r.rounds)} 轮 · {len(r.rows)} 行{extra}")
    else:
        print(f"💔 修复 {r.fix_rounds_used} 轮后仍失败：{r.final_error[:120]}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        ask(" ".join(sys.argv[1:]))
    else:
        for q in [
            "各会员等级的用户数和平均客单价",   # 首轮必错：user_id 歧义 → 看修复循环
            "上周各城市的订单量排名",
            "复购用户（下单超过1次）最喜欢的三个品类",
        ]:
            ask(q)
