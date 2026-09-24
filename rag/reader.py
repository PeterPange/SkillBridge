"""文档解析:PDF / Word / Markdown / 纯文本 → 标题小节序列。

统一输出 :class:`rag.models.ParsedDocument`(标题 + 小节列表),
供 :func:`rag.chunker.chunk_document` 做标题级分块。

统一规则:**文档的首个标题视为文档标题**(元数据,不作为小节),
其后的正文归入导语小节;没有任何标题时标题回退文件名主干。
这样标题路径从正文一级标题开始,引用不会与文档标题重复。

- **Markdown**:原生解析 ATX 标题(``#`` ~ ``######``),正确跳过代码块;
- **Word(.docx)**:python-docx 按段落样式识别标题
  (``Heading N`` / 中文 Word 的 ``标题 N``);
- **PDF**:pypdf 逐页抽取文本行,按「编号/章节模式 + 短行 + 无句末标点」
  启发式识别标题行(PDF 无结构信息,标题识别为最佳努力);
- **纯文本(.txt)**:无标题,整篇作为一个导语小节。

可选依赖缺失(pypdf / python-docx 未安装)时抛出带安装提示的
``ImportError``,不静默降级——解析失败必须显式暴露,而不是把
整篇文档当成一个无标题块入库。
"""

from __future__ import annotations

import re
from pathlib import Path

from rag.models import ParsedDocument, Section

#: 支持的文档后缀(小写,含点号)。
SUPPORTED_SUFFIXES = (".md", ".markdown", ".docx", ".pdf", ".txt")

# --- Markdown ---
_ATX_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_CODE_FENCE_RE = re.compile(r"^(```|~~~)")

# --- PDF 标题启发式 ---
#: 标题行最长字符数:超过即视为正文。
PDF_HEADING_MAX_CHARS = 60
#: 标题行不允许出现的句末/句中强标点(出现即视为正文)。
_PDF_SENTENCE_PUNCT_RE = re.compile(r"[。;；!！?？]")
#: 中文序号标题:「第X章/节/篇/部分」「一、」「(一)」。
_PDF_CN_HEADING_RE = re.compile(
    r"^(第[一二三四五六七八九十百千0-9]+[章节篇部分]"
    r"|[一二三四五六七八九十]+、"
    r"|[（(][一二三四五六七八九十]+[）)])"
)
#: 数字编号标题:「1.」「1.1」「1.1.1」「1、」。
_PDF_NUM_HEADING_RE = re.compile(r"^\d+(\.\d+)*[、.．\s]")
#: 英文章节标题:「Chapter 1」「Section 2」「Article 3」。
_PDF_EN_HEADING_RE = re.compile(r"^(chapter|section|article)\s+\d+", re.IGNORECASE)

# --- Word 标题样式 ---
#: ``Heading 3`` / ``标题 3`` / ``heading 3`` → 层级 3。
_DOCX_HEADING_STYLE_RE = re.compile(r"^(?:heading|标题)\s*(\d+)$", re.IGNORECASE)


