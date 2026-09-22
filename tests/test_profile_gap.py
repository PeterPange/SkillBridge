"""Skill Gap 纯算法计算测试(大纲第六节,阶段 2B 验收)。

验收用例即大纲第六节的示例:员工李明 vs AI Engineer 岗位——

    Python +1 / Machine Learning +1 / Generative AI +3 /
    AI Agent +3 / Deployment +1 / Monitoring +1
"""

import json

import pytest

from conftest import outline_skill
from data.collect import ESCO_QUERIES, ONET_CODES
from data.employees import generate_employees
from data import positions as positions_mod
from data.sources import esco as esco_source
from data.sources import onet as onet_source
from profile import (
    build_employee_profile,
    build_gap_report,
    build_position_requirements,
    calculate_skill_gaps,
)


# ---------- 验收:大纲第六节示例 ----------


def test_acceptance_outline_gap_list(outline_employee, outline_position):
    """验收:李明 vs AI Engineer 输出正确的 Gap 列表。"""
    profile = build_employee_profile(outline_employee)
    report = build_gap_report(profile, outline_position)

    # 大纲:GenAI +3 / AI Agent +3 / Python +1 / ML +1 / Deployment +1 / Monitoring +1
    # 排序:差距降序 → 重要度降序 → skill_id 升序
    assert [(gap.skill_id, gap.gap) for gap in report.gaps] == [
        ("SKILL_006", 3),  # Generative AI      +3
        ("SKILL_009", 3),  # AI Agent           +3
        ("SKILL_001", 1),  # Python             +1
        ("SKILL_004", 1),  # Machine Learning   +1
        ("SKILL_011", 1),  # Deployment(Docker) +1
        ("SKILL_015", 1),  # Monitoring         +1
    ]


def test_acceptance_outline_gap_details(outline_employee, outline_position):
    """每项差距携带当前等级 / 要求等级 / 重要度等结构化字段。"""
    profile = build_employee_profile(outline_employee)
    report = build_gap_report(profile, outline_position)
    by_id = {gap.skill_id: gap for gap in report.gaps}

    genai = by_id["SKILL_006"]
    assert genai.skill_name == "Generative AI"
    assert genai.category == "ai-ml"
    assert genai.current_level == 0
    assert genai.required_level == 3
    assert genai.importance == 5.0
    assert genai.gap_ratio == 1.0
    assert genai.weighted_gap == 15.0

    python = by_id["SKILL_001"]
    assert (python.current_level, python.required_level) == (2, 3)
    assert python.gap_ratio == pytest.approx(1 / 3)
    assert python.weighted_gap == 5.0


def test_acceptance_outline_report_summary(outline_employee, outline_position):
    """报告汇总:缺失数 / 总差距 / 加权差距 / 准备度。"""
    profile = build_employee_profile(outline_employee)
    report = build_gap_report(profile, outline_position)

    assert report.missing_count == 6
    assert report.total_gap == 3 + 3 + 1 + 1 + 1 + 1
    assert report.weighted_total_gap == 15 + 15 + 5 + 4 + 3 + 3
    # 准备度 = Σ min(当前, 要求)×重要度 / Σ 要求×重要度 = 20 / 65
    assert report.readiness == pytest.approx(20 / 65)
    # 大纲示例中六项要求全部存在差距 → 无已达标项
    assert report.met == ()
    # Java / SQL 是岗位未要求的额外技能
    assert [(extra.skill_id, extra.level) for extra in report.extra_skills] == [
        ("SKILL_002", 4),
        ("SKILL_003", 3),
    ]


