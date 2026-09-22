"""统一 JSON Schema 与跨文件校验测试(阶段 1A 验收:pytest 覆盖 schema 校验)。"""

import copy
import json
from pathlib import Path

import pytest

import data.schemas as schemas

FIXTURES = Path(__file__).resolve().parent.parent / "data" / "fixtures"


def _minimal_employee_skills() -> list[dict]:
    """构造 5 项技能(满足 schema 的 minItems=5)。"""
    base = [
        ("SKILL_001", 2, 50, "参与过项目", 2, ["基础培训已完成"]),
        ("SKILL_002", 0, 0, "无相关项目经历", 0, []),
        ("SKILL_003", 3, 70, "作为核心成员参与项目", 3, ["进阶培训已完成"]),
        ("SKILL_004", 1, 25, "完成过入门练习", 1, ["入门课程学习中"]),
        ("SKILL_011", 2, 48, "参与过项目", 2, ["基础培训已完成"]),
    ]
    return [
        {
            "skill_id": skill_id,
            "level": level,
            "evidence": {
                "assessment_score": score,
                "project_experience": project,
                "self_assessment": self_assessment,
                "training_records": records,
            },
        }
        for skill_id, level, score, project, self_assessment, records in base
    ]


def _minimal_docs() -> dict:
    """构造通过校验的最小数据集。"""
    return {
        "skills": {
            "generated_at": "2026-01-01T00:00:00+00:00",
            "skills": [
                {
                    "skill_id": skill_id,
                    "name": name,
                    "category": category,
                    "description": f"{name} 技能",
                    "aliases": [name.lower()],
                    "sources": sources,
                }
                for skill_id, name, category, sources in [
                    ("SKILL_001", "Python", "programming-language", ["curated"]),
                    ("SKILL_002", "Java", "programming-language", ["esco", "onet"]),
                    ("SKILL_003", "SQL", "database", ["curated"]),
                    ("SKILL_004", "Machine Learning", "ai-ml", ["curated"]),
                    ("SKILL_011", "Docker", "platform", ["onet"]),
                ]
            ],
        },
        "positions": {
            "generated_at": "2026-01-01T00:00:00+00:00",
            "positions": [
                {
                    "position_id": "POS_001",
                    "name": "Software Developer",
                    "description": "软件开发",
                    "responsibilities": ["开发软件"],
                    "sources": ["esco", "onet"],
                    "external_ids": {"onet_code": "15-1252.00"},
                    "skills": [
                        {
                            "skill_id": "SKILL_001",
                            "importance": 4.5,
                            "required_level": 3,
                            "sources": ["onet"],
                        },
                        {
                            "skill_id": "SKILL_002",
                            "importance": 3,
                            "required_level": 2,
                            "sources": ["esco"],
                        },
                        {
                            "skill_id": "SKILL_001",
                            "importance": 5,
                            "required_level": 4,
                            "sources": ["curated"],
                        },
                    ],
                }
            ],
        },
        "courses": {
            "generated_at": "2026-01-01T00:00:00+00:00",
            "courses": [
                {
                    "course_id": "CRS_001",
                    "uid": "learn.sample.a",
                    "name": "Course A",
                    "description": "基础课程",
                    "difficulty": "beginner",
                    "duration_minutes": 30,
                    "learning_objectives": ["理解基础概念"],
                    "skills": ["SKILL_001"],
                    "prerequisites": [],
                    "url": "https://learn.microsoft.com/en-us/training/modules/a/",
                    "source": "microsoft_learn",
                },
                {
                    "course_id": "CRS_002",
                    "uid": "learn.sample.b",
                    "name": "Course B",
                    "description": "进阶课程",
                    "difficulty": "intermediate",
                    "duration_minutes": 60,
                    "learning_objectives": ["构建应用"],
                    "skills": ["SKILL_002"],
                    "prerequisites": ["CRS_001"],
                    "url": "https://learn.microsoft.com/en-us/training/modules/b/",
                    "source": "microsoft_learn",
                },
            ],
        },
        "employees": {
            "generated_at": "2026-01-01T00:00:00+00:00",
            "seed": 42,
            "employees": [
                {
                    "employee_id": "EMP_001",
                    "name": "李明",
                    "department": "研发中心",
                    "current_position_id": "POS_001",
                    "target_position_id": "POS_001",
                    "years_of_experience": 3,
                    "skills": _minimal_employee_skills(),
                }
            ],
        },
    }


@pytest.fixture()
def docs():
    return _minimal_docs()


