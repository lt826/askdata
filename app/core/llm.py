"""LLM 客户端：OpenAI 兼容协议直连智谱（与 FitPilot 同款通道，免新依赖）。"""

from functools import lru_cache

from openai import OpenAI

from app.core.config import get_settings


@lru_cache
def get_llm_client() -> OpenAI:
    s = get_settings()
    if not s.zhipu_api_key:
        raise RuntimeError("缺少 ZHIPU_API_KEY：请复制 .env.example 为 .env 并填入")
    return OpenAI(api_key=s.zhipu_api_key, base_url=s.zhipu_base_url)


def chat(messages: list[dict], model: str | None = None,
         temperature: float = 0.2, **kwargs) -> str:
    """一次性返回完整文本。SQL 生成/修复循环用（结构化任务，低温度）。"""
    client = get_llm_client()
    resp = client.chat.completions.create(
        model=model or get_settings().chat_model,
        messages=messages,
        temperature=temperature,
        **kwargs,
    )
    return (resp.choices[0].message.content or "").strip()