def test_acceptance_outline_report_json_serializable(outline_employee, outline_position):
    """结构化报告可 JSON 序列化(供推荐模块与 Agent 工具消费)。"""
    profile = build_employee_profile(outline_employee)
    report = build_gap_report(profile, outline_position)
    payload = report.to_dict()

    json.dumps(payload, ensure_ascii=False)  # 不抛异常即可

    assert payload["employee"]["employee_id"] == "EMP_001"
    assert payload["target_position"]["name"] == "AI Engineer"
    assert payload["summary"]["missing_count"] == 6
    assert payload["summary"]["total_gap"] == 10
    assert [gap["skill_id"] for gap in payload["gaps"]] == [
        "SKILL_006", "SKILL_009", "SKILL_001", "SKILL_004", "SKILL_011", "SKILL_015",
    ]
    assert payload["gaps"][0] == {
        "skill_id": "SKILL_006",
        "skill_name": "Generative AI",
        "category": "ai-ml",
        "current_level": 0,
        "required_level": 3,
        "gap": 3,
        "gap_ratio": 1.0,
        "importance": 5.0,
        "weighted_gap": 15.0,
    }


# ---------- 算法边界 ----------


def _profile_with_skills(skills: dict[str, int]):
    """构造仅含指定技能等级的员工画像。"""
    return build_employee_profile(
        {
            "employee_id": "EMP_001",
            "name": "李明",
            "department": "研发中心",
            "current_position_id": "POS_001",
            "target_position_id": "POS_005",
            "years_of_experience": 3,
            "skills": [
                outline_skill(skill_id, level)
                for skill_id, level in sorted(skills.items())
            ],
        }
    )


def test_unregistered_skill_counts_as_level_zero():
    """岗位要求 RAG 3 级,员工未登记 RAG → 当前 0、差距 3。"""
    profile = _profile_with_skills({"SKILL_001": 3})
    requirements = build_position_requirements(
        {
            "position_id": "POS_005",
            "name": "AI Engineer",
            "skills": [
                {"skill_id": "SKILL_008", "importance": 5.0, "required_level": 3},
            ],
        }
    )
    gaps = calculate_skill_gaps(profile, requirements)
    assert len(gaps) == 1
    assert gaps[0].current_level == 0
    assert gaps[0].gap == 3


def test_overqualified_skill_not_in_gaps_but_in_met():
    """当前等级超过岗位要求 → 不进差距,进已达标列表。"""
    profile = _profile_with_skills({"SKILL_011": 4})
    report = build_gap_report(
        profile,
        {
            "position_id": "POS_005",
            "name": "AI Engineer",
            "skills": [
                {"skill_id": "SKILL_011", "importance": 3.0, "required_level": 2},
            ],
        },
    )
    assert report.gaps == ()
    assert report.missing_count == 0
    assert report.total_gap == 0
    assert [
        (met.skill_id, met.current_level, met.required_level) for met in report.met
    ] == [("SKILL_011", 4, 2)]
    assert report.readiness == 1.0


def test_empty_requirements_yield_no_gaps():
    assert calculate_skill_gaps(_profile_with_skills({"SKILL_001": 2}), []) == []


def test_zero_required_level_ignored():
    """要求等级 0 的技能既不构成差距,也不计入已达标。"""
    profile = _profile_with_skills({"SKILL_001": 2})
    report = build_gap_report(
        profile,
        {
            "position_id": "POS_005",
            "name": "AI Engineer",
            "skills": [
                {"skill_id": "SKILL_001", "importance": 3.0, "required_level": 0},
            ],
        },
    )
    assert report.gaps == ()
    assert report.met == ()
    assert report.readiness == 1.0  # 无有效要求 → 准备度 1.0