def test_minimal_docs_pass_all_validation(docs):
    assert schemas.validate_all(
        docs["skills"], docs["positions"], docs["courses"], docs["employees"]
    ) == []


def test_schema_files_are_valid_draft202012():
    import jsonschema

    for name, schema in schemas.SCHEMAS.items():
        jsonschema.Draft202012Validator.check_schema(schema)
        assert schema["$id"].endswith(f"{name}.schema.json")


# ------------------------------------------------------------- 单文件 Schema


def test_skill_level_out_of_range_rejected(docs):
    docs["employees"]["employees"][0]["skills"][0]["level"] = 5
    errors = schemas.validate_instance(docs["employees"], "employees")
    assert any("level" in e for e in errors)


def test_employee_missing_evidence_field_rejected(docs):
    del docs["employees"]["employees"][0]["skills"][0]["evidence"]["self_assessment"]
    errors = schemas.validate_instance(docs["employees"], "employees")
    assert errors


def test_course_invalid_difficulty_rejected(docs):
    docs["courses"]["courses"][0]["difficulty"] = "expert"
    errors = schemas.validate_instance(docs["courses"], "courses")
    assert errors


def test_course_bad_url_rejected(docs):
    docs["courses"]["courses"][0]["url"] = "not-a-url"
    errors = schemas.validate_instance(docs["courses"], "courses")
    assert errors


def test_position_importance_out_of_range_rejected(docs):
    docs["positions"]["positions"][0]["skills"][0]["importance"] = 6
    errors = schemas.validate_instance(docs["positions"], "positions")
    assert errors


def test_skill_id_pattern_rejected(docs):
    docs["skills"]["skills"][0]["skill_id"] = "SKILL_1"
    errors = schemas.validate_instance(docs["skills"], "skills")
    assert errors


def test_course_without_objectives_rejected(docs):
    docs["courses"]["courses"][0]["learning_objectives"] = []
    errors = schemas.validate_instance(docs["courses"], "courses")
    assert errors


# ------------------------------------------------------------- 跨文件引用


def test_unknown_skill_reference_rejected(docs):
    docs["positions"]["positions"][0]["skills"][0]["skill_id"] = "SKILL_999"
    errors = schemas.validate_referential(
        docs["skills"], docs["positions"], docs["courses"], docs["employees"]
    )
    assert any("SKILL_999" in e for e in errors)


def test_unknown_position_reference_rejected(docs):
    docs["employees"]["employees"][0]["current_position_id"] = "POS_999"
    errors = schemas.validate_referential(
        docs["skills"], docs["positions"], docs["courses"], docs["employees"]
    )
    assert any("POS_999" in e for e in errors)


def test_unknown_prerequisite_rejected(docs):
    docs["courses"]["courses"][1]["prerequisites"] = ["CRS_999"]
    errors = schemas.validate_referential(
        docs["skills"], docs["positions"], docs["courses"], docs["employees"]
    )
    assert any("CRS_999" in e for e in errors)


def test_prerequisite_cycle_rejected(docs):
    """A → B → A 的前置环必须被检出。"""
    docs["courses"]["courses"][0]["prerequisites"] = ["CRS_002"]
    docs["courses"]["courses"][1]["prerequisites"] = ["CRS_001"]
    errors = schemas.validate_referential(
        docs["skills"], docs["positions"], docs["courses"], docs["employees"]
    )
    assert any("环" in e for e in errors)


def test_self_prerequisite_rejected(docs):
    docs["courses"]["courses"][0]["prerequisites"] = ["CRS_001"]
    errors = schemas.validate_referential(
        docs["skills"], docs["positions"], docs["courses"], docs["employees"]
    )
    assert any("包含自身" in e for e in errors)


def test_duplicate_ids_rejected(docs):
    docs["skills"]["skills"].append(copy.deepcopy(docs["skills"]["skills"][0]))
    errors = schemas.validate_referential(
        docs["skills"], docs["positions"], docs["courses"], docs["employees"]
    )
    assert any("重复" in e for e in errors)


# ------------------------------------------------------------- 真实 fixture 自检


def test_bundled_objectives_fixture_covers_all_curriculum():
    """fixture 学习目标必须覆盖全部策展课程(离线模式不缺数据)。"""
    from data.sources.microsoft_learn import CURRICULUM

    objectives = json.loads(
        (FIXTURES / "microsoft_learn_objectives.json").read_text(encoding="utf-8")
    )
    for entry in CURRICULUM:
        assert objectives.get(entry["uid"]), f"{entry['uid']} 缺学习目标 fixture"
        assert all(isinstance(o, str) and o for o in objectives[entry["uid"]])
