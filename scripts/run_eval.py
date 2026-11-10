"""执行准确率评测：生成 SQL vs gold SQL 结果集逐行比对（确定性判定，无裁判模型）。

判定口径：
- 非拒答题：执行准确率 = 生成 SQL 与 gold SQL 的结果集（列数相等 + 行多重集相等，
  数值统一 ROUND 到 2 位后比较）完全一致才算对
- 拒答题：召回 = Agent 未执行任何成功 SQL（success=False），且如实说明
- 过程指标：首过率（第 1 轮就执行成功）、平均修复轮数（灵魂指标）

断点续跑：结果逐题追加 last_run.jsonl，重跑自动跳过已完成题。
用法: uv run scripts/run_eval.py [--limit 30] [--workers 4]
"""

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agent.sql_agent import run_agent  # noqa: E402
from app.db.duck import get_conn  # noqa: E402

EVAL_DIR = Path(__file__).resolve().parents[1] / "data" / "eval"
CKPT = EVAL_DIR / "last_run.jsonl"


def norm_rows(rows):
    """数值 ROUND 2 位、行排序后转 tuple，做多重集比较。"""
    out = []
    for row in rows:
        out.append(tuple(round(v, 2) if isinstance(v, (int, float)) and not isinstance(v, bool) else v
                         for v in row))
    return sorted(out, key=repr)


def run_gold(gold_sql: str):
    conn = get_conn(read_only=True)
    try:
        cur = conn.execute(gold_sql)
        cols = [d[0] for d in cur.description]
        return cols, cur.fetchall()
    finally:
        conn.close()


def judge(item: dict) -> dict:
    t0 = time.perf_counter()
    r = run_agent(item["question"])
    rec = {
        "id": item["id"], "type": item["type"], "question": item["question"],
        "rounds_used": len(r.rounds), "first_pass": len(r.rounds) == 1 and r.success,
        "error_class": r.rounds[-1].error_class if r.rounds and not r.success else "",
        "elapsed_s": round(time.perf_counter() - t0, 1),
    }

    if item["type"] == "reject":
        rec["verdict"] = "pass" if not r.success else "fail"
        rec["detail"] = "正确拒绝" if not r.success else "漏拒：执行了SQL并返回结果"
        return rec

    if not r.success:
        rec["verdict"] = "fail"
        rec["detail"] = f"执行失败({r.final_error[:80]})"
        return rec

    try:
        gcols, grows = run_gold(item["gold_sql"])
    except Exception as exc:  # gold 本身出错——评测基建 bug，单独标记
        rec["verdict"] = "gold_error"
        rec["detail"] = f"gold执行失败: {exc}"
        return rec

    ok = (len(r.columns) == len(gcols)
          and norm_rows(r.rows) == norm_rows(grows))
    rec["verdict"] = "pass" if ok else "fail"
    if not ok:
        rec["detail"] = (f"结果不一致: 生成{len(r.columns)}列{len(r.rows)}行 vs "
                         f"gold{len(gcols)}列{len(grows)}行; 生成SQL={r.rounds[-1].sql[:120]}")
    return rec


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="只跑前 N 题（调试用）")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    import csv
    with open(EVAL_DIR / "eval_set.csv", encoding="utf-8-sig") as f:
        items = list(csv.DictReader(f))

    done = set()
    if CKPT.exists():
        with open(CKPT, encoding="utf-8") as f:
            done = {json.loads(line)["id"] for line in f if line.strip()}
    todo = [it for it in items if it["id"] not in done]
    if args.limit:
        todo = todo[: args.limit]
    print(f"总 {len(items)} 题，已完成 {len(done)}，本轮跑 {len(todo)}")

    CKPT.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    with open(CKPT, "a", encoding="utf-8") as out, ThreadPoolExecutor(args.workers) as ex:
        futs = {ex.submit(judge, it): it for it in todo}
        for i, fut in enumerate(as_completed(futs), 1):
            rec = fut.result()
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            out.flush()
            mark = {"pass": "✅", "fail": "❌", "gold_error": "⚠️"}[rec["verdict"]]
            if i % 10 == 0 or rec["verdict"] != "pass":
                print(f"  [{i}/{len(todo)}] {mark} {rec['id']} {rec['type']} "
                      f"{rec.get('detail', '')[:70]}")
            elif i % 5 == 0:
                print(f"  [{i}/{len(todo)}] ✅ {rec['id']}")
    print(f"本轮完成，用时 {time.time()-t0:.0f}s。汇总用 summarize.py / 下一步生成报告")


if __name__ == "__main__":
    main()
