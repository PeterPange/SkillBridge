"""候选标准技能匹配:Embedding 相似度(sentence-transformers 本地模型)。

设计要点:
- ``TextEncoder`` 协议抽象「文本 → 向量」,便于测试注入与后端替换;
- ``SentenceTransformerEncoder`` 懒加载本地多语言模型(首次编码时加载);
- sentence-transformers 未安装、模型加载失败或网络不可用时,
  ``EmbeddingMatcher`` 自动降级为 ``LexicalEncoder``(字符 n-gram 词面匹配),
  保证离线环境主流程仍可运行(跨语言输入此时依赖别名表);
- 环境变量 ``SKILL_NORMALIZATION_BACKEND=lexical`` 可强制使用词面后端
  (CI / 无网络环境),``SKILL_NORMALIZATION_EMBEDDING_MODEL`` 可替换本地模型。
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
from typing import Protocol, Sequence

from skill_normalization.library import SkillLibrary
from skill_normalization.models import Candidate, Skill
from skill_normalization.text import normalize_text

logger = logging.getLogger(__name__)

DEFAULT_EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
ENV_BACKEND = "SKILL_NORMALIZATION_BACKEND"
ENV_EMBEDDING_MODEL = "SKILL_NORMALIZATION_EMBEDDING_MODEL"

Vector = list[float]


class TextEncoder(Protocol):
    """文本 → 向量编码器接口(sentence-transformers / 词面 / 测试桩)。"""

    def encode(self, texts: Sequence[str]) -> list[Vector]:
        """把一批文本编码为等长向量。"""
        ...


class SentenceTransformerEncoder:
    """sentence-transformers 本地模型编码器(懒加载)。

    模型加载或编码失败时向上抛出异常,由 ``EmbeddingMatcher`` 决定降级。
    """

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or os.getenv(ENV_EMBEDDING_MODEL, DEFAULT_EMBEDDING_MODEL)
        self._model = None

    def _load(self):
        if self._model is None:
            SentenceTransformer = _import_sentence_transformers()
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def encode(self, texts: Sequence[str]) -> list[Vector]:
        model = self._load()
        embeddings = model.encode(
            list(texts), normalize_embeddings=True, show_progress_bar=False
        )
        return [[float(x) for x in vec] for vec in embeddings]


class LexicalEncoder:
    """词面编码器(离线降级方案,零外部依赖)。

    将文本的整词(权重 2.0)与字符 2/3-gram(权重 1.0)哈希到固定维
    符号向量并 L2 归一化,余弦相似度即词面重合度。跨语言(中↔英)词面
    无重叠、得分为 0,这类输入依赖别名表或 LLM 校验。
    """

    def __init__(self, dim: int = 512):
        self.dim = dim

    def _add(self, vec: Vector, token: str, weight: float) -> None:
        digest = hashlib.md5(token.encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:4], "big") % self.dim
        sign = 1.0 if digest[4] & 1 else -1.0
        vec[bucket] += weight * sign

    def _vector(self, text: str) -> Vector:
        vec = [0.0] * self.dim
        for word in text.lower().split():
            self._add(vec, word, 2.0)
            for n in (2, 3):
                for i in range(len(word) - n + 1):
                    self._add(vec, word[i : i + n], 1.0)
        norm = math.sqrt(sum(x * x for x in vec))
        if norm:
            vec = [x / norm for x in vec]
        return vec

    def encode(self, texts: Sequence[str]) -> list[Vector]:
        return [self._vector(t) for t in texts]


def _import_sentence_transformers():
    """导入 sentence-transformers,免疫仓库 ``profile/`` 包与标准库的双向遮蔽。

    遮蔽是双向的,任一方向都会炸:

    - 本地 ``profile`` 先入 ``sys.modules`` → torch 导入链拿到本地包,
      ``profile`` 不是标准库模块 → ImportError → Embedding 降级词面编码;
    - 标准库 ``profile`` 先入(torch 导入时)→ 业务代码
      ``from profile.models import ...`` 拿到标准库单模块 → 不是包 →
      ModuleNotFoundError。

    解法:导入前保存并弹出当前 ``profile`` 缓存项,导入完成后弹出
    torch 装入的标准库项,再恢复原项。两个方向的既有引用都不受影响
    (torch 持有标准库引用,业务代码持有本地包引用)。
    """
    import sys
    from pathlib import Path

    saved_profile = sys.modules.get("profile")
    sys.modules.pop("profile", None)

    project_root = Path(__file__).resolve().parent.parent
    dropped: list[str] = []
    for entry in list(sys.path):
        resolved = None
        if entry:
            try:
                resolved = Path(entry).resolve()
            except OSError:
                resolved = None
        else:
            # 空串代表 cwd(python -m 时的 sys.path[0])
            resolved = Path.cwd().resolve()
        if resolved == project_root:
            dropped.append(entry)
    for entry in dropped:
        sys.path.remove(entry)
    try:
        from sentence_transformers import SentenceTransformer
    finally:
        for entry in reversed(dropped):
            sys.path.insert(0, entry)
        # torch 导入链装入的标准库 profile 让位:恢复调用方原有的缓存项
        sys.modules.pop("profile", None)
        if saved_profile is not None:
            sys.modules["profile"] = saved_profile
    return SentenceTransformer


def default_encoder(model_name: str | None = None) -> TextEncoder:
    """按环境选择默认编码器:lexical 强制词面;否则优先 sentence-transformers。"""
    backend = (os.getenv(ENV_BACKEND) or "").strip().lower() or "auto"
    if backend == "lexical":
        return LexicalEncoder()
    if backend not in ("auto", "sentence-transformers", "sentence_transformers", "st"):
        raise ValueError(f"未知的 {ENV_BACKEND} 取值: {backend!r}(可选 auto / lexical)")
    try:
        _import_sentence_transformers()
    except ImportError:
        logger.info("sentence-transformers 未安装,Embedding 使用词面匹配(降级模式)")
        return LexicalEncoder()
    return SentenceTransformerEncoder(model_name)


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """余弦相似度(零向量返回 0)。"""
    if len(a) != len(b):
        raise ValueError(f"向量维度不一致: {len(a)} != {len(b)}")
    dot = na = nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / math.sqrt(na * nb)


class EmbeddingMatcher:
    """基于向量余弦相似度的候选标准技能匹配。

    为技能库每个技能的全部称谓建立向量索引;查询文本与技能的相似度
    取其各称谓向量的最大值。索引按 (library, encoder) 缓存;编码器
    运行期降级时会自动重建索引保持一致。
    """

    def __init__(self, encoder: TextEncoder | None = None):
        self.encoder: TextEncoder = encoder if encoder is not None else default_encoder()
        self._entries: list[tuple[Skill, Vector]] = []
        self._indexed_library: SkillLibrary | None = None
        self._index_encoder: TextEncoder | None = None

    @property
    def backend(self) -> str:
        """当前实际使用的编码后端描述(用于日志与映射表元数据)。"""
        if isinstance(self.encoder, SentenceTransformerEncoder):
            return f"sentence-transformers:{self.encoder.model_name}"
        if isinstance(self.encoder, LexicalEncoder):
            return "lexical"
        return type(self.encoder).__name__

    # --- 编码(带一次性降级) ---
    def _encode(self, texts: Sequence[str]) -> list[Vector]:
        try:
            return self.encoder.encode(list(texts))
        except Exception:
            if isinstance(self.encoder, SentenceTransformerEncoder):
                logger.warning(
                    "sentence-transformers 模型加载/编码失败,降级为词面匹配(本次会话内生效)",
                    exc_info=True,
                )
                self.encoder = LexicalEncoder()
                self._indexed_library = None
                self._index_encoder = None
                return self.encoder.encode(list(texts))
            raise

    def _build_index(self, library: SkillLibrary) -> None:
        entries: list[tuple[Skill, str]] = []
        for skill in library:
            for label in skill.labels:
                normalized = normalize_text(label)
                if normalized:
                    entries.append((skill, normalized))
        vectors = self._encode([text for _, text in entries])
        self._entries = list(zip([skill for skill, _ in entries], vectors))
        self._indexed_library = library
        self._index_encoder = self.encoder

    def match(
        self,
        text: str,
        library: SkillLibrary,
        *,
        top_k: int = 3,
        threshold: float = 0.6,
    ) -> list[Candidate]:
        """返回按相似度降序、且得分 ≥ threshold 的前 top_k 个候选。"""
        normalized = normalize_text(text)
        if not normalized:
            return []
        if self._indexed_library is not library or self._index_encoder is not self.encoder:
            self._build_index(library)
        query_vec = self._encode([normalized])[0]
        if self._index_encoder is not self.encoder:
            # 查询编码时发生降级 → 用新编码器重建索引,保证向量空间一致
            self._build_index(library)

        best: dict[str, tuple[float, Skill]] = {}
        for skill, vec in self._entries:
            score = cosine_similarity(query_vec, vec)
            current = best.get(skill.skill_id)
            if current is None or score > current[0]:
                best[skill.skill_id] = (score, skill)
        ranked = sorted(best.values(), key=lambda item: item[0], reverse=True)
        return [
            Candidate(skill=skill, score=round(score, 6))
            for score, skill in ranked
            if score >= threshold
        ][:top_k]
