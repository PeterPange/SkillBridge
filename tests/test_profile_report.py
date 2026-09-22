"""差距报告与 Evidence 解释的文本渲染测试(大纲第五、六节)。"""

from conftest import outline_skill
from profile import (
    build_employee_profile,
    build_gap_report,
    render_evidence_explanation,
    render_gap_report,
)


def _build(outline_employee, outline_position):
    profile = build_employee_profile(outline_employee)
    return profile, build_gap_report(
        profile,
        outline_position,
        current_position={"position_id": "POS_001", "name": "Software Developer"},
    )


def test_render_contains_header_and_gap_table(outline_employee, outline_position):
    _, report = _build(outline_employee, outline_position)
    text = render_gap_report(report)

    assert "李明" in text
    assert "Software Developer" in text  # 当前岗位名称
    assert "AI Engineer" in text
    # 缺失技能与差距值
    for skill_name in (
        "Generative AI", "AI Agent", "Python", "Machine Learning", "Monitoring",
    ):
        assert skill_name in text
    assert text.count("+3") == 2  # GenAI / AI Agent
    assert text.count("+1") == 4  # Python / ML / Docker / Monitoring
    # 汇总行
    assert "缺失技能(6 项,总差距 10 级" in text
    assert "已达标:0 项" in text
    assert "岗位准备度:30.8%" in text  # 20 / 65


def test_render_lists_extra_skills(outline_employee, outline_position):
    _, report = _build(outline_employee, outline_position)
    text = render_gap_report(report)
    assert "额外技能" in text
    assert "Java(4)" in text
    assert "SQL(3)" in text


def test_render_no_gap_report(outline_employee, outline_position):
    """完全达标时输出达标提示,不渲染表格。"""
    profile = build_employee_profile(outline_employee)
    # 要求全部低于当前等级 → 无差距
    position = {
        "position_id": "POS_005",
        "name": "AI Engineer",
        "skills": [
            {"skill_id": "SKILL_001", "importance": 5.0, "required_level": 1},
        ],
    }
    report = build_gap_report(profile, position)
    text = render_gap_report(report)
    assert "无缺失技能" in text
    assert "已达标(1 项):Python(2/1)" in text


def test_render_evidence_explanation(outline_employee):
    """大纲第五节:为什么认为你的 Python 是 Level 2?"""
    profile = build_employee_profile(outline_employee)
    text = render_evidence_explanation(
        profile, "SKILL_001", skill_name="Python"
    )
    lines = text.splitlines()
    assert lines[0] == "为什么认为你的 Python 是 Level 2?"
    assert "技能考试 : 44 分" in text
    assert "员工自评 : Level 2" in text
    assert "培训记录 : SKILL_001 基础培训已完成" in text


def test_render_evidence_explanation_zero_level(outline_employee):
    """Level 0 技能:无考试、无项目、无培训记录。"""
    profile = build_employee_profile(outline_employee)
    text = render_evidence_explanation(
        profile, "SKILL_006", skill_name="Generative AI"
    )
    assert "为什么认为你的 Generative AI 是 Level 0?" in text
    assert "技能考试 : 0 分" in text
    assert "培训记录 : 无" in text


def test_render_evidence_explanation_unregistered(outline_employee):
    """未登记技能:说明按 Level 0 处理。"""
    profile = build_employee_profile(outline_employee)
    text = render_evidence_explanation(profile, "SKILL_008", skill_name="RAG")
    assert "RAG" in text
    assert "Level 0" in text
