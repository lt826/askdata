"""FastAPI 服务：SSE 流式问答（修复循环轮次实时推送）+ 图表静态服务。

SSE 事件协议（前后端契约）：
  round   {round_no, sql, ok, error, error_class, elapsed_ms}  SQL 修复循环每轮
  summary {text}                                                 中文结论
  chart   {chart_type, url}                                      图表（/api/charts/xx.png）
  table   {columns, rows, total}                                 表格（最多推 100 行）
  error   {message}                                              执行异常
  done    {}                                                     本轮结束

线程模型同 FitPilot：run_agent 阻塞，放工作线程，事件经 queue 给 SSE 生成器。
"""

import json
import queue
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.agent.present import present
from app.agent.sql_agent import run_agent
from app.core.config import get_settings
from app.core.observability import finish_turn, shutdown_client, turn_trace
from app.core.security import create_token, limiter, verify_token
from app.db.schema_doc import get_schema_doc

CHART_DIR = Path(__file__).resolve().parents[2] / "data" / "charts"

# ---- 展示层列名翻译：模型起的英文别名 → 中文（图表图例与表头共用）----
COLUMN_ZH = {
    # 常见聚合别名
    "sales": "销售额", "gmv": "GMV", "revenue": "营收", "amount": "金额",
    "order_count": "订单量", "orders": "订单量", "order_num": "订单量",
    "user_count": "用户数", "users": "用户数", "cnt": "数量", "count": "数量",
    "qty": "销量", "quantity": "销量", "aov": "客单价", "avg_amount": "平均金额",
    "month": "月份", "week": "周", "day": "日期", "date": "日期",
    # 维度列
    "channel": "渠道", "city": "城市", "category": "品类", "subcategory": "子类",
    "gender": "性别", "member_level": "会员等级", "brand": "品牌",
    "product_name": "商品名", "name": "名称",
    # 原始表列（SELECT * / 明细题）
    "order_id": "订单号", "user_id": "用户ID", "product_id": "商品ID",
    "order_date": "下单日期", "register_date": "注册日期", "status": "状态",
    "unit_price": "单价", "cost_price": "成本价", "sales_percentage": "销售额占比",
}


def zh_cols(columns: list[str]) -> list[str]:
    """展示层列名中文化：把模型的英文别名翻译成中文（表头与图例共用）。

    翻译策略三层：精确字典（sales→销售额/维度列/原始表列）→ 后缀规则
    （*_percentage→"xx占比"、total_*→"总xx"，递归处理前半段）→ 翻不出
    原样保留（宁缺毋滥不瞎翻）。放出口而非要求模型起中文名——出口
    兜底 > 生成端自觉（提示词规则模型只是"有时候听"）。
    """
    def one(c: str) -> str:
        low = str(c).lower()
        if low in COLUMN_ZH:
            return COLUMN_ZH[low]
        if str(c) in COLUMN_ZH:
            return COLUMN_ZH[str(c)]
        if low.endswith(("_percentage", "_pct", "_ratio")):
            return one(low.rsplit("_", 1)[0]) + "占比"
        if low.endswith("_count"):
            return one(low.rsplit("_", 1)[0]) + "数"
        if low.endswith("_rate"):
            return one(low.rsplit("_", 1)[0]) + "率"
        if low.startswith("total_"):
            return "总" + one(low[6:])
        if low.startswith("avg_"):
            return "平均" + one(low[4:])
        return str(c)

    return [one(c) for c in columns]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    shutdown_client()  # 退出前冲刷 LangFuse 缓冲，保住最后几条 trace


app = FastAPI(title="AskData API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5175", "http://127.0.0.1:5175"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/api/charts", StaticFiles(directory=str(CHART_DIR)), name="charts")


class AskIn(BaseModel):
    question: str


class LoginIn(BaseModel):
    password: str


@app.post("/api/login")
def login(body: LoginIn):
    """口令换 JWT。登录本身也限流（防爆破）。"""
    limiter.limit("login", 10)
    if body.password != get_settings().admin_password:
        raise HTTPException(status_code=401, detail="口令错误")
    return {"token": create_token("admin"), "expires_in": get_settings().jwt_expire_hours * 3600}


@app.post("/api/ask")
def ask_stream(body: AskIn, user: str = Depends(verify_token)):
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="question 不能为空")
    # 限流按用户计：每次问答都要花 LLM token，这是配额的第一道闸
    limiter.limit(f"ask:{user}", get_settings().rate_limit_per_min)

    events: queue.Queue = queue.Queue()

    def worker() -> None:
        # 根 trace 必须开在工作线程内：OTel 上下文不跨线程，
        # 线程内开根后 llm_chat/sql_execute/present 自动挂到同一棵树
        with turn_trace(body.question) as root:
            try:
                r = run_agent(body.question,
                              on_event=lambda e: events.put(("round", e)))
                finish_turn(root, r.success, len(r.rounds),
                            r.rounds[-1].error_class if r.rounds and not r.success else "")
                if not r.success:
                    events.put(("error", {"message": r.final_error}))
                    return
                p = present(r.question, r.columns, r.rows)
                events.put(("summary", {"text": p.summary}))
                if p.kind == "chart" and p.chart_path:
                    # 优先前端 ECharts 交互渲染；matplotlib PNG 作为兜底/离线报告用
                    events.put(("chart", {
                        "chart_type": p.chart_type,
                        "url": "/api/charts/" + Path(p.chart_path).name,
                        "columns": zh_cols(r.columns),
                        "rows": r.rows[:200]}))
                events.put(("table", {"columns": zh_cols(r.columns),
                                      "rows": r.rows[:100],
                                      "total": len(r.rows)}))
            except Exception as exc:  # noqa: BLE001 —— SSE 必须把异常传到前端
                events.put(("error", {"message": f"{exc.__class__.__name__}: {exc}"}))
            finally:
                events.put(None)  # 结束哨兵

    threading.Thread(target=worker, daemon=True).start()

    def gen():
        while True:
            item = events.get()
            if item is None:
                break
            event, data = item
            # default=str：结果里的 date 等类型转字符串，否则序列化炸掉整个 SSE 流
            yield f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/api/schema")
def schema(_: str = Depends(verify_token)):
    """数据字典原文（前端弹窗展示用）。"""
    return {"schema_doc": get_schema_doc()}

# ---------------- 生产模式：同源托管前端构建产物 ----------------
# 开发期前后端分端口（5175/8001，Vite 代理）；生产把 web/dist 挂到根路径，
# 单 uvicorn 进程同时服务页面与 API（与 FitPilot 生产部署同款方案）。
# 静态页面本身无需登录（登录页要能加载）；数据安全由 /api/* 的 JWT 把守。
# 必须放在所有路由之后：挂载在 "/" 的 StaticFiles 会吞掉后续未匹配路径。
from pathlib import Path  # noqa: E402

from fastapi.staticfiles import StaticFiles  # noqa: E402

_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"
if _DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="frontend")
else:
    print("[提示] 未找到 web/dist，当前为纯 API 模式（前端请用 npm run dev）")