def test_sorting_gap_desc_then_importance_desc_then_id():
    """排序:差距降序 → 重要度降序 → skill_id 升序(确定性)。"""
    profile = _profile_with_skills({"SKILL_001": 0})
    requirements = build_position_requirements(
        {
            "position_id": "POS_005",
            "name": "AI Engineer",
            "skills": [
                # 差距全部为 1:按重要度降序
                {"skill_id": "SKILL_015", "importance": 3.0, "required_level": 1},
                {"skill_id": "SKILL_004", "importance": 4.0, "required_level": 1},
                {"skill_id": "SKILL_001", "importance": 5.0, "required_level": 1},
                # 差距 2:排最前;重要度相同 → skill_id 升序
                {"skill_id": "SKILL_009", "importance": 4.0, "required_level": 2},
                {"skill_id": "SKILL_006", "importance": 4.0, "required_level": 2},
            ],
        }
    )
    gaps = calculate_skill_gaps(profile, requirements)
    assert [gap.skill_id for gap in gaps] == [
        "SKILL_006",  # 差距 2,重要度 4.0
        "SKILL_009",  # 差距 2,重要度 4.0(同差距同重要度 → id 升序)
        "SKILL_001",  # 差距 1,重要度 5.0
        "SKILL_004",  # 差距 1,重要度 4.0
        "SKILL_015",  # 差距 1,重要度 3.0
    ]


# ---------- 真实数据管线集成(fixture 岗位 + 生成器员工)----------


def _fixture_positions(tmp_path):
    """离线构建岗位数据(内置 fixture,不联网)。"""
    esco_raw, _ = esco_source.load_esco(ESCO_QUERIES, raw_dir=tmp_path, offline=True)
    onet_raw, _ = onet_source.load_onet(ONET_CODES, raw_dir=tmp_path, offline=True)
    return positions_mod.build_positions(
        esco_source.parse_esco_positions(esco_raw),
        onet_source.parse_onet_positions(onet_raw),
    )


def test_real_pipeline_li_ming_vs_ai_engineer(tmp_path):
    """端到端:生成器员工(李明,seed 42)vs fixture 构建的 AI Engineer 岗位。"""
    positions = {p["position_id"]: p for p in _fixture_positions(tmp_path)}
    employees = generate_employees(seed=42)
    li = employees[0]
    assert li["name"] == "李明"

    profile = build_employee_profile(li)
    report = build_gap_report(profile, positions["POS_005"])

    levels = {s["skill_id"]: s["level"] for s in li["skills"]}
    required = {s["skill_id"]: s["required_level"] for s in positions["POS_005"]["skills"]}

    # 不变量:每项差距 = 岗位要求等级 - 员工当前等级(未登记按 0),且 > 0
    for gap in report.gaps:
        assert gap.gap == required[gap.skill_id] - levels.get(gap.skill_id, 0)
        assert gap.gap > 0

    # 每项有效要求要么在差距列表、要么在已达标列表
    covered = {gap.skill_id for gap in report.gaps} | {met.skill_id for met in report.met}
    effective = {sid for sid, level in required.items() if level > 0}
    assert covered == effective

    # 李明未登记 LLM / RAG / AI Governance → 差距 = 岗位要求
    for skill_id in ("SKILL_007", "SKILL_008", "SKILL_018"):
        assert skill_id not in levels
        gap = next(g for g in report.gaps if g.skill_id == skill_id)
        assert gap.current_level == 0
        assert gap.gap == required[skill_id]

    # 后端出身的李明:GenAI / AI Agent 基础为 0(±1 扰动),缺口至少 2 级
    genai = next(g for g in report.gaps if g.skill_id == "SKILL_006")
    agent = next(g for g in report.gaps if g.skill_id == "SKILL_009")
    assert genai.gap >= 2
    assert agent.gap >= 2

    # 准备度在 0-1 之间
    assert 0 <= report.readiness <= 1

    # 可复现:同一份数据重算结果一致
    report_again = build_gap_report(build_employee_profile(li), positions["POS_005"])
    assert report_again == report


def test_real_pipeline_all_ten_employees(tmp_path):
    """全部 10 名模拟员工均可产出合法报告(数据管线兼容性)。"""
    positions = {p["position_id"]: p for p in _fixture_positions(tmp_path)}
    for employee in generate_employees(seed=42):
        profile = build_employee_profile(employee)
        report = build_gap_report(profile, positions[profile.target_position_id])
        assert 0 <= report.readiness <= 1
        assert report.missing_count == len(report.gaps)
        json.dumps(report.to_dict(), ensure_ascii=False)
