"""文档解析测试(大纲第九节:PDF / Word / Markdown → 标题小节)。

- Markdown:原生解析,无外部依赖,覆盖标题层级 / 导语 / 代码块;
- Word:用 python-docx 现场生成 .docx fixture 后解析;
- PDF:手工构造最小合法 PDF(纯 ASCII 文本流)后用 pypdf 解析,
  中文标题规则用 ``_is_pdf_heading`` 纯函数直接覆盖。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rag.reader import (
    _is_pdf_heading,
    _pdf_heading_level,
    parse_docx,
    parse_document,
    parse_markdown,
    parse_pdf,
)

# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

MARKDOWN_TEXT = """前言:本文档用于测试导语小节。

# 企业培训制度

## 第一章 总则

第一条 为建立员工能力发展体系,特制定本制度。

## 第二章 入职培训

### 2.1 导师制度

新员工由部门指定一名导师。

```python
# 这行井号是代码,不是标题
code = "block"
```

### 2.2 考核

入职培训期结束进行转正考核。
"""


def test_parse_markdown_headings_and_preamble():
    doc = parse_markdown(MARKDOWN_TEXT, source="policy.md")
    assert doc.title == "企业培训制度"  # 首个标题 = 文档标题(不作为小节)
    headings = [(s.heading, s.level) for s in doc.sections]
    # 导语 + 两个二级 + 两个三级(代码块不产生小节)
    assert headings == [
        (None, 0),
        ("第一章 总则", 2),
        ("第二章 入职培训", 2),
        ("2.1 导师制度", 3),
        ("2.2 考核", 3),
    ]
    preamble = doc.sections[0]
    assert preamble.is_preamble
    assert "前言" in preamble.text

    # 代码块内容保留在小节正文里,井号行没有被当成标题
    mentor = next(s for s in doc.sections if s.heading == "2.1 导师制度")
    assert "# 这行井号是代码,不是标题" in mentor.text


def test_parse_markdown_title_fallbacks(tmp_path):
    # 无一级标题:首个任意层级标题作为文档标题(同样不作为小节)
    doc = parse_markdown("## 唯一标题\n正文", source="a.md")
    assert doc.title == "唯一标题"
    assert doc.sections[0].is_preamble
    assert doc.sections[0].text == "正文"
    # 完全无标题 → 回退文件名主干
    doc = parse_markdown("只有正文,没有标题。", source=str(tmp_path / "培训手册.md"))
    assert doc.title == "培训手册"
    assert doc.sections[0].is_preamble


def test_parse_markdown_empty_text():
    doc = parse_markdown("", source="empty.md")
    assert doc.title == "empty"
    assert len(doc.sections) == 1
    assert not doc.sections[0].text


def test_parse_document_dispatch(tmp_path, training_policy_path):
    # .md 走 Markdown 解析
    doc = parse_document(training_policy_path)
    assert doc.title == "企业员工培训管理制度"
    assert doc.source == str(training_policy_path)
    assert any(s.heading == "第二章 新员工入职培训" for s in doc.sections)

    # .txt 走纯文本:整篇一个导语小节
    txt = tmp_path / "notes.txt"
    txt.write_text("普通文本第一行。\n普通文本第二行。", encoding="utf-8")
    doc = parse_document(txt)
    assert len(doc.sections) == 1
    assert doc.sections[0].is_preamble
    assert "普通文本第一行" in doc.sections[0].text


def test_parse_document_errors(tmp_path):
    with pytest.raises(FileNotFoundError, match="不存在"):
        parse_document(tmp_path / "missing.md")
    unsupported = tmp_path / "doc.doc"
    unsupported.write_bytes(b"\xd0\xcf")  # 旧版 Word 二进制
    with pytest.raises(ValueError, match="docx"):
        parse_document(unsupported)
    other = tmp_path / "data.csv"
    other.write_text("a,b\n1,2", encoding="utf-8")
    with pytest.raises(ValueError, match="不支持的文档类型"):
        parse_document(other)


# ---------------------------------------------------------------------------
# Word(.docx)
# ---------------------------------------------------------------------------

def test_parse_docx(tmp_path):
    pytest.importorskip("docx")
    import docx as docx_lib

    path = tmp_path / "岗位说明书.docx"
    document = docx_lib.Document()
    document.add_heading("AI Engineer 岗位说明书", level=1)
    document.add_paragraph("本说明书界定 AI Engineer 岗位的职责与能力要求。")
    document.add_heading("岗位职责", level=2)
    document.add_paragraph("负责 RAG 系统的设计与落地。")
    document.add_heading("能力要求", level=2)
    document.add_paragraph("熟练掌握 Python 与向量数据库。")
    document.save(str(path))

    doc = parse_docx(path)
    assert doc.title == "AI Engineer 岗位说明书"  # 首个标题 = 文档标题
    assert [(s.heading, s.level) for s in doc.sections] == [
        (None, 0),  # 标题下的引言段 → 导语
        ("岗位职责", 2),
        ("能力要求", 2),
    ]
    assert "本说明书" in doc.sections[0].text
    duty = next(s for s in doc.sections if s.heading == "岗位职责")
    assert "RAG" in duty.text


def test_parse_document_docx_dispatch(tmp_path):
    pytest.importorskip("docx")
    import docx as docx_lib

    path = tmp_path / "员工手册.docx"
    document = docx_lib.Document()
    document.add_heading("员工手册", level=1)
    document.add_paragraph("欢迎加入公司。")
    document.save(str(path))

    doc = parse_document(path)
    assert doc.title == "员工手册"
    assert doc.source == str(path)


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

def _make_pdf(lines: list[str]) -> bytes:
    """手工构造单页最小合法 PDF(每行一个文本对象,Helvetica)。"""
    ops = []
    y = 720
    for line in lines:
        escaped = (
            line.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        )
        ops.append(f"BT /F1 12 Tf 72 {y} Td ({escaped}) Tj ET")
        y -= 24
    content = "\n".join(ops).encode("utf-8")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n"
        + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for i, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref}\n%%EOF"
    ).encode()
    return out


def test_parse_pdf(tmp_path):
    pytest.importorskip("pypdf")
    path = tmp_path / "policy.pdf"
    path.write_bytes(
        _make_pdf(
            [
                "Chapter 1 General Provisions",
                "This policy applies to all employees.",
                "Chapter 2 Onboarding Training",
                "The onboarding training period is three months.",
            ]
        )
    )
    doc = parse_pdf(path)
    # 首个标题行作为文档标题(不作为小节);其后的正文归入导语
    assert doc.title == "Chapter 1 General Provisions"
    assert [(s.heading, s.level) for s in doc.sections] == [
        (None, 0),
        ("Chapter 2 Onboarding Training", 1),
    ]
    assert "This policy applies" in doc.sections[0].text
    onboarding = doc.sections[1]
    assert "three months" in onboarding.text


def test_parse_document_pdf_dispatch(tmp_path):
    pytest.importorskip("pypdf")
    path = tmp_path / "policy.pdf"
    path.write_bytes(_make_pdf(["Section 1 Scope", "All employees are covered."]))
    doc = parse_document(path)
    assert doc.title == "Section 1 Scope"
    assert "All employees" in doc.sections[0].text


def test_pdf_heading_heuristics():
    """中文标题规则(纯函数级覆盖,不需要真实 PDF)。"""
    # 命中:章节序号 / 中文序号 / 数字编号
    assert _is_pdf_heading("第二章 新员工入职培训")
    assert _is_pdf_heading("一、总则")
    assert _is_pdf_heading("(三) 培训考核")
    assert _is_pdf_heading("2.1 导师制度")
    assert _is_pdf_heading("1.1导师制度")  # 编号后无空格也应识别
    assert _is_pdf_heading("Chapter 3 Reimbursement")
    # 不命中:句末标点 / 超长 / 无编号的正文
    assert not _is_pdf_heading("新员工入职培训期为三个月。")
    assert not _is_pdf_heading("培训学时要求为每年40学时;")
    assert not _is_pdf_heading("这是一段没有句末标点但是长度明显超过六十个字符上限的正文行,不应被识别为标题")
    assert not _is_pdf_heading("普通正文行,没有编号")
    assert not _is_pdf_heading("")

    # 层级估算:章 = 1,数字编号按点号深度
    assert _pdf_heading_level("第三章 在职培训") == 1
    assert _pdf_heading_level("1. 总则") == 1
    assert _pdf_heading_level("2.1 导师制度") == 2
    assert _pdf_heading_level("一、总则") == 2
