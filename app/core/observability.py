"""LangFuse 可观测层（v5 SDK，OpenTelemetry 架构）。

核心设计原则：**观测系统绝不能成为业务的故障点**——
所有入口（obs 装饰器 / note_* / turn_trace）在未配置 Key 或 SDK 报错时
全部退化为直通，业务路径零感知。

打点位置：
- ask_turn       每次问答的根 trace（成功/轮数/修复轮数/错误分类/耗时——修复轮数=核心质量指标）
- llm_chat       每次 LLM 调用（generation：模型/用量/成本——SQL生成/修复/呈现决策共用）
- sql_execute    每轮 SQL 执行（含护栏拦截）
- present        呈现决策（表格/图型）
"""

from __future__ import annotations

from contextlib import contextmanager

from app.core.config import get_settings

_client = None  # 模块级单例；None 表示未启用


def get_client():
    """返回初始化的 Langfuse 客户端；未配置 Key 时返回 None（观测关闭）。"""
    global _client
    if _client is not None:
        return _client
    s = get_settings()
    if not (s.langfuse_public_key and s.langfuse_secret_key):
        return None
    from langfuse import Langfuse

    _client = Langfuse(
        public_key=s.langfuse_public_key,
        secret_key=s.langfuse_secret_key,
        host=s.langfuse_host,
        flush_at=5,
        flush_interval=3,
    )
    return _client


def obs(name: str | None = None, as_type: str | None = None,
        capture_output: bool | None = None, capture_input: bool | None = None):
    """@observe 装饰器的降级包装：未配置时原样返回被装饰函数。

    注意：装饰实例方法时 self 会进入观测入参，方法里带大对象（如 Qdrant 客户端）
    的场景应 capture_input=False 并用 note_metadata 手动记关键入参。
    """
    if get_client() is None:
        return lambda f: f
    from langfuse import observe

    kwargs: dict = {}
    if capture_output is not None:
        kwargs["capture_output"] = capture_output
    if capture_input is not None:
        kwargs["capture_input"] = capture_input
    return observe(name=name, as_type=as_type, **kwargs)


def note_generation_usage(model: str, prompt_tokens, completion_tokens) -> None:
    """给当前 generation 观测补记 token 用量——LangFuse 成本统计的数据源。

    用量同时写入 metadata：v2 查询接口的列表视图不回传 usageDetails，
    metadata 是统计脚本的兜底读取通道。
    """
    c = get_client()
    if c is None:
        return
    p, o = int(prompt_tokens or 0), int(completion_tokens or 0)
    try:
        c.update_current_generation(
            model=model, usage_details={"input": p, "output": o},
            metadata={"prompt_tokens": p, "completion_tokens": o},
        )
    except Exception:  # noqa: BLE001 —— 观测失败静默，不影响业务
        pass


def note_metadata(**kw) -> None:
    """给当前观测补记元数据（如检索命中、路由结果）。"""
    c = get_client()
    if c is None:
        return
    try:
        c.update_current_span(metadata=kw)
    except Exception:  # noqa: BLE001
        pass


@contextmanager
def turn_trace(question: str):
    """一轮对话的根观测。

    必须包住整个 stream_chat（在 worker 线程内调用）：
    OTel 上下文本不跨线程，在线程内开根 trace 后，内部所有
    @obs 装饰的调用（路由/检索/LLM/工具）自动挂到同一棵树上。
    session/user 用官方的 propagate_attributes 通道设置并向下传播。
    """
    c = get_client()
    if c is None:
        yield None
        return
    from langfuse import propagate_attributes

    with c.start_as_current_observation(name="ask_turn", as_type="chain", input=question) as root:
        with propagate_attributes(user_id="local-user", tags=["askdata"]):
            yield root


def finish_turn(root, success: bool, rounds_used: int, error_class: str = "") -> None:
    """回合收尾：核心质量指标写回根 trace——修复轮数分布是 LangFuse 面板的看板指标。"""
    if root is None:
        return
    try:
        root.update(output={"success": success, "rounds_used": rounds_used},
                    metadata={"success": success, "rounds_used": rounds_used,
                              "fix_rounds": max(0, rounds_used - 1),
                              "error_class": error_class})
    except Exception:  # noqa: BLE001
        pass


def shutdown_client() -> None:
    """进程退出前冲刷缓冲区，保证最后几条 trace 不丢。"""
    global _client
    if _client is not None:
        try:
            _client.shutdown()
        except Exception:  # noqa: BLE001
            pass
        _client = None
