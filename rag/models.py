"""RAG 领域模型(大纲第九节)。

四类对象:

- **解析**::class:`Section` 标题小节(标题 + 层级 + 正文),
  :class:`ParsedDocument` 解析后的整篇文档(标题 + 来源 + 小节列表);
- **分块**::class:`Chunk` 标题级分块结果,携带完整溯源信息
  (文档标题 / 来源路径 / 标题路径 / 块序号),是入库与检索的最小单元;
- **检索**::class:`ScoredChunk` 带评分的命中块(向量分 + 词面分 + 综合分),
  :class:`SearchResult` 一次问答的完整结果(问题 + 命中块 + 引用上下文);
- **入库**::class:`IngestResult` 单篇文档入库摘要,
  :class:`DocumentRecord` 向量库中的文档登记项。

所有模型均可 ``to_dict()`` 回写为 JSON 可序列化对象,供 Agent 工具
(大纲第十节)与 CLI ``--json`` 输出消费。
"""

from __future__ import annotations

from dataclasses import dataclass

#: 标题路径的展示分隔符(如「第二章 入职培训 > 2.1 导师制度」)。
HEADING_SEPARATOR = " > "


@dataclass(frozen=True)
class Section:
    """文档中的一个小节:一个标题 + 该标题下的正文。

    :param heading: 小节标题;文档开头没有标题的导语部分为 ``None``;
    :param level: 标题层级(Markdown ``#`` 数 / Word 标题样式数字),
        导语固定为 0,正文标题从 1 开始;
    :param text: 小节正文(保留换行,空小节为空字符串)。
    """

    heading: str | None
    level: int
    text: str

    @property
    def is_preamble(self) -> bool:
        """是否为文档开头无标题的导语部分。"""
        return self.heading is None

    def to_dict(self) -> dict:
        return {"heading": self.heading, "level": self.level, "text": self.text}


@dataclass(frozen=True)
class ParsedDocument:
    """解析后的整篇文档。

    :param title: 文档标题(首个一级标题;缺失时回退文件名);
    :param source: 来源标识(通常为文件路径,用于引用溯源);
    :param sections: 按出现顺序排列的小节列表(含空小节,保留标题层级)。
    """

    title: str
    source: str
    sections: tuple[Section, ...]

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "source": self.source,
            "sections": [s.to_dict() for s in self.sections],
        }


@dataclass(frozen=True)
class Chunk:
    """标题级分块:入库与检索的最小单元,携带完整溯源信息。

    :param chunk_id: 全局唯一块标识(``{doc_id}:{序号}``);
    :param doc_id: 所属文档 ID(默认取文档标题;同 ID 重复入库为幂等替换);
    :param doc_title: 文档标题(引用展示用);
    :param source: 来源路径(引用展示用);
    :param heading_path: 从文档标题到本块的标题路径
        (如 ``("第二章 入职培训", "2.1 导师制度")``);
    :param chunk_index: 文档内块序号(从 0 开始,顺序即原文顺序);
    :param content: 块正文(段落以换行分隔,不含标题)。
    """

    chunk_id: str
    doc_id: str
    doc_title: str
    source: str
    heading_path: tuple[str, ...]
    chunk_index: int
    content: str

    @property
    def char_count(self) -> int:
        return len(self.content)

    @property
    def heading_display(self) -> str:
        """标题路径的单行展示(如「第二章 入职培训 > 2.1 导师制度」)。"""
        return HEADING_SEPARATOR.join(self.heading_path)

    @property
    def citation(self) -> str:
        """来源引用的标题部分:``《文档标题》 标题路径``。"""
        text = f"《{self.doc_title}》"
        if self.heading_display:
            text += f" {self.heading_display}"
        return text

    def embed_text(self) -> str:
        """送入 Embedding 模型的文本:文档标题 + 标题路径 + 正文。

        标题上下文能显著提升「问标题答正文」类自然语言提问的召回质量。
        """
        parts = [self.doc_title]
        if self.heading_display:
            parts.append(self.heading_display)
        parts.append(self.content)
        return "\n".join(parts)

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "doc_title": self.doc_title,
            "source": self.source,
            "heading_path": list(self.heading_path),
            "chunk_index": self.chunk_index,
            "content": self.content,
            "char_count": self.char_count,
            "citation": self.citation,
        }


@dataclass(frozen=True)
class ScoredChunk:
    """带评分的检索命中块。

    :param chunk: 命中的分块;
    :param vector_score: 向量余弦相似度(召回阶段得分,0-1);
    :param lexical_score: 查询词覆盖率(重排阶段词面得分,0-1);
    :param score: 重排后的综合得分(未重排时等于向量分)。
    """

    chunk: Chunk
    vector_score: float
    lexical_score: float = 0.0
    score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "chunk": self.chunk.to_dict(),
            "vector_score": round(self.vector_score, 6),
            "lexical_score": round(self.lexical_score, 6),
            "score": round(self.score, 6),
        }


@dataclass(frozen=True)
class IngestResult:
    """单篇文档入库摘要。

    :param backend: 实际使用的 Embedding 后端描述(如
        ``sentence-transformers:paraphrase-multilingual-MiniLM-L12-v2``
        / ``lexical``);
    :param dim: 本批向量的维度(向量库表结构按此创建)。
    """

    doc_id: str
    title: str
    source: str
    chunk_count: int
    dim: int
    backend: str

    def to_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "title": self.title,
            "source": self.source,
            "chunk_count": self.chunk_count,
            "dim": self.dim,
            "backend": self.backend,
        }


@dataclass(frozen=True)
class DocumentRecord:
    """向量库中的文档登记项(``list_documents`` 的返回行)。"""

    doc_id: str
    title: str
    source: str
    chunk_count: int

    def to_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "title": self.title,
            "source": self.source,
            "chunk_count": self.chunk_count,
        }


@dataclass(frozen=True)
class SearchResult:
    """一次知识库问答的完整检索结果。

    :param query: 用户的自然语言问题;
    :param chunks: 重排后的命中块(按综合分降序,至多 ``top_k`` 个);
    :param context: 带来源引用的上下文文本,直接拼入 LLM 提示词即可
        (见 :func:`rag.pipeline.format_context`)。
    """

    query: str
    chunks: tuple[ScoredChunk, ...]
    context: str

    @property
    def has_hits(self) -> bool:
        return bool(self.chunks)

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "chunks": [sc.to_dict() for sc in self.chunks],
            "context": self.context,
        }
