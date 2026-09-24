"""重排:对向量召回的候选块做二次排序(大纲第九节 Retriever → Reranker)。

向量召回擅长语义泛化(「多久」≈「多长时间」),但对问题中
**具体业务词**的命中不敏感(「报销」「导师制」这类关键词可能被
语义相近但答非所问的段落压过)。重排阶段用查询词覆盖率修正排序:

.. code-block:: text

    综合分 = vector_weight × 向量相似度 + (1 - vector_weight) × 查询词覆盖率

- :class:`Reranker` 协议抽象「(问题, 候选块) → 排序结果」,
  后续可替换为 cross-encoder 或 LLM 重排而不影响管线;
- :class:`LexicalReranker` 默认实现:零外部依赖、确定性,
  词元化 = 西文/数字词 + CJK 二元组,覆盖率为命中的查询词元占比
  (在标题路径 + 正文上匹配——标题命中同样计分)。
"""

from __future__ import annotations

import re
from typing import Protocol, Sequence

from rag.models import ScoredChunk

#: 向量分在综合分中的权重(其余为词面覆盖分)。
DEFAULT_VECTOR_WEIGHT = 0.6

_WORD_RE = re.compile(r"[a-zA-Z0-9]+")
_CJK_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")


class Reranker(Protocol):
    """重排器协议:对召回候选按与问题的相关度重新排序。"""

    def rerank(self, query: str, chunks: Sequence[ScoredChunk]) -> list[ScoredChunk]:
        """返回重排后的候选列表(新对象,不修改入参)。"""
        ...


def tokenize(text: str) -> set[str]:
    """文本 → 词元集合:小写西文/数字词 + CJK 相邻二元组。

    中文没有空格分词,二元组是零依赖下最稳的词面匹配单元
    (「导师制」「导师」共享「导师」二元组)。
    """
    tokens = set(_WORD_RE.findall(text.lower()))
    cjk_chars = "".join(_CJK_CHAR_RE.findall(text))
    tokens.update(cjk_chars[i : i + 2] for i in range(len(cjk_chars) - 1))
    return tokens


class LexicalReranker:
    """词面重排:向量相似度 × 查询词覆盖率线性融合。

    :param vector_weight: 向量分权重(0-1);越大越信任语义召回,
        越小越强调问题关键词的精确命中。
    """

    def __init__(self, *, vector_weight: float = DEFAULT_VECTOR_WEIGHT):
        if not 0.0 <= vector_weight <= 1.0:
            raise ValueError(f"vector_weight 须在 [0, 1],收到 {vector_weight}")
        self.vector_weight = vector_weight

    def rerank(self, query: str, chunks: Sequence[ScoredChunk]) -> list[ScoredChunk]:
        """融合向量分与词面覆盖分,返回降序新列表。

        并列时按向量分、块 ID 稳定排序,保证结果确定。
        """
        query_tokens = tokenize(query)
        reranked = []
        for scored in chunks:
            lexical = self._coverage(query_tokens, scored)
            reranked.append(
                ScoredChunk(
                    chunk=scored.chunk,
                    vector_score=scored.vector_score,
                    lexical_score=lexical,
                    score=(
                        self.vector_weight * scored.vector_score
                        + (1.0 - self.vector_weight) * lexical
                    ),
                )
            )
        reranked.sort(
            key=lambda sc: (-sc.score, -sc.vector_score, sc.chunk.chunk_id)
        )
        return reranked

    # --- 内部 ---
    def coverage(self, query: str, chunk: ScoredChunk) -> float:
        """查询词元在块(标题路径 + 正文)中的覆盖率,0-1。"""
        return self._coverage(tokenize(query), chunk)

    def _coverage(self, query_tokens: set[str], scored: ScoredChunk) -> float:
        if not query_tokens:
            return 0.0
        chunk_tokens = tokenize(scored.chunk.embed_text())
        return len(query_tokens & chunk_tokens) / len(query_tokens)


__all__ = [
    "DEFAULT_VECTOR_WEIGHT",
    "LexicalReranker",
    "Reranker",
    "tokenize",
]
