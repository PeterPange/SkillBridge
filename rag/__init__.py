"""企业知识库 RAG 模块(大纲第九节,阶段 4)。

解决「为什么、怎么学、公司规定是什么」:企业培训制度、岗位说明书、
课程材料等文档入库后,支持自然语言提问检索出**带来源引用**的相关段落::

    PDF / Word / Markdown
          ↓ reader(文档解析,标题识别)
    标题级分块(chunker,块携带标题路径与来源)
          ↓ Embedding(复用 skill_normalization 后端)
    pgvector(store,余弦 Top-K 召回)
          ↓ rerank(查询词覆盖重排)
    带来源引用的上下文(pipeline.format_context,拼入 LLM 提示词)

主要入口:
- ``RagPipeline.ingest_file / ingest_dir`` → 文档入库;
- ``RagPipeline.query`` → :class:`SearchResult`(命中块 + 引用上下文);
- ``python -m rag ingest <路径>`` / ``python -m rag ask \"问题\"`` → CLI。

降级策略(与 skill_normalization 一致):无 sentence-transformers /
无网络时 Embedding 自动退化为词面匹配;向量存储除 pgvector 外提供
内存实现,pytest 固定 fixture 在无数据库环境下即可覆盖分块与检索逻辑。
"""

from rag.chunker import DEFAULT_MAX_CHARS, chunk_document
from rag.models import (
    Chunk,
    DocumentRecord,
    IngestResult,
    ParsedDocument,
    ScoredChunk,
    SearchResult,
    Section,
)
from rag.pipeline import DEFAULT_TOP_K, RagPipeline, format_context
from rag.reader import (
    SUPPORTED_SUFFIXES,
    parse_docx,
    parse_document,
    parse_markdown,
    parse_pdf,
)
from rag.rerank import DEFAULT_VECTOR_WEIGHT, LexicalReranker, Reranker, tokenize
from rag.store import MemoryVectorStore, PgvectorStore, VectorStore
# Embedding 后端直接复用 skill_normalization(阶段 1B)的实现,
# 此处重导出方便调用方从 rag 统一导入。
from skill_normalization import (
    LexicalEncoder,
    SentenceTransformerEncoder,
    TextEncoder,
    default_encoder,
)

__all__ = [
    "Chunk",
    "DEFAULT_MAX_CHARS",
    "DEFAULT_TOP_K",
    "DEFAULT_VECTOR_WEIGHT",
    "DocumentRecord",
    "IngestResult",
    "LexicalEncoder",
    "LexicalReranker",
    "MemoryVectorStore",
    "ParsedDocument",
    "PgvectorStore",
    "RagPipeline",
    "Reranker",
    "ScoredChunk",
    "SearchResult",
    "Section",
    "SentenceTransformerEncoder",
    "SUPPORTED_SUFFIXES",
    "TextEncoder",
    "VectorStore",
    "chunk_document",
    "default_encoder",
    "format_context",
    "parse_docx",
    "parse_document",
    "parse_markdown",
    "parse_pdf",
    "tokenize",
]
