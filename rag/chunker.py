"""标题级分块:解析后的文档 → 带溯源信息的分块序列。

大纲第九节流程「文档解析 → 标题级分块」的第二步。策略:

- **以小节为单位**:每个标题小节至少独立成块,块携带完整标题路径
  (如 ``第二章 入职培训 > 2.1 导师制度``),引用溯源精确到节;
- **超长小节按段落边界切分**:段落贪心装箱到 ``max_chars`` 为止,
  单段超过上限再按句子边界硬切,最后按字符兜底;
- **短小节不跨标题合并**:相邻小节即使很短也不合并,
  保证每块只属于一个标题(引用不歧义)。

纯函数实现,不依赖 Embedding 与数据库,便于固定 fixture 单测。
"""

from __future__ import annotations

import re

from rag.models import Chunk, ParsedDocument, Section

#: 单块目标最大字符数(中文约 500-800 token 语义完整性最好)。
DEFAULT_MAX_CHARS = 800

#: 段落分隔:一个及以上空行。
_PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n+")
#: 句子边界(保留句末标点)。
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[。!?!?;;])")


def chunk_document(
    doc: ParsedDocument,
    *,
    doc_id: str | None = None,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> list[Chunk]:
    """把解析后的文档按标题级分块。

    :param doc: :func:`rag.reader.parse_document` 的输出;
    :param doc_id: 文档 ID(向量库幂等替换的键),默认取文档标题;
    :param max_chars: 单块最大字符数;
    :return: 按原文顺序排列的分块列表(空文档返回空列表);
    :raises ValueError: ``max_chars`` 非正。
    """
    if max_chars <= 0:
        raise ValueError(f"max_chars 必须为正数,收到 {max_chars}")
    resolved_doc_id = doc_id or doc.title
    chunks: list[Chunk] = []
    stack: list[tuple[int, str]] = []  # (level, heading) 标题层级栈

    for section in doc.sections:
        heading_path = _push_heading(stack, section)
        if not section.text:
            continue  # 空小节:只维护层级栈,不产生分块
        for piece in _split_section_text(section.text, max_chars):
            chunks.append(
                Chunk(
                    chunk_id=f"{resolved_doc_id}:{len(chunks):04d}",
                    doc_id=resolved_doc_id,
                    doc_title=doc.title,
                    source=doc.source,
                    heading_path=heading_path,
                    chunk_index=len(chunks),
                    content=piece,
                )
            )
    return chunks


# ---------------------------------------------------------------------------
# 内部实现
# ---------------------------------------------------------------------------

def _push_heading(stack: list[tuple[int, str]], section: Section) -> tuple[str, ...]:
    """把小节标题压入层级栈,返回从文档根到本节的标题路径。

    层级回退规则:新标题层级 ≤ 栈顶层级时弹栈(同级替换、回退上级),
    与 Markdown / Word 标题语义一致;导语小节(level 0)清空整个栈。
    """
    if section.is_preamble:
        stack.clear()
        return ()
    while stack and stack[-1][0] >= section.level:
        stack.pop()
    stack.append((section.level, section.heading or ""))
    return tuple(heading for _, heading in stack)


def _split_section_text(text: str, max_chars: int) -> list[str]:
    """小节正文 → 块文本列表:段落贪心装箱,超长段落按句子硬切。"""
    paragraphs = [_normalize_paragraph(p) for p in _PARAGRAPH_SPLIT_RE.split(text)]
    paragraphs = [p for p in paragraphs if p]

    pieces: list[str] = []
    buffer: list[str] = []
    buffer_chars = 0
    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            # 超长段落:先落盘缓冲区,再按句子切分
            _flush_buffer(pieces, buffer)
            pieces.extend(_split_long_paragraph(paragraph, max_chars))
            continue
        if buffer_chars and buffer_chars + 1 + len(paragraph) > max_chars:
            _flush_buffer(pieces, buffer)
        buffer.append(paragraph)
        buffer_chars = len("\n".join(buffer))
    _flush_buffer(pieces, buffer)
    return pieces


def _flush_buffer(pieces: list[str], buffer: list[str]) -> None:
    if buffer:
        pieces.append("\n".join(buffer))
        buffer.clear()


def _normalize_paragraph(paragraph: str) -> str:
    """段落内部整理:折叠换行与连续空白为单个空格。"""
    return " ".join(paragraph.split())


def _split_long_paragraph(paragraph: str, max_chars: int) -> list[str]:
    """超过 ``max_chars`` 的段落:按句子边界切分,单句超长再按字符切。"""
    sentences = [s for s in _SENTENCE_SPLIT_RE.split(paragraph) if s]
    pieces: list[str] = []
    buffer = ""
    for sentence in sentences:
        if len(sentence) > max_chars:
            if buffer:
                pieces.append(buffer)
                buffer = ""
            for i in range(0, len(sentence), max_chars):
                pieces.append(sentence[i : i + max_chars])
            continue
        if buffer and len(buffer) + len(sentence) > max_chars:
            pieces.append(buffer)
            buffer = ""
        buffer = buffer + sentence if buffer else sentence
    if buffer:
        pieces.append(buffer)
    return pieces
