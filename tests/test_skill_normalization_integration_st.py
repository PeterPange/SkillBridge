"""sentence-transformers 真实模型集成测试(可选,需网络下载模型,约 470MB)。

验证别名表未覆盖的跨语言表述能通过本地多语言 Embedding 归一到正确技能。

跳过条件(任一):
- sentence-transformers 未安装;
- 本地 Embedding 模型无法加载(网络不可达且未缓存);
- 环境变量 SKILL_SN_SKIP_ST=1(CI / 离线环境)。

网络说明:
- huggingface.co 不可达时,可用国内镜像:``HF_ENDPOINT=https://hf-mirror.com``;
- 模型已缓存时,可设 ``HF_HUB_OFFLINE=1`` 跳过在线校验,加快加载。
"""

import os

import pytest

if os.getenv("SKILL_SN_SKIP_ST") == "1":
    pytest.skip("SKILL_SN_SKIP_ST=1 跳过真实模型测试", allow_module_level=True)


def _load_encoder_or_none():
    """探测 sentence-transformers 可用性:导入 + 实际加载默认模型。

    模型加载失败(网络不可达且未缓存)时返回 None,整个模块跳过,
    避免误用词面降级后端跑出与真实模型不符的结论。
    """
    try:
        from skill_normalization.matcher import (
            SentenceTransformerEncoder,
            _import_sentence_transformers,
        )

        _import_sentence_transformers()  # ImportError → 未安装
        encoder = SentenceTransformerEncoder()
        encoder._load()  # 显式加载,失败(网络/缓存)→ 跳过
        return encoder
    except Exception:
        return None


_ENCODER = _load_encoder_or_none()

if _ENCODER is None:
    pytest.skip(
        "sentence-transformers 或本地 Embedding 模型不可用(未安装/网络不可达且未缓存)",
        allow_module_level=True,
    )

from skill_normalization.llm import LLMVerifier  # noqa: E402
from skill_normalization.normalizer import SkillNormalizer  # noqa: E402


@pytest.fixture(scope="module")
def st_normalizer() -> SkillNormalizer:
    """整个模块只加载一次模型。"""
    return SkillNormalizer(encoder=_ENCODER, llm_verifier=LLMVerifier(enabled=False))


@pytest.mark.parametrize(
    ("raw", "skill_id"),
    [
        # 别名表未覆盖、依赖跨语言语义相似度的输入
        ("生成式人工智能应用", "SKILL_004"),
        ("人工智能生成内容", "SKILL_004"),   # AIGC 的中文全称
        ("大模型应用开发", "SKILL_004"),
        ("深度学习", "SKILL_003"),
        ("容器编排平台", "SKILL_007"),
        ("智能体应用开发", "SKILL_006"),
    ],
)
def test_cross_lingual_semantic_match(st_normalizer, raw, skill_id):
    mapping = st_normalizer.normalize(raw)
    assert mapping.skill_id == skill_id, f"{raw!r} → {mapping.skill_id}(候选: {mapping.candidates})"


def test_javascript_not_matched_by_real_model(st_normalizer):
    """真实模型下 javascript 也不应误映射到 Java。"""
    mapping = st_normalizer.normalize("javascript")
    assert mapping.skill_id != "SKILL_002"
