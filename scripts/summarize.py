"""评测汇总：从 last_run.jsonl 生成指标与 docs/eval-report.md。

指标口径：
- 执行准确率 = 非拒答题中结果集比对通过的比例（不含 gold_error 基建错）
- 拒答召回 = 拒答题中正确拒绝（未执行任何 SQL）的比例
- 首过率 = 第 1 轮生成即执行成功的比例
- 平均修复轮数 = 非首过但最终成功者平均多用的轮数（修复循环价值）
"""

import json
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

EVAL_DIR = Path(__file__).resolve().parents[1] / "data" / "eval"
REPORT = Path(__file__).resolve().parents[1] / "docs" / "eval-report.md"


def main() -> None:
    recs = [json.loads(l) for l in open(EVAL_DIR / "last_run.jsonl", encoding="utf-8")]
    verdict = Counter(r["verdict"] for r in recs)

    answerable = [r for r in recs if r["type"] != "reject" and r["verdict"] != "gold_error"]
    acc = sum(r["verdict"] == "pass" for r in answerable) / max(len(answerable), 1)
    rejects = [r for r in recs if r["type"] == "reject"]
    rej_recall = sum(r["verdict"] == "pass" for r in rejects) / max(len(rejects), 1)
    first_pass = sum(bool(r.get("first_pass")) for r in answerable) / max(len(answerable), 1)
    fixed = [r for r in answerable if r["verdict"] == "pass" and not r.get("first_pass")]
    avg_fix = (sum(r["rounds_used"] - 1 for r in fixed) / len(fixed)) if fixed else 0
    avg_s = sum(r["elapsed_s"] for r in recs) / max(len(recs), 1)

    by_type = defaultdict(lambda: [0, 0])
    for r in answerable:
        by_type[r["type"]][1] += 1
        by_type[r["type"]][0] += r["verdict"] == "pass"

    lines = [
        "# AskData 执行准确率评测报告",
        "",
        f"- 日期：{date.today().isoformat()}　模型：glm-4-flash　题量：{len(recs)}",
        f"- 判定：生成 SQL 与标准 SQL **结果集逐行比对**（列数相等 + 行多重集相等，数值 ROUND 2 位）——确定性判定，无裁判模型",
        "",
        "## 总指标",
        "",
        "| 指标 | 数值 |",
        "|---|---|",
        f"| **执行准确率**（非拒答题） | **{acc:.1%}**（{sum(r['verdict']=='pass' for r in answerable)}/{len(answerable)}） |",
        f"| 拒答召回（域外/恶意题） | **{rej_recall:.1%}**（{sum(r['verdict']=='pass' for r in rejects)}/{len(rejects)}） |",
        f"| 首过率（第 1 轮即成功） | {first_pass:.1%} |",
        f"| 修复循环救回 | {len(fixed)} 题（平均多用 {avg_fix:.2f} 轮） |",
        f"| 平均单题耗时 | {avg_s:.1f}s |",
        "",
        "## 分题型准确率",
        "",
        "| 题型 | 准确率 |",
        "|---|---|",
    ]
    for t, (ok, n) in sorted(by_type.items(), key=lambda kv: -kv[1][1]):
        lines.append(f"| {t} | {ok}/{n}（{ok/n:.0%}） |")

    lines += ["", "## 失败明细（修复迭代用）", ""]
    for r in recs:
        if r["verdict"] in ("fail", "gold_error"):
            lines.append(f"- **{r['id']}** [{r['type']}] {r['question']}：{r.get('detail','')[:110]}")

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:18]))
    print(f"\n报告已写入 {REPORT}")


if __name__ == "__main__":
    main()
