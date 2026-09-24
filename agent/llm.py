"""Agent LLM 客户端(OpenAI 兼容 ``/chat/completions``,标准库实现)。

与 :class:`skill_normalization.llm.LLMVerifier` 同一模式:零额外依赖、
配置复用 :mod:`skillbridge.config`(``OPENAI_API_KEY`` /
``OPENAI_BASE_URL`` / ``LLM_MODEL``),未配置时 ``available`` 为
``False``,Agent 自动降级规则模式(不阻塞、不报错)。

在纯文本对话之外支持 **Tool Calling**:``chat(messages, tools=...)``
透传 OpenAI function calling 的 ``tools`` 参数,返回
:class:`LLMResponse`(``content`` + 解析好的 ``tool_calls``),
供「规划工具调用」节点使用。
"""

from __future__ import annotations

import json
import logging
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Sequence

from skillbridge.config import Settings, get_settings

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_TIMEOUT_SECONDS = 60.0


class LLMError(RuntimeError):
    """LLM 调用失败(网络 / 鉴权 / 响应异常)。调用方捕获后降级规则模式。"""


@dataclass(frozen=True)
class ToolCall:
    """一次工具调用请求:LLM 规划出的工具名 + 参数。"""

    id: str
    name: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMResponse:
    """LLM 一次回复:文本内容 + 工具调用请求(可同时存在)。"""

    content: str = ""
    tool_calls: tuple[ToolCall, ...] = ()


class LLMClient:
    """OpenAI 兼容 Chat Completions 客户端(urllib,支持 tool calling)。

    :param api_key: API key,缺省读 ``OPENAI_API_KEY``;
    :param base_url: 接口地址,缺省读 ``OPENAI_BASE_URL``;
    :param model: 模型名,缺省读 ``LLM_MODEL``;
    :param enabled: 总开关(测试可强制关闭模拟未配置);
    :param timeout: 单次请求超时秒数(超时抛 :class:`LLMError`)。

    ``available`` 为 ``False`` 时(未配置 key / 模型或开关关闭),
    Agent 直接走规则模式;运行期调用失败抛 :class:`LLMError`,
    由状态机节点捕获并降级,保证主流程不中断。
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        *,
        enabled: bool = True,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        settings: Settings | None = None,
    ):
        if settings is None:
            settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.openai_api_key
        self.base_url = (
            base_url if base_url is not None else settings.openai_base_url
        ) or DEFAULT_BASE_URL
        self.model = model if model is not None else settings.llm_model
        self.enabled = enabled
        self.timeout = timeout

    @property
    def available(self) -> bool:
        """开关开启且配置了 API key 与模型时才可用。"""
        return bool(self.enabled and self.api_key and self.model)

    # --- 对外接口 ---
    def chat(
        self,
        messages: Sequence[dict[str, Any]],
        *,
        tools: Sequence[dict[str, Any]] | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        """一次对话调用,返回文本内容与工具调用请求。

        :param messages: OpenAI 消息列表(system / user / assistant / tool)。
        :param tools: OpenAI function calling 的 ``tools`` schema 列表。
        :raises LLMError: 网络 / 鉴权 / 响应格式异常(调用方降级)。
        """
        if not self.available:
            raise LLMError("LLM 不可用:未配置 OPENAI_API_KEY / LLM_MODEL")
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": list(messages),
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = list(tools)
            payload["tool_choice"] = "auto"
        body = self._request(payload)
        return self._parse(body)

    # --- 内部实现(测试可子类重写) ---
    def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url=self.base_url.rstrip("/") + "/chat/completions",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except LLMError:
            raise
        except Exception as exc:  # 网络 / HTTP / JSON 异常统一转 LLMError
            raise LLMError(f"LLM 调用失败: {exc}") from exc

    def _parse(self, body: dict[str, Any]) -> LLMResponse:
        try:
            message = body["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"LLM 响应缺少 choices/message: {body!r:.200}") from exc
        content = message.get("content") or ""
        calls: list[ToolCall] = []
        for item in message.get("tool_calls") or ():
            name = item.get("function", {}).get("name", "")
            raw_args = item.get("function", {}).get("arguments", "{}")
            try:
                args = json.loads(raw_args) if raw_args else {}
            except json.JSONDecodeError:
                logger.warning("工具调用参数不是合法 JSON:%s", raw_args)
                args = {}
            if isinstance(args, dict) and name:
                calls.append(
                    ToolCall(id=item.get("id", ""), name=name, args=args)
                )
        return LLMResponse(content=content, tool_calls=tuple(calls))