def parse_document(path: str | Path) -> ParsedDocument:
    """按扩展名分发解析:PDF / Word / Markdown / 纯文本 → ParsedDocument。

    :raises FileNotFoundError: 文件不存在;
    :raises ValueError: 不支持的扩展名(旧版 ``.doc`` 二进制格式同样报错,
        提示另存为 ``.docx``)。
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"文档不存在: {file_path}")
    suffix = file_path.suffix.lower()
    source = str(file_path)
    if suffix in (".md", ".markdown"):
        return parse_markdown(file_path.read_text(encoding="utf-8"), source=source)
    if suffix == ".docx":
        return parse_docx(file_path, source=source)
    if suffix == ".pdf":
        return parse_pdf(file_path, source=source)
    if suffix == ".txt":
        return parse_markdown(file_path.read_text(encoding="utf-8"), source=source)
    if suffix == ".doc":
        raise ValueError(
            f"不支持旧版 Word 二进制格式: {file_path}(请另存为 .docx 后重试)"
        )
    raise ValueError(
        f"不支持的文档类型: {file_path}(支持 {' / '.join(SUPPORTED_SUFFIXES)})"
    )


# ---------------------------------------------------------------------------
# Markdown / 纯文本
# ---------------------------------------------------------------------------

def parse_markdown(text: str, *, source: str = "<text>") -> ParsedDocument:
    """解析 Markdown 文本:ATX 标题切分小节,跳过围栏代码块。

    文档的**首个标题**视为文档标题(元数据,不作为小节),
    其后的正文归入导语小节;没有任何标题时回退 ``source`` 文件名主干。
    """
    sections: list[Section] = []
    title: str | None = None
    current_heading: str | None = None
    current_level = 0
    current_lines: list[str] = []
    in_fence = False
    fence_marker = ""

    def flush() -> None:
        sections.append(
            Section(heading=current_heading, level=current_level, text=_join_lines(current_lines))
        )
        current_lines.clear()

    for raw_line in text.splitlines():
        fence = _CODE_FENCE_RE.match(raw_line.strip())
        if fence:
            marker = fence.group(1)
            if not in_fence:
                in_fence, fence_marker = True, marker
            elif marker == fence_marker:
                in_fence, fence_marker = False, ""
            current_lines.append(raw_line)
            continue
        if not in_fence:
            heading_match = _ATX_HEADING_RE.match(raw_line)
            if heading_match:
                flush()
                level = len(heading_match.group(1))
                heading = heading_match.group(2).strip()
                if title is None:
                    # 首个标题 = 文档标题;其后正文归入导语
                    title = heading
                    current_heading, current_level = None, 0
                else:
                    current_heading, current_level = heading, level
                continue
        current_lines.append(raw_line)
    flush()

    return ParsedDocument(
        title=title or _stem(source),
        source=source,
        sections=tuple(_compact_sections(sections)),
    )


# ---------------------------------------------------------------------------
# Word(.docx)
# ---------------------------------------------------------------------------

def parse_docx(path: str | Path, *, source: str | None = None) -> ParsedDocument:
    """解析 .docx:按段落样式 ``Heading N`` / ``标题 N`` 识别标题层级。

    :raises ImportError: python-docx 未安装(提示 ``uv add python-docx``)。
    """
    try:
        import docx  # python-docx
    except ImportError as exc:  # pragma: no cover - 依赖缺失分支
        raise ImportError(
            "解析 Word 文档需要 python-docx(uv add python-docx)"
        ) from exc

    file_path = Path(path)
    document = docx.Document(str(file_path))
    src = source or str(file_path)

    sections: list[Section] = []
    title: str | None = None
    current_heading: str | None = None
    current_level = 0
    current_lines: list[str] = []

    def flush() -> None:
        sections.append(
            Section(heading=current_heading, level=current_level, text=_join_lines(current_lines))
        )
        current_lines.clear()

    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        style_name = (paragraph.style.name or "").strip()
        style_match = _DOCX_HEADING_STYLE_RE.match(style_name)
        if style_match:
            flush()
            level = int(style_match.group(1))
            if title is None:
                # 首个标题 = 文档标题(元数据,不作为小节)
                title = text
                current_heading, current_level = None, 0
            else:
                current_heading, current_level = text, level
            continue
        current_lines.append(text)
    flush()

    return ParsedDocument(
        title=title or _stem(src),
        source=src,
        sections=tuple(_compact_sections(sections)),
    )


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

def parse_pdf(path: str | Path, *, source: str | None = None) -> ParsedDocument:
    """解析 PDF:逐页抽取文本行,启发式识别标题行。

    PDF 没有结构信息,标题识别规则(全部满足才判为标题):

    - 行长 ≤ :data:`PDF_HEADING_MAX_CHARS`;
    - 不含句末强标点(。;!?等);
    - 命中中文序号 / 数字编号 / 英文章节模式之一。

    :raises ImportError: pypdf 未安装(提示 ``uv add pypdf``)。
    """
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - 依赖缺失分支
        raise ImportError("解析 PDF 文档需要 pypdf(uv add pypdf)") from exc

    file_path = Path(path)
    reader = PdfReader(str(file_path))
    src = source or str(file_path)

    lines: list[str] = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        lines.extend(line.strip() for line in page_text.splitlines() if line.strip())

    sections: list[Section] = []
    title: str | None = None
    current_heading: str | None = None
    current_level = 0
    current_lines: list[str] = []

    def flush() -> None:
        sections.append(
            Section(heading=current_heading, level=current_level, text=_join_lines(current_lines))
        )
        current_lines.clear()

    for line in lines:
        if _is_pdf_heading(line):
            flush()
            if title is None:
                # 首个标题行 = 文档标题(元数据,不作为小节)
                title = line
                current_heading, current_level = None, 0
            else:
                current_heading = line
                current_level = _pdf_heading_level(line)
            continue
        current_lines.append(line)
    flush()

    return ParsedDocument(
        title=title or _stem(src),
        source=src,
        sections=tuple(_compact_sections(sections)),
    )


def _is_pdf_heading(line: str) -> bool:
    """判断一行 PDF 文本是否为标题(见 :func:`parse_pdf` 的规则说明)。"""
    if not line or len(line) > PDF_HEADING_MAX_CHARS:
        return False
    if _PDF_SENTENCE_PUNCT_RE.search(line):
        return False
    return bool(
        _PDF_CN_HEADING_RE.match(line)
        or _PDF_NUM_HEADING_RE.match(line)
        or _PDF_EN_HEADING_RE.match(line)
    )


def _pdf_heading_level(line: str) -> int:
    """估算标题层级:「第X章」/「Chapter N」= 1,数字编号按点号深度,
    「一、」等中文序号 = 2。

    仅用于构建标题路径的相对层级,不影响小节切分本身。
    """
    if _PDF_EN_HEADING_RE.match(line):
        return 1
    if _PDF_CN_HEADING_RE.match(line) and line.startswith("第"):
        return 1
    if _PDF_NUM_HEADING_RE.match(line):
        digits = re.match(r"^\d+(\.\d+)*", line)
        if digits:
            return digits.group(0).count(".") + 1
    return 2


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------

def _join_lines(lines: list[str]) -> str:
    """把正文行合并为小节文本(去首尾空白行,保留中间换行)。"""
    return "\n".join(lines).strip("\n").strip()


def _compact_sections(sections: list[Section]) -> list[Section]:
    """去掉无正文的导语空小节(如文档以标题开头时产生的空导语)。

    保留无正文的标题小节:它们不产生分块,但维护标题层级栈,
    保证「# A → ## B(有正文)」的 B 块标题路径仍包含 A。
    """
    kept = [s for s in sections if s.heading is not None or s.text]
    if not kept and sections:
        return [sections[0]]  # 空文档:保留唯一空小节,由分块阶段报错
    return kept


def _stem(source: str) -> str:
    """来源路径的文件名主干(无标题文档的标题回退值)。"""
    try:
        return Path(source).stem or source
    except ValueError:  # source 含非法路径字符(如 <text>)
        return source
