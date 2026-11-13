"""LLM 客户端：OpenAI 兼容协议直连智谱（与 FitPilot 同款通道，免新依赖）。"""

from functools import lru_cache

from openai import OpenAI

from app.core.config import get_settings
from app.core.observability import note_generation_usage, obs


@lru_cache
def get_llm_client() -> OpenAI:
    """LLM 客户端单例：OpenAI 兼容协议直连智谱。

    全项目所有模型调用（SQL 生成/修复/呈现决策）共用这一个客户端和
    同一条通道；缺 Key 时立刻抛错（fail-fast，不带病运行）。
    @lru_cache 保证只初始化一次。
    """
    s = get_settings()
    if not s.zhipu_api_key:
        raise RuntimeError("缺少 ZHIPU_API_KEY：请复制 .env.example 为 .env 并填入")
    return OpenAI(api_key=s.zhipu_api_key, base_url=s.zhipu_base_url)


@obs("llm_chat", as_type="generation", capture_input=False)
def chat(messages: list[dict], model: str | None = None,
         temperature: float = 0.2, **kwargs) -> str:
    """一次性返回完整文本。SQL 生成/修复循环用（结构化任务，低温度）。"""
    client = get_llm_client()
    m = model or get_settings().chat_model
    resp = client.chat.completions.create(
        model=m,
        messages=messages,
        temperature=temperature,
        **kwargs,
    )
    usage = getattr(resp, "usage", None)
    note_generation_usage(m, getattr(usage, "prompt_tokens", None),
                          getattr(usage, "completion_tokens", None))
    return (resp.choices[0].message.content or "").strip()
