"""向量存储:pgvector 生产实现 + 内存实现(测试 / 离线演示)。

- :class:`VectorStore` 协议统一「建表 / 入库 / 删除 / 检索 / 文档列表」,
  检索逻辑(重排、上下文组装)只依赖协议,不绑定具体数据库;
- :class:`PgvectorStore` 基于 psycopg + pgvector(大纲的 PostgreSQL 存储),
    - 表结构按首次入库的向量维度创建(``vector(dim)``),换用不同维度的
      Embedding 后端时显式报错,而不是静默写入坏向量;
    - 余弦距离索引(HNSW ``vector_cosine_ops``),检索按
      ``embedding <=> query`` 排序,得分换算为余弦相似度 ``1 - distance``;
    - 同一 ``doc_id`` 重复入库为幂等替换(先删旧块再插入);
- :class:`MemoryVectorStore` 纯 Python 暴力余弦实现,复用
  :func:`skill_normalization.cosine_similarity`,供 pytest 固定 fixture
  与无数据库环境使用,排序语义与 pgvector 一致
  (得分降序,并列时按块 ID 稳定排序)。
"""

from __future__ import annotations

import json
from typing import Protocol, Sequence

from psycopg import Connection, sql

from rag.models import Chunk, DocumentRecord
from skillbridge.config import Settings
from skillbridge.db import postgres_connect
from skill_normalization import cosine_similarity

Vector = Sequence[float]


class VectorStore(Protocol):
    """向量存储协议:入库与检索的统一接口。"""

    def setup(self, dim: int) -> None:
        """初始化存储(建扩展 / 建表),并约定向量维度。"""
        ...

    def reset(self) -> None:
        """清空全部存储(删表 / 清内存),允许换用不同维度的后端重建。"""
        ...

    def upsert_chunks(
        self, chunks: Sequence[Chunk], embeddings: Sequence[Vector]
    ) -> int:
        """整批写入分块(同文档旧块先删除,幂等替换),返回写入块数。"""
        ...

    def delete_document(self, doc_id: str) -> int:
        """删除一个文档的全部分块,返回删除块数。"""
        ...

    def search(
        self, query_embedding: Vector, *, top_k: int = 5
    ) -> list[tuple[Chunk, float]]:
        """按余弦相似度检索最相近的 ``top_k`` 个块,返回 (块, 相似度)。"""
        ...

    def list_documents(self) -> list[DocumentRecord]:
        """列出已入库文档(按 doc_id 排序)。"""
        ...


# ---------------------------------------------------------------------------
# pgvector 实现
# ---------------------------------------------------------------------------

