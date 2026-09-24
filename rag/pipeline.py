"""RAG 管线:解析 → 分块 → Embedding → 入库 / 检索 → 重排 → 引用上下文。

大纲第九节「企业知识库 RAG」的组装层::

    PDF / Word / Markdown          自然语言提问
          ↓ parse_document              ↓ encode
    标题级分块 chunk_document    查询向量
          ↓ encode(批量)            ↓ VectorStore.search(余弦 Top-K)
    分块向量                          候选块(向量分)
          ↓ VectorStore.upsert         ↓ Reranker.rerank(词面覆盖修正)
    pgvector / 内存存储          Top-K 命中块
                                       ↓ format_context
                                 带来源引用的上下文(拼入 LLM 提示词)

Embedding 后端**复用 skill_normalization**(阶段 1B):
:data:`skill_normalization.default_encoder` 按环境选择
sentence-transformers 本地模型或词面编码器,
``SKILL_NORMALIZATION_BACKEND=lexical`` 同样对本模块生效
(CI / 无网络环境强制离线)。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Sequence

from rag.chunker import DEFAULT_MAX_CHARS, chunk_document
from rag.models import (
    Chunk,
    IngestResult,
    ParsedDocument,
    ScoredChunk,
    SearchResult,
)
from rag.reader import SUPPORTED_SUFFIXES, parse_document
from rag.rerank import LexicalReranker, Reranker
from rag.store import MemoryVectorStore, PgvectorStore, VectorStore
from skill_normalization import (
    LexicalEncoder,
    SentenceTransformerEncoder,
    TextEncoder,
    default_encoder,
)

logger = logging.getLogger(__name__)

#: 默认返回的引用块数。
DEFAULT_TOP_K = 4
#: 重排候选池相对 top_k 的放大倍数(召回宽一点,交给重排精选)。
CANDIDATE_FACTOR = 3


def format_context(query: str, chunks: Sequence[ScoredChunk]) -> str:
    """把命中块渲染为带来源引用的上下文文本(直接拼入 LLM 提示词)。

    格式::

        基于知识库检索到的相关内容(按相关度降序):

        [1] 《企业员工培训管理制度》第二章 入职培训 > 2.1 导师制度
            来源: data/fixtures/training_policy.md | 相关度 0.82(向量 0.79 / 词面 0.86)
            新员工入职后,由部门负责人指定一名资深员工作为导师……

        无命中时返回「未检索到相关内容」提示,LLM 可据此拒答。
    """
    if not chunks:
        return "知识库中未检索到与问题相关的内容。"
    lines = ["基于知识库检索到的相关内容(按相关度降序):", ""]
    for i, scored in enumerate(chunks, 1):
        chunk = scored.chunk
        lines.append(f"[{i}] {chunk.citation}")
        lines.append(
            f"    来源: {chunk.source} | "
            f"相关度 {scored.score:.2f}"
            f"(向量 {scored.vector_score:.2f} / 词面 {scored.lexical_score:.2f})"
        )
        lines.append(chunk.content)
        lines.append("")
    return "\n".join(lines).rstrip()


class RagPipeline:
    """企业知识库 RAG 管线(入库 + 检索问答)。

    :param encoder: 文本 → 向量编码器,缺省复用 skill_normalization 的
        默认后端(sentence-transformers,不可用时自动降级词面);
    :param store: 向量存储,缺省 pgvector(PostgreSQL);
    :param reranker: 重排器,缺省词面重排;
    :param max_chars: 标题级分块的单块最大字符数;
    :param top_k: 问答默认返回的引用块数。

    用法::

        pipeline = RagPipeline(store=MemoryVectorStore())
        pipeline.ingest_file("data/fixtures/training_policy.md")
        result = pipeline.query("新员工入职培训期是多久?")
        print(result.context)   # 带来源引用的上下文
    """

    def __init__(
        self,
        encoder: TextEncoder | None = None,
        store: VectorStore | None = None,
        reranker: Reranker | None = None,
        *,
        max_chars: int = DEFAULT_MAX_CHARS,
        top_k: int = DEFAULT_TOP_K,
    ):
        self.encoder: TextEncoder = encoder if encoder is not None else default_encoder()
        self.store: VectorStore = store if store is not None else PgvectorStore()
        self.reranker: Reranker = reranker if reranker is not None else LexicalReranker()
        self.max_chars = max_chars
        self.top_k = top_k

    @property
    def backend(self) -> str:
        """当前实际使用的 Embedding 后端描述(入库摘要 / 日志用)。"""
        if isinstance(self.encoder, SentenceTransformerEncoder):
            return f"sentence-transformers:{self.encoder.model_name}"
        if isinstance(self.encoder, LexicalEncoder):
            return "lexical"
        return type(self.encoder).__name__

    # ------------------------------------------------------------------
    # 入库:解析 → 分块 → 编码 → 存储
    # ------------------------------------------------------------------
    def ingest_file(self, path: str | Path, *, doc_id: str | None = None) -> IngestResult:
        """解析并入库单个文档(同 doc_id 重复入库为幂等替换)。"""
        doc = parse_document(path)
        return self.ingest_document(doc, doc_id=doc_id)

    def ingest_dir(
        self, directory: str | Path, *, doc_id_prefix: str | None = None
    ) -> list[IngestResult]:
        """入库目录下全部受支持的文档(按文件名排序,逐个幂等替换)。

        :param doc_id_prefix: 文档 ID 前缀,避免不同目录同名文件互相覆盖。
        """
        root = Path(directory)
        if not root.is_dir():
            raise FileNotFoundError(f"目录不存在: {root}")
        results = []
        for path in sorted(root.iterdir()):
            if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES:
                doc_id = f"{doc_id_prefix}{path.stem}" if doc_id_prefix else None
                results.append(self.ingest_file(path, doc_id=doc_id))
        return results

    def ingest_document(
        self, doc: ParsedDocument, *, doc_id: str | None = None
    ) -> IngestResult:
        """入库一个已解析的文档:分块 → 批量编码 → 整批写入。"""
        chunks = chunk_document(doc, doc_id=doc_id, max_chars=self.max_chars)
        if not chunks:
            raise ValueError(f"文档没有可分块的内容: {doc.source}")
        return self._store_chunks(doc, chunks)

    def _encode(self, texts: list[str]) -> list[list[float]]:
        """批量编码,带一次性降级(与 EmbeddingMatcher 同策略)。

        sentence-transformers 模型加载/编码失败(未安装、无网络、
        无缓存)时,本次会话内退化为词面编码器,主流程仍可用;
        其他编码器(含测试桩)的异常原样抛出。
        """
        try:
            return self.encoder.encode(texts)
        except Exception:
            if isinstance(self.encoder, SentenceTransformerEncoder):
                logger.warning(
                    "sentence-transformers 模型加载/编码失败,"
                    "RAG 降级为词面匹配(本次会话内生效)",
                    exc_info=True,
                )
                self.encoder = LexicalEncoder()
                return self.encoder.encode(texts)
            raise

    def _store_chunks(self, doc: ParsedDocument, chunks: list[Chunk]) -> IngestResult:
        embeddings = self._encode([chunk.embed_text() for chunk in chunks])
        dim = len(embeddings[0])
        self.store.setup(dim)
        count = self.store.upsert_chunks(chunks, embeddings)
        logger.info(
            "RAG 入库: %s → %d 块(维度 %d,后端 %s)",
            doc.title, count, dim, self.backend,
        )
        return IngestResult(
            doc_id=chunks[0].doc_id,
            title=doc.title,
            source=doc.source,
            chunk_count=count,
            dim=dim,
            backend=self.backend,
        )

    # ------------------------------------------------------------------
    # 检索:编码 → 召回 → 重排 → 引用上下文
    # ------------------------------------------------------------------
    def query(self, question: str, *, top_k: int | None = None) -> SearchResult:
        """自然语言提问 → 带来源引用的相关段落。

        :param question: 用户问题(空问题返回空结果,不检索);
        :param top_k: 覆盖默认返回块数;
        :return: :class:`SearchResult`,``context`` 直接拼入 LLM 提示词,
            ``chunks`` 保留逐块得分供 Agent 工具结构化消费。
        """
        if not question.strip():
            return SearchResult(query=question, chunks=(), context=format_context(question, ()))
        k = top_k if top_k is not None else self.top_k
        pool_size = max(k * CANDIDATE_FACTOR, k)

        query_vec = self._encode([question])[0]
        self.store.setup(len(query_vec))
        hits = self.store.search(query_vec, top_k=pool_size)
        candidates = [
            ScoredChunk(chunk=chunk, vector_score=score, score=score)
            for chunk, score in hits
        ]
        reranked = self.reranker.rerank(question, candidates)[:k]
        return SearchResult(
            query=question,
            chunks=tuple(reranked),
            context=format_context(question, reranked),
        )


__all__ = [
    "CANDIDATE_FACTOR",
    "DEFAULT_TOP_K",
    "MemoryVectorStore",
    "PgvectorStore",
    "RagPipeline",
    "format_context",
]
