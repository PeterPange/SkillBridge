"""标题级分块测试(大纲第九节:文档解析 → 标题级分块)。

使用固定 fixture「企业员工培训制度」覆盖:
- 小节 → 块的标题路径(引用溯源的依据);
- 超长小节按段落边界切分、超长段落按句子硬切;
- 空小节保留层级但不产生块;空文档 / 非法参数的边界行为。
"""

from __future__ import annotations

import pytest

from rag.chunker import chunk_document
from rag.models import ParsedDocument, Section
from rag.reader import parse_document

# ---------------------------------------------------------------------------
# 固定 fixture:企业培训制度文档
# ---------------------------------------------------------------------------

def test_chunk_policy_document(training_policy_path):
    """验收 fixture 整篇分块:块数、溯源字段、标题路径全部正确。"""
    doc = parse_document(training_policy_path)
    chunks = chunk_document(doc)

    assert len(chunks) >= 7  # 导语 + 七章,至少每章一块
    # 溯源字段
    assert all(c.doc_id == "企业员工培训管理制度" for c in chunks)
    assert all(c.doc_title == doc.title for c in chunks)
    assert all(c.source == str(training_policy_path) for c in chunks)
    # 块号连续、块 ID 唯一且与序号对应
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    assert len({c.chunk_id for c in chunks}) == len(chunks)
    assert chunks[0].chunk_id.endswith(":0000")

    # 每章至少一块,且标题路径以章标题开头
    chapter_titles = [s.heading for s in doc.sections if s.heading and s.level == 2]
    for title in chapter_titles:
        assert any(
            c.heading_path and c.heading_path[0] == title for c in chunks
        ), f"章节未产生分块: {title}"

    # 导语(文档元信息行)是第 0 块,标题路径为空
    assert chunks[0].heading_path == ()
    assert "人力资源部" in chunks[0].content


def test_chunk_heading_path_nesting():
    """多级标题:块的标题路径包含完整层级链,空标题小节保留层级。"""
    doc = ParsedDocument(
        title="手册",
        source="handbook.md",
        sections=(
            Section(heading="第一章 入职", level=1, text=""),  # 无正文,仅维护层级
            Section(heading="1.1 导师", level=2, text="导师负责带教。"),
            Section(heading="第二章 考核", level=1, text="考核以笔试为主。"),
        ),
    )
    chunks = chunk_document(doc)
    assert [c.heading_path for c in chunks] == [
        ("第一章 入职", "1.1 导师"),  # 空的父标题仍在路径中
        ("第二章 考核",),
    ]


def test_chunk_preamble_then_heading_reset():
    """导语清空标题栈;同级标题相互替换。"""
    doc = ParsedDocument(
        title="文档",
        source="d.md",
        sections=(
            Section(heading=None, level=0, text="导语。"),
            Section(heading="A", level=1, text="A 的正文。"),
            Section(heading="B", level=1, text="B 的正文。"),
        ),
    )
    chunks = chunk_document(doc)
    assert [c.heading_path for c in chunks] == [(), ("A",), ("B",)]


def test_chunk_long_section_split_respects_limit(training_policy_path):
    """超长小节切分为多块:每块不超上限、内容按原文顺序完整保留。"""
    doc = parse_document(training_policy_path)
    onboarding = next(s for s in doc.sections if s.heading == "第二章 新员工入职培训")
    assert len(onboarding.text) > 300  # 前提:该章足够长

    chunks = chunk_document(doc, max_chars=300)
    onboarding_chunks = [
        c for c in chunks if c.heading_path == ("第二章 新员工入职培训",)
    ]
    assert len(onboarding_chunks) >= 2  # 被切成多块
    assert all(c.char_count <= 300 for c in onboarding_chunks)
    # 块按原文顺序拼接后与原小节内容一致(忽略空白折叠差异,无丢失无重复)
    rejoined = "".join("".join(c.content.split()) for c in onboarding_chunks)
    assert rejoined in "".join(onboarding.text.split())
    # 切分不跨标题:块号在文档内连续
    indexes = [c.chunk_index for c in onboarding_chunks]
    assert indexes == list(range(indexes[0], indexes[0] + len(indexes)))


def test_chunk_oversized_paragraph_hard_split():
    """单段超过上限:按句子边界切;无标点的病态段按字符兜底切。"""
    sentences = ["这是第%d句话,内容足够长一些。" % i for i in range(30)]
    doc = ParsedDocument(
        title="文档",
        source="long.md",
        sections=(Section(heading="长文", level=1, text="".join(sentences)),),
    )
    chunks = chunk_document(doc, max_chars=100)
    assert len(chunks) >= 3
    assert all(c.char_count <= 100 for c in chunks)
    assert "".join(c.content for c in chunks) == "".join(sentences)  # 无丢失无重复

    # 病态:整段无任何句末标点 → 按字符硬切,内容完整
    pathological = "无标点正文" * 50  # 250 字
    doc = ParsedDocument(
        title="文档",
        source="pathological.md",
        sections=(Section(heading="病态", level=1, text=pathological),),
    )
    chunks = chunk_document(doc, max_chars=80)
    assert all(c.char_count <= 80 for c in chunks)
    assert "".join(c.content for c in chunks) == pathological


def test_chunk_paragraphs_packed_greedily():
    """短段落贪心合并进同一块,直到超过上限。"""
    paragraphs = "\n\n".join(f"第{i}段。" for i in range(1, 6))  # 每段约 4 字
    doc = ParsedDocument(
        title="文档",
        source="pack.md",
        sections=(Section(heading="短段", level=1, text=paragraphs),),
    )
    chunks = chunk_document(doc, max_chars=30)
    assert len(chunks) == 1  # 全部段落装进一块
    assert "第1段" in chunks[0].content and "第5段" in chunks[0].content
    assert chunks[0].char_count <= 30


def test_chunk_empty_and_invalid():
    doc = ParsedDocument(title="空", source="empty.md", sections=(Section(None, 0, ""),))
    assert chunk_document(doc) == []

    doc = ParsedDocument(
        title="只有标题", source="headings.md",
        sections=(Section(heading="A", level=1, text=""),),
    )
    assert chunk_document(doc) == []  # 空小节不产生块

    with pytest.raises(ValueError, match="max_chars"):
        chunk_document(doc, max_chars=0)


def test_chunk_custom_doc_id(training_policy_path):
    """显式 doc_id 覆盖默认(向量库幂等替换的键)。"""
    doc = parse_document(training_policy_path)
    chunks = chunk_document(doc, doc_id="policy_v2")
    assert all(c.doc_id == "policy_v2" for c in chunks)
    assert all(c.chunk_id.startswith("policy_v2:") for c in chunks)
    # 引用展示仍使用文档标题,与 doc_id 无关
    assert chunks[0].citation.startswith("《企业员工培训管理制度》")
