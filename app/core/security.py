"""认证与限流（设计为可复用组件：FitPilot 等项目直接拷走即用）。

- JWT：HS256，登录换 token，过期 401。无用户体系，单管理员口令制（demo 场景）
- 限流：进程内滑动窗口，按 key（token 用户 / IP）计数，超限 429 + Retry-After
  多 worker 部署时换 Redis 计数器即可（接口不变，注释在类上）
"""

import time
from collections import defaultdict, deque

import jwt
from fastapi import HTTPException, Request

from app.core.config import get_settings

ALG = "HS256"


def create_token(username: str) -> str:
    s = get_settings()
    now = int(time.time())
    payload = {"sub": username, "iat": now,
               "exp": now + s.jwt_expire_hours * 3600}
    return jwt.encode(payload, s.jwt_secret, algorithm=ALG)


def verify_token(request: Request) -> str:
    """FastAPI 依赖：从 Authorization: Bearer 验签，返回用户名。"""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    try:
        payload = jwt.decode(auth[7:], get_settings().jwt_secret, algorithms=[ALG])
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="无效凭证")


class RateLimiter:
    """滑动窗口限流器（进程内版；多 worker 换 Redis ZSET，方法签名不变）。

    limit(key, max_n, window_s) -> None 或抛 429。
    """

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def limit(self, key: str, max_n: int, window_s: int = 60) -> None:
        now = time.monotonic()
        q = self._hits[key]
        while q and q[0] <= now - window_s:
            q.popleft()
        if len(q) >= max_n:
            retry = int(q[0] + window_s - now) + 1
            raise HTTPException(
                status_code=429,
                detail=f"请求过于频繁（{window_s}s 内限 {max_n} 次），{retry}s 后重试",
                headers={"Retry-After": str(retry)},
            )
        q.append(now)


limiter = RateLimiter()
