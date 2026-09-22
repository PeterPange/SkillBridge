"""文本标准化(normalize_text)单元测试。"""

import pytest

from skill_normalization.text import normalize_text


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # 大小写 / 空白折叠
        ("  Machine   Learning ", "machine learning"),
        ("PYTHON", "python"),
        # 分隔符与标点
        ("Machine-Learning", "machine learning"),
        ("machine_learning", "machine learning"),
        ("RAG/检索增强生成", "rag检索增强生成"),
        ("AI, Machine Learning", "ai machine learning"),
        ("generative-a.i.", "generative ai"),
        # 全角 → 半角(NFKC)
        ("ＧｅｎＡＩ", "genai"),
        ("ＳＱＬ查询", "sql查询"),
        # 受保护技术词
        ("C++", "cplusplus"),
        ("c#", "csharp"),
        (".NET", "dotnet"),
        ("Node.js", "nodejs"),
        # 领域通用前后缀修剪
        ("Python Skills", "python"),
        ("Docker 技术", "docker"),
        ("技能: Python", "python"),
        # CJK 邻接空白去除
        ("生成式 AI", "生成式ai"),
        ("机器 学习", "机器学习"),
        ("Python 编程", "python编程"),
        # 空输入
        ("", ""),
        ("   ", ""),
        ("技能", ""),
    ],
)
def test_normalize_text(raw, expected):
    assert normalize_text(raw) == expected


def test_normalize_text_is_idempotent():
    samples = ["ＧｅｎＡＩ", "生成式 AI", "  Machine-Learning  ", "技能: Python"]
    for s in samples:
        once = normalize_text(s)
        assert normalize_text(once) == once