class PgvectorStore:
    """pgvector 向量存储(PostgreSQL,大纲第九节的存储层)。

    :param settings: 数据库配置,缺省读 ``skillbridge.config``(环境变量);
    :param connection: 已建立的 psycopg 连接(测试注入用);
        传入则由调用方管理生命周期,未传则内部创建并在 ``close()`` 时关闭。
    """

    def __init__(self, *, settings: Settings | None = None, connection: Connection | None = None):
        self._settings = settings
        self._connection = connection
        self._owned = connection is None
        self._dim: int | None = None
        self._adapters_registered = False

    # --- 连接管理 ---
    def _conn(self) -> Connection:
        if self._connection is None:
            self._connection = postgres_connect(self._settings)
        if not self._adapters_registered:
            # pgvector 的 Vector 适配器按连接注册(内部创建与外部注入同样需要)
            from pgvector.psycopg import register_vector

            register_vector(self._connection)
            self._adapters_registered = True
        return self._connection

    def close(self) -> None:
        """关闭内部创建的连接(外部注入的连接不关闭)。"""
        if self._owned and self._connection is not None:
            self._connection.close()
            self._connection = None

    def __enter__(self) -> "PgvectorStore":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    # --- 协议实现 ---
    def setup(self, dim: int) -> None:
        """建扩展 / 建表 / 校验维度(幂等,可重复调用)。"""
        if dim <= 0:
            raise ValueError(f"向量维度必须为正数,收到 {dim}")
        conn = self._conn()
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS rag_documents (
                    doc_id      TEXT PRIMARY KEY,
                    title       TEXT NOT NULL,
                    source      TEXT NOT NULL,
                    chunk_count INTEGER NOT NULL DEFAULT 0,
                    dim         INTEGER NOT NULL,
                    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            cur.execute(
                sql.SQL(
                    """
                    CREATE TABLE IF NOT EXISTS rag_chunks (
                        chunk_id     TEXT PRIMARY KEY,
                        doc_id       TEXT NOT NULL
                                     REFERENCES rag_documents(doc_id) ON DELETE CASCADE,
                        doc_title    TEXT NOT NULL,
                        source       TEXT NOT NULL,
                        heading_path JSONB NOT NULL DEFAULT '[]',
                        chunk_index  INTEGER NOT NULL,
                        content      TEXT NOT NULL,
                        embedding    VECTOR({}),
                        UNIQUE (doc_id, chunk_index)
                    )
                    """
                ).format(sql.Literal(dim))
            )
            cur.execute(
                """
                SELECT atttypmod FROM pg_attribute
                WHERE attrelid = 'rag_chunks'::regclass
                  AND attname = 'embedding' AND NOT attisdropped
                """
            )
            row = cur.fetchone()
            if row is not None and row[0] != dim:
                raise ValueError(
                    f"rag_chunks 向量维度为 {row[0]},与当前 Embedding 后端的 "
                    f"{dim} 维不一致(换后端后需重建);"
                    f"请用 `python -m rag ingest <路径> --reset` 重建,"
                    f"或换回原后端"
                )
        conn.commit()
        self._dim = dim

    def reset(self) -> None:
        """删除 RAG 两张表并忘记维度(换 Embedding 后端后重建用)。

        与 ``TRUNCATE`` 不同,本方法连列类型(vector(dim))一并删除,
        之后可用任意维度的后端重新 ``setup`` 入库。
        """
        conn = self._conn()
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS rag_chunks")
            cur.execute("DROP TABLE IF EXISTS rag_documents")
        conn.commit()
        self._dim = None

    def upsert_chunks(
        self, chunks: Sequence[Chunk], embeddings: Sequence[Vector]
    ) -> int:
        if len(chunks) != len(embeddings):
            raise ValueError(f"块数与向量数不一致: {len(chunks)} != {len(embeddings)}")
        if not chunks:
            return 0
        if self._dim is None:
            self.setup(len(embeddings[0]))
        elif len(embeddings[0]) != self._dim:
            raise ValueError(
                f"向量维度 {len(embeddings[0])} 与存储维度 {self._dim} 不一致"
            )
        conn = self._conn()
        doc_ids = sorted({c.doc_id for c in chunks})
        from pgvector import Vector as PgVector

        with conn.cursor() as cur:
            for doc_id in doc_ids:
                cur.execute("DELETE FROM rag_chunks WHERE doc_id = %s", (doc_id,))
            for chunk, embedding in zip(chunks, embeddings):
                cur.execute(
                    """
                    INSERT INTO rag_documents (doc_id, title, source, chunk_count, dim)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (doc_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        source = EXCLUDED.source,
                        chunk_count = EXCLUDED.chunk_count,
                        dim = EXCLUDED.dim
                    """,
                    (
                        chunk.doc_id,
                        chunk.doc_title,
                        chunk.source,
                        sum(1 for c in chunks if c.doc_id == chunk.doc_id),
                        self._dim,
                    ),
                )
                cur.execute(
                    """
                    INSERT INTO rag_chunks
                        (chunk_id, doc_id, doc_title, source, heading_path,
                         chunk_index, content, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        chunk.chunk_id,
                        chunk.doc_id,
                        chunk.doc_title,
                        chunk.source,
                        json.dumps(list(chunk.heading_path), ensure_ascii=False),
                        chunk.chunk_index,
                        chunk.content,
                        PgVector(list(embedding)),
                    ),
                )
        conn.commit()
        return len(chunks)

    def delete_document(self, doc_id: str) -> int:
        conn = self._conn()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM rag_chunks WHERE doc_id = %s", (doc_id,))
            deleted = cur.rowcount
            cur.execute("DELETE FROM rag_documents WHERE doc_id = %s", (doc_id,))
        conn.commit()
        return deleted

    def search(
        self, query_embedding: Vector, *, top_k: int = 5
    ) -> list[tuple[Chunk, float]]:
        if self._dim is not None and len(query_embedding) != self._dim:
            raise ValueError(
                f"查询向量维度 {len(query_embedding)} 与存储维度 {self._dim} 不一致"
            )
        from pgvector import Vector as PgVector

        query = PgVector(list(query_embedding))
        conn = self._conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT chunk_id, doc_id, doc_title, source, heading_path,
                       chunk_index, content,
                       1 - (embedding <=> %s) AS score
                FROM rag_chunks
                ORDER BY embedding <=> %s
                LIMIT %s
                """,
                (query, query, top_k),
            )
            rows = cur.fetchall()
        return [
            (
                Chunk(
                    chunk_id=row[0],
                    doc_id=row[1],
                    doc_title=row[2],
                    source=row[3],
                    heading_path=tuple(row[4]),
                    chunk_index=row[5],
                    content=row[6],
                ),
                float(row[7]),
            )
            for row in rows
        ]

    def list_documents(self) -> list[DocumentRecord]:
        conn = self._conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT doc_id, title, source, chunk_count
                FROM rag_documents ORDER BY doc_id
                """
            )
            rows = cur.fetchall()
        return [DocumentRecord(*row) for row in rows]


# ---------------------------------------------------------------------------
# 内存实现(测试 / 离线)
# ---------------------------------------------------------------------------

class MemoryVectorStore:
    """内存向量存储:暴力余弦检索,语义与 pgvector 实现对齐。

    供 pytest 固定 fixture 与无数据库环境使用;进程内状态,
    不做持久化。
    """

    def __init__(self):
        self._chunks: list[tuple[Chunk, list[float]]] = []
        self._documents: dict[str, DocumentRecord] = {}
        self._dim: int | None = None

    def setup(self, dim: int) -> None:
        if dim <= 0:
            raise ValueError(f"向量维度必须为正数,收到 {dim}")
        if self._dim is not None and self._dim != dim:
            raise ValueError(
                f"向量维度不一致:已按 {self._dim} 维入库,不能切换为 {dim} 维"
                f"(与 pgvector 行为一致,可 reset 后重建)"
            )
        self._dim = dim

    def reset(self) -> None:
        """清空全部块、文档登记与维度约定(与 pgvector 实现语义对齐)。"""
        self._chunks = []
        self._documents = {}
        self._dim = None

    def upsert_chunks(
        self, chunks: Sequence[Chunk], embeddings: Sequence[Vector]
    ) -> int:
        if len(chunks) != len(embeddings):
            raise ValueError(f"块数与向量数不一致: {len(chunks)} != {len(embeddings)}")
        if not chunks:
            return 0
        vectors = [list(v) for v in embeddings]
        if self._dim is None:
            self.setup(len(vectors[0]))
        for vector in vectors:
            if len(vector) != self._dim:
                raise ValueError(
                    f"向量维度 {len(vector)} 与存储维度 {self._dim} 不一致"
                )
        doc_ids = {c.doc_id for c in chunks}
        self._chunks = [pair for pair in self._chunks if pair[0].doc_id not in doc_ids]
        self._chunks.extend(zip(chunks, vectors))
        for doc_id in doc_ids:
            doc_chunks = [c for c in chunks if c.doc_id == doc_id]
            first = doc_chunks[0]
            self._documents[doc_id] = DocumentRecord(
                doc_id=doc_id,
                title=first.doc_title,
                source=first.source,
                chunk_count=len(doc_chunks),
            )
        return len(chunks)

    def delete_document(self, doc_id: str) -> int:
        remaining = []
        deleted = 0
        for chunk, vector in self._chunks:
            if chunk.doc_id == doc_id:
                deleted += 1
            else:
                remaining.append((chunk, vector))
        self._chunks = remaining
        self._documents.pop(doc_id, None)
        return deleted

    def search(
        self, query_embedding: Vector, *, top_k: int = 5
    ) -> list[tuple[Chunk, float]]:
        if not self._chunks:
            return []
        query = list(query_embedding)
        scored = [
            (chunk, cosine_similarity(query, vector)) for chunk, vector in self._chunks
        ]
        # 得分降序;并列时按 (doc_id, chunk_index) 稳定排序,保证确定性
        scored.sort(key=lambda item: (-item[1], item[0].doc_id, item[0].chunk_index))
        return scored[:top_k]

    def list_documents(self) -> list[DocumentRecord]:
        return [self._documents[doc_id] for doc_id in sorted(self._documents)]


__all__ = [
    "MemoryVectorStore",
    "PgvectorStore",
    "VectorStore",
]
