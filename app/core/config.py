"""集中配置：pydantic-settings 读 .env（密钥只进 .env，绝不入库）。"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # ---- LLM：OpenAI 兼容协议直连智谱 ----
    zhipu_base_url: str = "https://open.bigmodel.cn/api/paas/v4/"
    zhipu_api_key: str = ""
    chat_model: str = "glm-4-flash"  # 免费主力
    judge_model: str = "glm-4-flash"  # 评测裁判（暂用免费，与被测同模型有偏差，README 注明）

    # ---- 数据层 ----
    db_path: Path = PROJECT_ROOT / "data" / "sales.duckdb"  # 单文件列存分析库

    # ---- Agent ----
    max_fix_rounds: int = 3  # SQL 修复循环熔断：报错回喂重生成的最大轮数

    # ---- 认证与限流 ----
    admin_password: str = "askdata123"       # 登录口令（生产改强口令，只进 .env）
    jwt_secret: str = "change-me-in-.env"    # HS256 签名密钥
    jwt_expire_hours: int = 24
    rate_limit_per_min: int = 20             # /api/ask 每分钟上限（每次问答都花 LLM token）


@lru_cache
def get_settings() -> Settings:
    return Settings()
