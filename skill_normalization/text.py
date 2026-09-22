"""文本标准化:把同一技能的各种书写形式折叠为统一小写规范形。

处理流程(按顺序):
1. NFKC 归一:全角→半角(ＧｅｎＡＩ→GenAI)、兼容字符折叠;
2. 小写(对中文无影响);
3. 受保护技术词替换:C++→cplusplus、C#→csharp、.NET→dotnet 等,
   避免被当作标点/分隔符破坏;
4. 分隔符(- _ / \\ + & ,)统一为空格;
5. 删除其余标点;
6. 折叠空白;
7. 修剪领域通用前后缀(skill/skills/技术/技能/能力…);
8. 去除紧邻 CJK 字符的空白(「生成式 AI」→「生成式ai」、「机器 学习」→「机器学习」)。

输出供 Alias 精确匹配与 Embedding 编码使用;所有步骤幂等。
"""

from __future__ import annotations

import re
import unicodedata

# 归一化后修剪的领域通用前后缀(中英文)
_GENERIC_WORDS = frozenset({
    "skill", "skills", "ability", "abilities", "knowledge", "proficiency", "expertise",
    "技术", "技能", "能力", "知识", "经验",
})

# 受保护技术词:小写原文 → 替换形(替换形两侧加空格,防止粘连)
_PROTECTED_TOKENS: tuple[tuple[str, str], ...] = (
    ("c++", "cplusplus"),
    ("c#", "csharp"),
    ("f#", "fsharp"),
    (".net", "dotnet"),
    ("node.js", "nodejs"),
    ("vue.js", "vuejs"),
)

# 分隔符统一为空格
_SEPARATORS_RE = re.compile(r"[-_/\\+&,]+")
# 其余标点(保留字母数字、空白与 CJK)直接删除
_PUNCT_RE = re.compile(r"[^\w\s]")
# 折叠连续空白
_MULTI_SPACE_RE = re.compile(r"\s+")
# 紧邻 CJK 字符的空白(两侧任一侧是 CJK 即删除)
_CJK = r"\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff"
_CJK_ADJACENT_SPACE_RE = re.compile(rf"(?<=[{_CJK}])\s+|\s+(?=[{_CJK}])")


def _strip_generic_words(text: str) -> str:
    """修剪首尾的领域通用词,如「python skills」→「python」。"""
    tokens = text.split(" ") if text else []
    while tokens and tokens[0] in _GENERIC_WORDS:
        tokens.pop(0)
    while tokens and tokens[-1] in _GENERIC_WORDS:
        tokens.pop()
    return " ".join(tokens)


def normalize_text(text: str) -> str:
    """技能名称文本标准化(幂等)。

    >>> normalize_text("  ＧｅｎＡＩ ")
    'genai'
    >>> normalize_text("生成式 AI")
    '生成式ai'
    """
    if not text or not text.strip():
        return ""
    # 1. 全角→半角、兼容字符折叠
    s = unicodedata.normalize("NFKC", text)
    # 2. 小写
    s = s.lower()
    # 3. 受保护技术词(在标点/分隔符处理前替换)
    for token, replacement in _PROTECTED_TOKENS:
        s = s.replace(token, f" {replacement} ")
    # 4. 分隔符 → 空格
    s = _SEPARATORS_RE.sub(" ", s)
    # 5. 删除其余标点
    s = _PUNCT_RE.sub("", s)
    # 6. 折叠空白
    s = _MULTI_SPACE_RE.sub(" ", s).strip()
    # 7. 修剪领域通用前后缀(须在 CJK 粘连前,否则「docker 技术」会粘成一词)
    s = _strip_generic_words(s)
    # 8. 去除紧邻 CJK 的空白
    s = _CJK_ADJACENT_SPACE_RE.sub("", s)
    return s.strip()
