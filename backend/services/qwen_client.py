"""百炼 Qwen3 文本 + Qwen-VL 多模态模型调用封装。

仅做模型调用层面的封装，不包含任何 Agent 业务逻辑（Agent 在 Task 3 实现）。
依赖 dashscope SDK，通过 asyncio.to_thread 把同步 SDK 调用包装成异步。

支持两种 Key：
1. 普通账号 Key：DASHSCOPE_API_KEY=sk-xxx，SDK 默认走 https://dashscope.aliyuncs.com
2. 业务空间 Key：DASHSCOPE_API_KEY=sk-ws-xxx，必须配 DASHSCOPE_API_BASE 指向业务空间专属网关
   （业务空间网关形如 https://llm-xxx.cn-beijing.maas.aliyuncs.com/api/v1）
"""
from __future__ import annotations

import asyncio
from typing import Any

import dashscope

from config import settings

# 全局设置 dashscope api_key（dashscope SDK 依赖该模块级变量）
dashscope.api_key = settings.DASHSCOPE_API_KEY

# 业务空间专属网关：若配置了 DASHSCOPE_API_BASE，则覆盖 SDK 默认域名
# dashscope SDK 的网关地址由 dashscope.base_http_api_url 控制
if settings.DASHSCOPE_API_BASE:
    dashscope.base_http_api_url = settings.DASHSCOPE_API_BASE


def _ensure_api_key() -> None:
    """校验 API Key 是否已配置，未配置则抛 ValueError。"""
    if not settings.DASHSCOPE_API_KEY:
        raise ValueError(
            "DASHSCOPE_API_KEY 未配置：请在 backend/.env 中设置真实的百炼 API Key"
        )


def _extract_text(response: Any) -> str:
    """从 dashscope Generation 响应中提取 assistant 文本。

    result_format='message' 时结构为：
        response.output.choices[0].message.content
    """
    output = getattr(response, "output", None)
    if output is None:
        raise RuntimeError(f"dashscope 响应缺少 output 字段：{response}")
    choices = getattr(output, "choices", None) or []
    if not choices:
        raise RuntimeError(f"dashscope 响应 choices 为空：{output}")
    message = choices[0].get("message") if isinstance(choices[0], dict) else getattr(choices[0], "message", None)
    if message is None:
        raise RuntimeError(f"dashscope 响应缺少 message：{choices[0]}")
    content = message.get("content") if isinstance(message, dict) else getattr(message, "content", None)
    if content is None:
        raise RuntimeError(f"dashscope 响应缺少 content：{message}")
    # content 通常是字符串；个别版本可能返回 list，做兼容
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                parts.append(item["text"])
            elif isinstance(item, str):
                parts.append(item)
        return "".join(parts)
    return str(content)


def _extract_vl_text(response: Any) -> str:
    """从 dashscope MultiModalConversation 响应中提取 assistant 文本。

    多模态响应 message.content 是 list，形如 [{"text": "..."}]。
    """
    output = getattr(response, "output", None)
    if output is None:
        raise RuntimeError(f"dashscope VL 响应缺少 output 字段：{response}")
    choices = getattr(output, "choices", None) or []
    if not choices:
        raise RuntimeError(f"dashscope VL 响应 choices 为空：{output}")
    message = choices[0].get("message") if isinstance(choices[0], dict) else getattr(choices[0], "message", None)
    if message is None:
        raise RuntimeError(f"dashscope VL 响应缺少 message：{choices[0]}")
    content = message.get("content") if isinstance(message, dict) else getattr(message, "content", None)
    if content is None:
        raise RuntimeError(f"dashscope VL 响应缺少 content：{message}")
    # 多模态 content 必然是 list[{"text": "..."}]
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                parts.append(item["text"])
            elif isinstance(item, str):
                parts.append(item)
        return "".join(parts)
    return str(content)


async def call_qwen3(prompt: str, system: str | None = None) -> str:
    """调用 Qwen3 文本模型进行推理，返回 assistant 回复文本。

    Args:
        prompt: 用户输入提示词。
        system: 可选 system prompt，用于约束模型角色/风格。

    Returns:
        模型回复的文本内容。

    Raises:
        ValueError: DASHSCOPE_API_KEY 未配置。
        RuntimeError: dashscope 调用失败（含原始错误信息）。
    """
    _ensure_api_key()

    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    def _sync_call() -> Any:
        # dashscope SDK 默认同步调用，返回 Response 对象
        return dashscope.Generation.call(
            model=settings.QWEN3_MODEL,
            messages=messages,
            result_format="message",
        )

    try:
        response = await asyncio.to_thread(_sync_call)
    except Exception as exc:
        raise RuntimeError(f"dashscope Generation 调用异常：{exc}") from exc

    # dashscope 通过 status_code 标识成功（200）与失败
    status_code = getattr(response, "status_code", None)
    if status_code != 200:
        raise RuntimeError(
            f"dashscope Generation 调用失败 status={status_code} "
            f"code={getattr(response, 'code', None)} "
            f"message={getattr(response, 'message', None)}"
        )

    return _extract_text(response)


async def call_qwen_vl(image_url: str, prompt: str) -> str:
    """调用 Qwen-VL 多模态模型，对图片+提示词进行识别，返回模型回复文本。

    Args:
        image_url: 图片可访问 URL（公网或 OSS 地址）。
        prompt: 针对图片的提问/指令。

    Returns:
        模型回复的文本内容。

    Raises:
        ValueError: DASHSCOPE_API_KEY 未配置。
        RuntimeError: dashscope 调用失败（含原始错误信息）。
    """
    _ensure_api_key()

    # 多模态消息格式：content 是 list，元素含 image / text 键
    messages = [
        {
            "role": "user",
            "content": [
                {"image": image_url},
                {"text": prompt},
            ],
        }
    ]

    def _sync_call() -> Any:
        return dashscope.MultiModalConversation.call(
            model=settings.QWEN_VL_MODEL,
            messages=messages,
        )

    try:
        response = await asyncio.to_thread(_sync_call)
    except Exception as exc:
        raise RuntimeError(f"dashscope MultiModalConversation 调用异常：{exc}") from exc

    status_code = getattr(response, "status_code", None)
    if status_code != 200:
        raise RuntimeError(
            f"dashscope MultiModalConversation 调用失败 status={status_code} "
            f"code={getattr(response, 'code', None)} "
            f"message={getattr(response, 'message', None)}"
        )

    return _extract_vl_text(response)
