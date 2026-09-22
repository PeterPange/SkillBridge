"""LLM 语义校验(可选开关,大纲第三节流程的最后一级)。

对 Embedding 产生的候选做最终语义确认,处理别名表未覆盖、
相似度不足以定案的输入(如「深度学习」与「机器学习」这类相关但不同的技能)。

- 使用 OpenAI 兼容 ``/chat/completions`` 接口,标准库 ``urllib`` 实现,零额外依赖;
- 未配置 API key / 模型,或开关关闭(``enabled=False``)时自动跳过,
  主流程回退 Embedding 结果(无 API key 不阻塞);
- API 调用失败或输出无法解析时同样回退,不抛出异常。
"""

from __future__ import annotations

import json
import logging
import re
import urllib.request
from dataclasses import dataclass
from typing import Sequence

from skill_normalization.models import Candidate

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_TIMEOUT_SECONDS = 20.0

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)
_NULLISH = ("", "null", "none")


@dataclass(frozen=True)
class LLMVerdict:
    """LLM 校验结论:skill_id 为 None 表示 LLM 否定了全部候选。"""

    skill_id: str | None
    skill_name: str | None
    confidence: float
    reason: str


class LLMVerifier:
    """LLM 语义校验器(OpenAI 兼容接口)。

    参数可显式传入,缺省时从 ``skillbridge.config.Settings`` 读取
    (OPENAI_API_KEY / OPENAI_BASE_URL / LLM_MODEL)。
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        *,
        enabled: bool = True,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        settings=None,
    ):
        if settings is None:
            from skillbridge.config import get_settings

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
        """开关开启且配置了 API key 与模型时才可用;否则调用方自动跳过。"""
        return bool(self.enabled and self.api_key and self.model)

    # --- 对外接口 ---
    def verify(self, raw_text: str, candidates: Sequence[Candidate]) -> LLMVerdict | None:
        """校验输入技能名与候选的语义一致性。

        返回 None 表示校验不可用或失败(调用方回退 Embedding 结果);
        返回 ``LLMVerdict(skill_id=None, ...)`` 表示 LLM 明确否定全部候选。
        """
        if not self.available or not candidates:
            return None
        try:
            content = self._chat(self._build_messages(raw_text, candidates))
            return self._parse_verdict(content, candidates)
        except Exception:
            logger.warning("LLM 语义校验失败,回退 Embedding 结果", exc_info=True)
            return None

    # --- 内部实现(测试可 monkeypatch) ---
    def _build_messages(self, raw_text: str, candidates: Sequence[Candidate]) -> list[dict]:
        lines = []
        for i, cand in enumerate(candidates, 1):
            aliases = "、".join(cand.skill.labels[1:6]) or "-"
            lines.append(
                f"{i}. {cand.skill.skill_id} | {cand.skill.name} | "
                f"别名/同义词: {aliases} | 相似度: {cand.score:.3f}"
            )
        system = (
            "你是企业培训系统的技能名称归一化助手。"
            "判断输入的外部技能名称与哪个候选标准技能是同一项能力"
            "(同义、缩写、同一技术栈的同一能力)。只输出 JSON,不要输出其他内容。"
        )
        user = (
            f"输入技能名称:{raw_text}\n\n"
            f"候选标准技能(按相似度降序):\n" + "\n".join(lines) + "\n\n"
            "规则:\n"
            "- 语义相同或为同一能力的不同说法 → 选择对应 skill_id;\n"
            "- 仅为相关但不是同一能力(如「深度学习」与「生成式AI」)→ skill_id 为 null;\n"
            "- confidence 为 0 到 1 的小数。\n\n"
            '输出 JSON:{"skill_id": "SKILL_XXX 或 null", "confidence": 0.0, "reason": "简短理由"}'
        )
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    def _chat(self, messages: list[dict]) -> str:
        payload = json.dumps(
            {"model": self.model, "messages": messages, "temperature": 0.0}
        ).encode("utf-8")
        request = urllib.request.Request(
            url=self.base_url.rstrip("/") + "/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
        return body["choices"][0]["message"]["content"]

    def _parse_verdict(
        self, content: str, candidates: Sequence[Candidate]
    ) -> LLMVerdict | None:
        match = _JSON_RE.search(content)
        if match is None:
            logger.warning("LLM 输出中未找到 JSON:%.200s", content)
            return None
        try:
            data = json.loads(match.group())
        except json.JSONDecodeError:
            logger.warning("LLM 输出 JSON 解析失败:%.200s", content)
            return None
        if not isinstance(data, dict):
            return None

        skill_id = data.get("skill_id")
        if isinstance(skill_id, str):
            skill_id = skill_id.strip()
            if skill_id.lower() in _NULLISH:
                skill_id = None
        else:
            skill_id = None

        valid_ids = {cand.skill.skill_id for cand in candidates}
        if skill_id is not None and skill_id not in valid_ids:
            # 模型幻觉出的 skill_id 一律视为否定,但保留理由供审计
            logger.warning("LLM 返回了候选之外的 skill_id: %s", skill_id)
            skill_id = None

        try:
            confidence = min(max(float(data.get("confidence", 0.0)), 0.0), 1.0)
        except (TypeError, ValueError):
            confidence = 0.0
        reason = str(data.get("reason") or "")[:500]
        skill_name = next(
            (cand.skill.name for cand in candidates if cand.skill.skill_id == skill_id), None
        )
        return LLMVerdict(
            skill_id=skill_id, skill_name=skill_name, confidence=confidence, reason=reason
        )
