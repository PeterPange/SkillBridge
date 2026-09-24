"""检索与重排测试(大纲第九节:Retriever → Reranker → 引用上下文)。

不依赖数据库与网络:固定 fixture「企业员工培训制度」+ 词面编码器
(skill_normalization 的 LexicalEncoder,确定性)+ 内存向量存储,
完整覆盖「入库 → 自然语言提问 → 检索出相关段落 → 带来源引用」链路。
pgvector 真库验收见 ``test_rag_pgvector.py``。
"""

from __future__ import annotations

import pytest

from rag import (
    LexicalEncoder,
    LexicalReranker,
    MemoryVectorStore,
    RagPipeline,
    chunk_document,
    format_context,
    tokenize,
)
from rag.models import Chunk, ScoredChunk
from rag.reader import parse_document

# ---------------------------------------------------------------------------
# 固定 fixture:入库一次,模块内复用
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def pipeline(training_policy_path):
    """词面编码器 + 内存存储的 RAG 管线(离线确定性)。"""
    pipe = RagPipeline(
        encoder=LexicalEncoder(),
        store=MemoryVectorStore(),
        top_k=3,
    )
    pipe.ingest_file(training_policy_path)
    return pipe


def _chunk(pipeline, doc_id="企业员工培训管理制度") -> list[Chunk]:
    return [chunk for chunk, _ in pipeline.store._chunks if chunk.doc_id == doc_id]


# ---------------------------------------------------------------------------
# 入库
# ---------------------------------------------------------------------------

def test_ingest_result(pipeline, training_policy_path):
    """入库摘要:块数、维度、后端描述。"""
    result = pipeline.ingest_file(training_policy_path)  # 幂等:重复入库
    assert result.title == "企业员工培训管理制度"
    assert result.source == str(training_policy_path)
    assert result.chunk_count >= 7
    assert result.dim == 512  # LexicalEncoder 固定维度
    assert result.backend == "lexical"
    # 重复入库为替换而非追加
    assert len(_chunk(pipeline)) == result.chunk_count
    documents = pipeline.store.list_documents()
    assert [d.doc_id for d in documents] == ["企业员工培训管理制度"]
    assert documents[0].chunk_count == result.chunk_count


def test_ingest_empty_document_rejected():
    """空文档(无正文可分块)入库时显式报错,而不是静默写入零块。"""
    from rag.models import ParsedDocument, Section

    pipe = RagPipeline(encoder=LexicalEncoder(), store=MemoryVectorStore())
    empty = ParsedDocument(title="空", source="empty.md", sections=(Section(None, 0, ""),))
    with pytest.raises(ValueError, match="没有可分块的内容"):
        pipe.ingest_document(empty)


# ---------------------------------------------------------------------------
# 验收:自然语言提问 → 相关段落(大纲第九节验收标准)
# ---------------------------------------------------------------------------

def test_query_onboarding_duration(pipeline):
    """「新员工入职培训期是多久」→ 命中第二章,答案段落在 Top-1。"""
    result = pipeline.query("新员工入职培训期是多久?")
    assert result.has_hits
    top = result.chunks[0]
    assert top.chunk.heading_path[0] == "第二章 新员工入职培训"
    assert "三个月" in top.chunk.content
    assert top.vector_score > 0.3  # 词面编码器下相关段落相似度显著


def test_query_reimbursement(pipeline):
    """「外部培训费用怎么报销」→ 命中第五章培训费用。"""
    result = pipeline.query("外部培训费用怎么报销?")
    assert result.has_hits
    top = result.chunks[0]
    assert top.chunk.heading_path[0] == "第五章 培训费用与报销"
    assert "报销" in top.chunk.content


def test_query_mentor_system(pipeline):
    """「导师是怎么指定的」→ 命中导师制度条款。"""
    result = pipeline.query("新员工的导师是怎么指定的?")
    assert result.has_hits
    top = result.chunks[0]
    assert top.chunk.heading_path[0] == "第二章 新员工入职培训"
    assert "导师" in top.chunk.content


def test_query_promotion(pipeline):
    """「晋升看什么材料」→ 命中第六章晋升与能力发展。"""
    result = pipeline.query("晋升答辩需要参考哪些材料?")
    assert result.has_hits
    top = result.chunks[0]
    assert top.chunk.heading_path[0] == "第六章 晋升与能力发展"
    assert "晋升" in top.chunk.content


