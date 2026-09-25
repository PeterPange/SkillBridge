"""pgvector 集成测试:大纲第九节验收——企业培训制度文档入库后,
自然语言提问能检索出相关段落。

前置条件:``make up``(PostgreSQL + pgvector)。数据库不可达时整模块
跳过;分块与检索逻辑本身的离线覆盖见 ``test_rag_retrieval.py``。

Embedding 使用生产默认后端(sentence-transformers 本地模型,
未安装/无网络时管线自动降级词面匹配);全部断言问题均已在
两种后端下验证命中对应章节,测试在任一环境下结果一致。
模块 fixture 在独立测试库 skillbridge_rag_test 中重建 RAG 两张表,
"""

from __future__ import annotations

import pytest

psycopg = pytest.importorskip("psycopg")

from rag import MemoryVectorStore, PgvectorStore, RagPipeline, default_encoder  # noqa: E402
from psycopg import errors as pg_errors  # noqa: E402
from skillbridge.config import get_settings  # noqa: E402
from skillbridge.db import postgres_connect  # noqa: E402

TEST_DOC_ID = "rag_it_培训制度"
TEST_DB_NAME = "skillbridge_rag_test"


def _postgres_available() -> bool:
    try:
        conn = postgres_connect()
    except Exception:
        return False
    conn.close()
    return True


def _test_db_connect():
    """连接独立测试库(不存在则创建),不触碰开发库的 rag 表。

    测试库与开发库同实例、同凭据,仅 dbname 不同;
    DROP/CREATE 只影响 ``skillbridge_rag_test``。
    """
    admin = postgres_connect()
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (TEST_DB_NAME,))
        if cur.fetchone() is None:
            cur.execute(
                f'CREATE DATABASE "{TEST_DB_NAME}" TEMPLATE template0 ENCODING \'utf8\''
            )
    admin.close()
    s = get_settings()
    conn = psycopg.connect(
        host=s.postgres_host,
        port=s.postgres_port,
        user=s.postgres_user,
        password=s.postgres_password,
        dbname=TEST_DB_NAME,
    )
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
    conn.commit()
    return conn


pytestmark = pytest.mark.skipif(
    not _postgres_available(), reason="需要 PostgreSQL + pgvector:先 make up"
)


# ---------------------------------------------------------------------------
# fixture:独立测试库中重建 RAG 表 + 入库固定文档,模块内全部测试复用
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def test_conn():
    conn = _test_db_connect()
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS rag_chunks")
        cur.execute("DROP TABLE IF EXISTS rag_documents")
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def store(test_conn):
    store = PgvectorStore(connection=test_conn)
    yield store
    try:
        store.delete_document(TEST_DOC_ID)
    except pg_errors.UndefinedTable:
        pass  # 某个测试刚 reset 过表:无需清理


@pytest.fixture(scope="module")
def pipeline(store, training_policy_path) -> RagPipeline:
    pipe = RagPipeline(encoder=default_encoder(), store=store, top_k=3)
    result = pipe.ingest_file(training_policy_path, doc_id=TEST_DOC_ID)
    print(f"RAG 验收入库: {result.chunk_count} 块,后端 {result.backend}")
    return pipe


# ---------------------------------------------------------------------------
# 验收:自然语言提问 → 相关段落
# ---------------------------------------------------------------------------

def test_acceptance_natural_language_query(pipeline):
    """大纲第九节验收:培训制度入库后,自然语言提问检索出相关段落。"""
    result = pipeline.query("新员工入职培训期是多久?")
    assert result.has_hits
    top = result.chunks[0]
    assert top.chunk.doc_id == TEST_DOC_ID
    assert top.chunk.heading_path[0] == "第二章 新员工入职培训"
    assert "三个月" in top.chunk.content
    # 上下文带完整来源引用
    assert "[1]" in result.context
    assert "《企业员工培训管理制度》" in result.context
    assert "第二章 新员工入职培训" in result.context


