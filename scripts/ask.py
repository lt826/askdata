"""CLI 验收：问一句话 → 生成 SQL → 护栏执行 → 打印结果表。

用法: uv run scripts/ask.py "上个月销售额最高的五个品类"
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agent.present import present  # noqa: E402
from app.agent.sql_agent import run_agent  # noqa: E402


def ask(question: str) -> None:
    print(f"\n❓ {question}")
    r = run_agent(question)
    for t in r.rounds:
        mark = "✅" if t.ok else f"❌[{t.error_class}]"
        print(f"  第{t.round_no}轮 {mark} {t.elapsed_ms}ms  {t.sql[:70]}...")
        if not t.ok:
            print(f"        ↳ {t.error[:100]}")
    if not r.success:
        print(f"💔 修复 {r.fix_rounds_used} 轮后仍失败：{r.final_error[:120]}")
        return

    p = present(r.question, r.columns, r.rows)
    print(f"\n💬 {p.summary}")
    if p.kind == "chart" and p.chart_path:
        print(f"🖼  [{p.chart_type}] {p.chart_path}")
    elif p.chart_error:
        print(f"⚠️  图表渲染失败已降级为表格：{p.chart_error[:80]}")
    df = pd.DataFrame(r.rows, columns=r.columns)
    print(df.head(15).to_string(index=False))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        ask(" ".join(sys.argv[1:]))
    else:
        for q in [
            "近12个月每月的销售额趋势",
            "上个月各渠道的销售额占比",
            "各城市的用户数排名",
        ]:
            ask(q)