def test_query_ranked_and_limited(pipeline):
    """结果按综合分降序、数量不超过 top_k。"""
    result = pipeline.query("年度培训学时要求是多少?", top_k=2)
    assert len(result.chunks) <= 2
    scores = [sc.score for sc in result.chunks]
    assert scores == sorted(scores, reverse=True)
    # 每个命中块的分值字段完整
    for scored in result.chunks:
        assert 0.0 <= scored.lexical_score <= 1.0
        assert scored.score >= 0.0


def test_query_empty_question(pipeline):
    """空问题不检索,返回未命中结果。"""
    result = pipeline.query("   ")
    assert not result.has_hits
    assert result.chunks == ()
    assert "未检索到" in result.context


# ---------------------------------------------------------------------------
# 带来源引用的上下文
# ---------------------------------------------------------------------------

def test_context_contains_citations(pipeline):
    """上下文带编号引用:文档标题、标题路径、来源、相关度、正文。"""
    result = pipeline.query("入职培训期是多久?")
    context = result.context
    assert context.startswith("基于知识库检索到的相关内容")
    assert "[1]" in context
    assert "《企业员工培训管理制度》" in context
    assert "第二章 新员工入职培训" in context  # 标题路径
    assert "来源:" in context and "training_policy.md" in context
    assert "相关度" in context
    assert "三个月" in context  # 命中正文


def test_format_context_empty():
    assert format_context("问题", ()) == "知识库中未检索到与问题相关的内容。"


# ---------------------------------------------------------------------------
# 重排:词面覆盖修正向量排序
# ---------------------------------------------------------------------------

def _scored(chunk_id: str, content: str, vector_score: float) -> ScoredChunk:
    chunk = Chunk(
        chunk_id=chunk_id,
        doc_id="doc",
        doc_title="文档",
        source="doc.md",
        heading_path=(),
        chunk_index=int(chunk_id.split("-")[1]),
        content=content,
    )
    return ScoredChunk(chunk=chunk, vector_score=vector_score, score=vector_score)


def test_rerank_flips_semantically_similar_but_off_topic():
    """向量分接近但答非所问的块,被查询词覆盖重排压下去。

    场景:两个块语义上都和「培训」相关(向量分接近),但只有后者
    命中问题里的具体业务词(费用/报销/提交),重排后应反超。
    """
    chunks = [
        _scored("doc-0", "培训考核以百分制评分,85分为合格线。", 0.62),
        _scored("doc-1", "外部培训费用报销须提交发票与审批记录。", 0.50),
    ]
    reranker = LexicalReranker()  # 默认 vector_weight=0.6
    reranked = reranker.rerank("培训费用报销需要提交什么材料?", chunks)

    assert reranked[0].chunk.chunk_id == "doc-1"  # 覆盖率高的反超
    assert reranked[0].lexical_score > reranked[1].lexical_score
    assert reranked[0].score > reranked[1].score
    # 入参不被修改(返回新对象)
    assert chunks[0].score == 0.62 and chunks[0].lexical_score == 0.0


def test_rerank_respects_vector_dominance():
    """词面都不命中时,向量分决定排序。"""
    chunks = [
        _scored("doc-0", "苹果与香蕉都属于水果类别。", 0.30),
        _scored("doc-1", "橙子葡萄西瓜同样是常见水果。", 0.80),
    ]
    reranked = LexicalReranker().rerank("量子力学的基本原理是什么?", chunks)
    assert reranked[0].chunk.chunk_id == "doc-1"
    assert reranked[0].score > reranked[1].score


def test_rerank_stable_for_ties():
    """完全并列时按块 ID 稳定排序,结果确定。"""
    chunks = [
        _scored("doc-1", "内容甲。", 0.5),
        _scored("doc-0", "内容乙。", 0.5),
    ]
    reranked = LexicalReranker().rerank("内容", chunks)
    assert [sc.chunk.chunk_id for sc in reranked] == ["doc-0", "doc-1"]


def test_rerank_weight_validation():
    with pytest.raises(ValueError, match="vector_weight"):
        LexicalReranker(vector_weight=1.5)


def test_tokenize_mixed_language():
    """词元化:西文小写化 + CJK 二元组。"""
    tokens = tokenize("RAG 报销流程")
    assert "rag" in tokens
    assert "报销" in tokens and "销流" in tokens and "流程" in tokens
    assert tokenize("") == set()


# ---------------------------------------------------------------------------
# 内存向量存储:维度约束与确定性
# ---------------------------------------------------------------------------

