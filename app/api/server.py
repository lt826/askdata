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

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.agent.present import present
from app.agent.sql_agent import run_agent
from app.db.schema_doc import get_schema_doc

CHART_DIR = Path(__file__).resolve().parents[2] / "data" / "charts"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield


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


@app.post("/api/ask")
def ask_stream(body: AskIn):
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="question 不能为空")

    events: queue.Queue = queue.Queue()

    def worker() -> None:
        try:
            r = run_agent(body.question,
                          on_event=lambda e: events.put(("round", e)))
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
                    "columns": r.columns,
                    "rows": r.rows[:200]}))
            events.put(("table", {"columns": r.columns,
                                  "rows": r.rows[:100],
                                  "total": len(r.rows)}))
        except Exception as exc:  # noqa: BLE001 —— SSE 必须把异常传到前端
            events.put(("error", {"message": f"{exc.__class__.__name__}: {exc}"}))
        finally:
            events.put(None)

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
def schema():
    """数据字典原文（前端弹窗展示用）。"""
    return {"schema_doc": get_schema_doc()}
