"""启动 API 服务。

用法: uv run scripts/run_server.py   （或 python scripts/run_server.py）
端口 8001：避开 FitPilot 的 8000，两个项目可同时本地跑。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import uvicorn  # noqa: E402

if __name__ == "__main__":
    uvicorn.run("app.api.server:app", host="127.0.0.1", port=8001, reload=False)