def test_store_rejects_dim_mismatch(training_policy_path):
    store = MemoryVectorStore()
    store.setup(512)
    with pytest.raises(ValueError, match="维度"):
        store.setup(384)

    doc = parse_document(training_policy_path)
    chunks = chunk_document(doc, doc_id="dim_test", max_chars=400)
    encoder = LexicalEncoder()
    embeddings = encoder.encode([c.embed_text() for c in chunks])
    with pytest.raises(ValueError, match="维度"):
        store.upsert_chunks(chunks, [v[:384] for v in embeddings])


def test_store_upsert_count_mismatch(training_policy_path):
    store = MemoryVectorStore()
    store.setup(512)
    doc = parse_document(training_policy_path)
    chunks = chunk_document(doc, doc_id="count_test", max_chars=400)
    with pytest.raises(ValueError, match="块数与向量数不一致"):
        store.upsert_chunks(chunks[:2], [])


def test_store_delete_document(training_policy_path):
    """按文档删除:块与登记项一起清掉。"""
    pipe = RagPipeline(encoder=LexicalEncoder(), store=MemoryVectorStore())
    pipe.ingest_file(training_policy_path)
    deleted = pipe.store.delete_document("企业员工培训管理制度")
    assert deleted > 0
    assert pipe.store.list_documents() == []
    assert pipe.query("入职培训期是多久?").chunks == ()


# ---------------------------------------------------------------------------
# 管线:降级与批量入库
# ---------------------------------------------------------------------------

def test_store_reset_allows_dim_switch(training_policy_path):
    """reset() 清空维度约定:可换维度后端重建(与 pgvector 语义对齐)。"""
    pipe = RagPipeline(encoder=LexicalEncoder(), store=MemoryVectorStore())
    pipe.ingest_file(training_policy_path)
    assert pipe.store._dim == 512
    with pytest.raises(ValueError, match="维度"):
        pipe.store.setup(384)

    pipe.store.reset()
    assert pipe.store.list_documents() == []
    pipe.store.setup(384)  # 新维度可用
    assert pipe.store.search([0.0] * 384, top_k=3) == []  # 旧数据已清空


def test_pipeline_degrades_gracefully_when_model_unavailable(training_policy_path):
    """sentence-transformers 加载/编码失败时,管线降级为词面匹配而不是报错
    (与 skill_normalization.EmbeddingMatcher 同策略)。"""
    from rag import SentenceTransformerEncoder

    class UnavailableModel(SentenceTransformerEncoder):
        def encode(self, texts):
            raise RuntimeError("模型加载失败(未安装/无网络/无缓存)")

    pipe = RagPipeline(encoder=UnavailableModel(), store=MemoryVectorStore())
    result = pipe.ingest_file(training_policy_path)
    assert result.backend == "lexical"  # 降级后的后端
    assert result.dim == 512
    # 降级后的检索仍然可用
    top = pipe.query("新员工入职培训期是多久?").chunks[0]
    assert top.chunk.heading_path[0] == "第二章 新员工入职培训"


def test_pipeline_raises_for_broken_custom_encoder(training_policy_path):
    """非 sentence-transformers 编码器(含测试桩)的异常原样抛出,不降级。"""

    class BrokenStub:
        def encode(self, texts):
            raise RuntimeError("boom")

    pipe = RagPipeline(encoder=BrokenStub(), store=MemoryVectorStore())
    with pytest.raises(RuntimeError, match="boom"):
        pipe.ingest_file(training_policy_path)


def test_ingest_dir(tmp_path, training_policy_path):
    """目录批量入库:只取受支持的类型,按文件名顺序,可加 doc_id 前缀。"""
    (tmp_path / "b制度.md").write_text("# B 文档\n\n正文内容。", encoding="utf-8")
    (tmp_path / "a手册.md").write_text("# A 文档\n\n正文内容。", encoding="utf-8")
    (tmp_path / "忽略.json").write_text("{}", encoding="utf-8")  # 不支持的类型

    pipe = RagPipeline(encoder=LexicalEncoder(), store=MemoryVectorStore())
    results = pipe.ingest_dir(tmp_path, doc_id_prefix="dir1/")
    assert [r.title for r in results] == ["A 文档", "B 文档"]
    assert all(r.doc_id.startswith("dir1/") for r in results)
    assert [d.doc_id for d in pipe.store.list_documents()] == [
        "dir1/a手册",
        "dir1/b制度",
    ]
    # 同一目录换前缀再入库:两套文档共存,互不覆盖
    pipe.ingest_dir(tmp_path, doc_id_prefix="dir2/")
    assert len(pipe.store.list_documents()) == 4

    with pytest.raises(FileNotFoundError, match="目录不存在"):
        pipe.ingest_dir(tmp_path / "missing")
