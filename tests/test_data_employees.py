"""模拟员工生成器测试(大纲第二节员工数据 + 第五节 Evidence)。"""

import random

from data import skilllib
from data.employees import (
    MAX_LEVEL,
    TARGET_POSITION_ID,
    _jitter_level,
    generate_employees,
)

EVIDENCE_FIELDS = (
    "assessment_score",
    "project_experience",
    "self_assessment",
    "training_records",
)


def test_generates_ten_employees():
    employees = generate_employees()
    assert len(employees) == 10
    assert [e["employee_id"] for e in employees] == [
        f"EMP_{i:03d}" for i in range(1, 11)
    ]


def test_deterministic_with_same_seed():
    assert generate_employees(seed=42) == generate_employees(seed=42)


def test_different_seed_changes_data():
    a = generate_employees(seed=1)
    b = generate_employees(seed=2)
    levels_a = [s["level"] for e in a for s in e["skills"]]
    levels_b = [s["level"] for e in b for s in e["skills"]]
    assert levels_a != levels_b, "不同种子应产生不同的技能等级扰动"


def test_all_skills_have_evidence():
    for employee in generate_employees():
        for skill in employee["skills"]:
            evidence = skill["evidence"]
            for field in EVIDENCE_FIELDS:
                assert field in evidence, f"{employee['name']} {skill['skill_id']} 缺 {field}"


def test_levels_within_0_to_4():
    for employee in generate_employees(seed=7):
        for skill in employee["skills"]:
            assert 0 <= skill["level"] <= MAX_LEVEL
            # 自评同样应在 0-4
            assert 0 <= skill["evidence"]["self_assessment"] <= MAX_LEVEL
            assert 0 <= skill["evidence"]["assessment_score"] <= 100


def test_assessment_score_correlates_with_level():
    """等级越高,考试分数区间越高(允许噪声但不允许倒挂)。"""
    employees = generate_employees(seed=42)
    scores = {
        (s["level"], s["evidence"]["assessment_score"])
        for e in employees
        for s in e["skills"]
    }
    max_l2 = max(sc for lv, sc in scores if lv == 2)
    min_l3 = min(sc for lv, sc in scores if lv == 3)
    assert max_l2 < min_l3


def test_skill_ids_are_known_to_registry():
    known = set(skilllib.all_skill_ids())
    for employee in generate_employees():
        assert {s["skill_id"] for s in employee["skills"]} <= known


def test_all_target_ai_engineer():
    for employee in generate_employees():
        assert employee["target_position_id"] == TARGET_POSITION_ID
        assert employee["current_position_id"] != TARGET_POSITION_ID


def test_backend_archetype_signature():
    """后端员工:Java 强、生成式 AI / Agent 弱(贴合转型场景)。"""
    li = generate_employees(seed=42)[0]
    assert li["name"] == "李明"
    skills = {s["skill_id"]: s["level"] for s in li["skills"]}
    assert skills["SKILL_002"] >= 3  # Java
    assert skills["SKILL_006"] <= 1  # Generative AI
    assert skills["SKILL_009"] <= 1  # AI Agent


def test_zero_level_evidence_shape():
    """Level 0 技能:无考试、无项目、无培训记录。"""
    employees = generate_employees(seed=42)
    zeros = [s for e in employees for s in e["skills"] if s["level"] == 0]
    assert zeros, "10 名员工中应存在 Level 0 技能"
    for skill in zeros:
        assert skill["evidence"]["assessment_score"] == 0
        assert skill["evidence"]["training_records"] == []


def test_count_parameter_limits_output():
    assert len(generate_employees(seed=42, count=3)) == 3


def test_jitter_stays_within_one_level_of_base():
    """随机扰动不超过基础等级 ±1,且不越界。"""
    rng = random.Random(0)
    for base in (0, 2, 4):
        for _ in range(100):
            jittered = _jitter_level(rng, base)
            assert abs(jittered - base) <= 1
            assert 0 <= jittered <= MAX_LEVEL
