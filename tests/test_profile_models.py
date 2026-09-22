"""员工画像领域模型与构建器测试(大纲第五节,阶段 2B)。"""

import pytest

from profile import (
    EmployeeProfile,
    SkillEvidence,
    build_employee_profile,
    build_position_requirements,
)


def _skill(skill_id, level, *, evidence=None):
    return {
        "skill_id": skill_id,
        "level": level,
        "evidence": evidence
        or {
            "assessment_score": level * 22,
            "project_experience": "参与过项目" if level else "无相关项目经历",
            "self_assessment": level,
            "training_records": [f"{skill_id} 基础培训已完成"] if level else [],
        },
    }


def _employee(skills=None):
    return {
        "employee_id": "EMP_001",
        "name": "李明",
        "department": "研发中心",
        "current_position_id": "POS_001",
        "target_position_id": "POS_005",
        "years_of_experience": 3,
        "skills": skills if skills is not None else [_skill("SKILL_001", 2)],
    }


# ---------- 员工画像构建 ----------


def test_build_employee_profile_fields():
    profile = build_employee_profile(_employee([_skill("SKILL_001", 2)]))
    assert isinstance(profile, EmployeeProfile)
    assert profile.employee_id == "EMP_001"
    assert profile.name == "李明"
    assert profile.current_position_id == "POS_001"
    assert profile.target_position_id == "POS_005"
    assert profile.years_of_experience == 3


def test_level_of_returns_registered_level():
    profile = build_employee_profile(_employee([_skill("SKILL_001", 2)]))
    assert profile.level_of("SKILL_001") == 2
    assert profile.has_skill("SKILL_001")


def test_level_of_unregistered_skill_is_zero():
    """未登记技能(如后端员工的 RAG)按 Level 0 处理(大纲第六节)。"""
    profile = build_employee_profile(_employee([_skill("SKILL_001", 2)]))
    assert profile.level_of("SKILL_008") == 0
    assert not profile.has_skill("SKILL_008")
    assert profile.assessment_of("SKILL_008") is None


def test_profile_to_dict_roundtrip():
    record = _employee(
        [_skill("SKILL_001", 2), _skill("SKILL_002", 4), _skill("SKILL_006", 0)]
    )
    profile = build_employee_profile(record)
    assert profile.to_dict() == record  # skills 已按 skill_id 排序
    # 再次构建应得到等价画像
    assert build_employee_profile(profile.to_dict()) == profile


def test_level_zero_skill_kept_with_evidence():
    """Level 0 技能同样登记(带「无证据」形态),不丢失。"""
    profile = build_employee_profile(_employee([_skill("SKILL_006", 0)]))
    assert profile.has_skill("SKILL_006")
    assert profile.level_of("SKILL_006") == 0
    evidence = profile.assessment_of("SKILL_006").evidence
    assert evidence.assessment_score == 0
    assert evidence.training_records == ()


# ---------- Evidence 校验 ----------


def test_evidence_from_dict_roundtrip():
    data = {
        "assessment_score": 65,
        "project_experience": "有 Python 项目",
        "self_assessment": 2,
        "training_records": ["Python 基础已完成"],
    }
    evidence = SkillEvidence.from_dict(data)
    assert evidence.to_dict() == data
    assert isinstance(evidence.training_records, tuple)


def test_evidence_missing_field_rejected():
    data = {
        "assessment_score": 65,
        "project_experience": "有项目",
        "self_assessment": 2,
        # 缺 training_records
    }
    with pytest.raises(ValueError, match="training_records"):
        SkillEvidence.from_dict(data)


def test_evidence_out_of_range_rejected():
    base = {
        "assessment_score": 65,
        "project_experience": "有项目",
        "self_assessment": 2,
        "training_records": [],
    }
    with pytest.raises(ValueError, match="考试分数"):
        SkillEvidence.from_dict({**base, "assessment_score": 101})
    with pytest.raises(ValueError, match="员工自评"):
        SkillEvidence.from_dict({**base, "self_assessment": 5})


def test_employee_level_out_of_range_rejected():
    with pytest.raises(ValueError, match="0-4"):
        build_employee_profile(_employee([_skill("SKILL_001", 5)]))


def test_duplicate_skill_rejected():
    with pytest.raises(ValueError, match="重复技能"):
        build_employee_profile(
            _employee([_skill("SKILL_001", 2), _skill("SKILL_001", 3)])
        )


def test_unknown_skill_id_rejected():
    with pytest.raises(ValueError, match="未知技能"):
        build_employee_profile(_employee([_skill("SKILL_999", 2)]))


# ---------- 岗位要求构建 ----------


def test_build_position_requirements_enriched_from_skilllib():
    position = {
        "position_id": "POS_005",
        "name": "AI Engineer",
        "skills": [
            {"skill_id": "SKILL_001", "importance": 5.0, "required_level": 3},
        ],
    }
    requirements = build_position_requirements(position)
    assert len(requirements) == 1
    requirement = requirements[0]
    assert requirement.skill_id == "SKILL_001"
    assert requirement.skill_name == "Python"  # skilllib 补全
    assert requirement.category == "programming-language"
    assert requirement.importance == 5.0
    assert requirement.required_level == 3


def test_position_unknown_skill_rejected():
    position = {
        "position_id": "POS_005",
        "name": "AI Engineer",
        "skills": [
            {"skill_id": "SKILL_999", "importance": 5.0, "required_level": 3},
        ],
    }
    with pytest.raises(ValueError, match="未知技能"):
        build_position_requirements(position)


def test_position_importance_out_of_range_rejected():
    position = {
        "position_id": "POS_005",
        "name": "AI Engineer",
        "skills": [
            {"skill_id": "SKILL_001", "importance": 5.5, "required_level": 3},
        ],
    }
    with pytest.raises(ValueError, match="重要度"):
        build_position_requirements(position)


def test_position_required_level_out_of_range_rejected():
    position = {
        "position_id": "POS_005",
        "name": "AI Engineer",
        "skills": [
            {"skill_id": "SKILL_001", "importance": 5.0, "required_level": 4},
        ],
    }
    # 4 合法;5 越界
    assert build_position_requirements(position)[0].required_level == 4
    position["skills"][0]["required_level"] = 5
    with pytest.raises(ValueError, match="岗位要求等级"):
        build_position_requirements(position)