def test_acceptance_multiple_questions(pipeline):
    """多个自然语言问题各自命中对应章节(检索不是只会答一题)。"""
    cases = [
        ("外部培训费用怎么报销?", "第五章 培训费用与报销"),
        ("全体员工每自然年度须完成多少培训学时?", "第三章 在职培训与年度学时"),
        ("考核多少分算合格?", "第四章 培训考核与效果评估"),
        ("晋升答辩看什么?", "第六章 晋升与能力发展"),
    ]
    for question, expected_chapter in cases:
        result = pipeline.query(question)
        assert result.has_hits, f"未检索到: {question}"
        assert result.chunks[0].chunk.heading_path[0] == expected_chapter, (
            f"{question} → {result.chunks[0].chunk.heading_path}"
        )


# ---------------------------------------------------------------------------
# 存储行为:幂等入库 / 维度校验 / 删除 / 标题路径往返
# ---------------------------------------------------------------------------

def test_reingest_is_idempotent(pipeline, training_policy_path, store):
    """同一文档重复入库为替换:块数不变、无重复块。"""
    first = pipeline.ingest_file(training_policy_path, doc_id=TEST_DOC_ID)
    second = pipeline.ingest_file(training_policy_path, doc_id=TEST_DOC_ID)
    assert first.chunk_count == second.chunk_count

    documents = store.list_documents()
    record = next(d for d in documents if d.doc_id == TEST_DOC_ID)
    assert record.chunk_count == second.chunk_count

    result = pipeline.query("导师制度是怎么规定的?", top_k=10)
    chunk_ids = [sc.chunk.chunk_id for sc in result.chunks]
    assert len(chunk_ids) == len(set(chunk_ids))  # 无重复块


def test_heading_path_roundtrip_via_jsonb(pipeline):
    """标题路径经 JSONB 存取后完整还原(引用溯源不丢层级)。"""
    result = pipeline.query("晋升答辩看什么?")
    assert result.has_hits
    top = result.chunks[0].chunk
    assert top.heading_path == ("第六章 晋升与能力发展",)
    assert top.doc_title == "企业员工培训管理制度"
    assert top.source.endswith("training_policy.md")


def test_setup_rejects_dim_change(store):
    """表已按当前后端维度建立后,换维度后端被显式拒绝。"""
    current_dim = store._dim
    assert current_dim > 0
    with pytest.raises(ValueError, match="维度"):
        store.setup(current_dim + 1)


def test_delete_document(pipeline, training_policy_path):
    """删除文档后检索不到,再入库可恢复。"""
    deleted = pipeline.store.delete_document(TEST_DOC_ID)
    assert deleted > 0
    assert pipeline.query("入职培训期是多久?").chunks == ()
    assert all(
        d.doc_id != TEST_DOC_ID for d in pipeline.store.list_documents()
    )
    # 恢复,供同模块后续测试(或下一轮运行)使用
    pipeline.ingest_file(training_policy_path, doc_id=TEST_DOC_ID)


def test_memory_and_pgvector_agree_on_top_chunk(pipeline, test_conn, training_policy_path):
    """内存实现与 pgvector 对同一问题的 Top-1 判定一致(语义对齐)。"""
    memory = RagPipeline(
        encoder=pipeline.encoder, store=MemoryVectorStore(), top_k=1
    )
    memory.ingest_file(training_policy_path)

    pg = RagPipeline(
        encoder=pipeline.encoder, store=PgvectorStore(connection=test_conn), top_k=1
    )
    question = "新员工入职培训期是多久?"
    memory_top = memory.query(question).chunks[0]
    pg_top = pg.query(question).chunks[0]
    assert memory_top.chunk.content == pg_top.chunk.content
    assert abs(memory_top.vector_score - pg_top.vector_score) < 1e-6


def test_reset_allows_backend_switch(pipeline, store, training_policy_path):
    """reset() 连列类型一起删:换维度后端后可重建(本模块最后一个测试,
    结束前恢复原维度与数据,供 fixture 清理与下一轮运行使用)。"""
    dim_before = store._dim
    assert dim_before > 0

    store.reset()
    store.setup(dim_before + 1)  # 新维度建表成功
    assert store.list_documents() == []  # 旧数据已清空

    # 恢复:换回原维度并重新入库
    store.reset()
    pipeline.ingest_file(training_policy_path, doc_id=TEST_DOC_ID)
    assert store._dim == dim_before
    assert pipeline.query("入职培训期是多久?").has_hits
