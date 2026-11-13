"""呈现层：表格/图型决策 → 图表代码生成 → 沙箱渲染 → 中文结论。

一次 LLM 调用同时产出：呈现方式、图型、画图代码、数据结论（JSON）。
画图代码失败走轻量重试（错误回喂 1 次）——与 SQL 修复循环同一哲学。
"""

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from app.agent.sandbox import run_chart_code
from app.core.llm import chat
from app.core.observability import note_metadata, obs

CHART_DIR = Path(__file__).resolve().parents[2] / "data" / "charts"

DECIDE_TEMPLATE = """你是数据分析呈现专家。根据问题和查询结果，决定呈现方式；适合出图则生成 matplotlib 代码。

只输出一个 JSON（不要围栏不要解释）：
{{"kind": "table 或 chart", "chart_type": "bar/line/pie，table 则为 null", "summary": "一两句中文结论，直接带关键数字", "code": "chart 时给画图代码，table 给 null"}}

summary 铁律：只能引用"数据预览"里出现的原数字，禁止自己换算百分比/加总/平均——心算必错（实测）。占比类结论交给图的 autopct 显示。

图表判断：
- 维度+数值两列、类别不多 → bar（排名对比）
- 按月/按日时间序列 → line（趋势）
- 占比构成且类别 ≤ 8 → pie（构成）
- 标量/单行/多列明细/类别过多 → table

code 规则（必须遵守）：
- 变量 df（pandas.DataFrame，列名同查询结果）和 plt 已注入；禁止任何 import；禁止 plt.show()
- 中文字体已配置，直接写中文标题和轴标签
- 必须以 plt.savefig(OUT, dpi=150, bbox_inches='tight') 收尾，然后 plt.close()
- 数字轴从 0 起或按数据合理范围；金额大数可用 plt.ticklabel_format 关闭科学计数

问题：{question}
结果列：{columns}
行数：{n}
数据预览：
{head}"""


@dataclass
class PresentResult:
    kind: str                 # table / chart
    chart_type: str = ""
    summary: str = ""
    chart_path: str = ""      # 空串=无图
    chart_error: str = ""     # 渲染重试后仍失败时记录（表格照常返回，降级不阻断）


def _parse_json(text: str) -> dict:
    """从模型回复中提取决策 JSON（与 extract_sql 同一设计思想：解析容错）。

    模型可能加 ```json 围栏或附带解释文字，直接 json.loads 必炸。
    用贪心正则抓第一个 { 到最后一个 } 之间的内容再解析；抓不到或解析
    失败都返回"表格+空结论"的安全默认值——呈现决策失败不阻断主流程。
    """
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return {"kind": "table", "summary": "", "code": None}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"kind": "table", "summary": "", "code": None}


@obs("present", capture_input=False)
def present(question: str, columns: list[str], rows: list[tuple]) -> PresentResult:
    """呈现层：决定答案长什么样（出表格还是图、什么图、中文结论、画图代码）。

    只多调一次 LLM，输入刻意收窄（问题+列名+行数+前 12 行预览——防大结果
    打爆上下文），要求模型一次返回四合一 JSON。失败链按轻重处理：
      JSON 没解析出来 → 带反馈重问一次
      图渲染失败     → 错误回喂重画一次 → 仍败则 kind 降级为 table
    （呈现是次要交付物，最多给一次重试，不像 SQL 修复给三轮。）

    参数: question 用户问题；columns/rows 已执行成功的查询结果
    返回:  PresentResult{kind, chart_type, summary, chart_path, chart_error}
    """
    df = pd.DataFrame(rows, columns=columns)
    prompt = DECIDE_TEMPLATE.format(
        question=question, columns=columns, n=len(rows),
        head=df.head(12).to_string(index=False))
    decision = _parse_json(chat([{"role": "user", "content": prompt}], temperature=0))
    if not decision.get("summary") and not decision.get("code"):
        # 输出抖动（围栏坏了/非JSON）——带错误反馈重试一次
        decision = _parse_json(chat([
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": "（刚才的输出不是合法 JSON）"},
            {"role": "user", "content": "请严格只输出一个 JSON 对象，不要任何围栏或解释。"},
        ], temperature=0))
    note_metadata(kind=decision.get("kind"), chart_type=decision.get("chart_type"))
    result = PresentResult(
        kind=decision.get("kind") or "table",
        chart_type=decision.get("chart_type") or "",
        summary=(decision.get("summary") or "").strip(),
    )

    if result.kind != "chart" or not decision.get("code"):
        return result

    CHART_DIR.mkdir(parents=True, exist_ok=True)
    h = hashlib.md5(question.encode()).hexdigest()[:8]
    out = CHART_DIR / f"chart_{h}.png"
    code = decision["code"]
    err = run_chart_code(code, df, out)
    if err:  # 错误回喂重画一次
        retry = chat([
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": json.dumps(decision, ensure_ascii=False)},
            {"role": "user", "content": f"画图代码执行失败：{err}\n请只重新输出修正后的完整 JSON。"},
        ], temperature=0)
        decision2 = _parse_json(retry)
        if decision2.get("code"):
            err = run_chart_code(decision2["code"], df, out) or ""
    if not err and out.exists():
        result.chart_path = str(out)
    else:
        result.chart_error = err or "未知渲染错误"
        result.kind = "table"  # 图挂了降级为表格，不阻断主流程
    return result
