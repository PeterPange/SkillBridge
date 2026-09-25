"""共享测试夹具。

- 大纲第六节验收用例(李明 vs AI Engineer):员工 / 岗位 fixture;
- 大纲第九节验收用例(企业知识库 RAG):企业培训制度文档 fixture。

大纲第二节的示例员工李明(Java 后端,工作 3 年)与第六节的
AI Engineer 岗位要求,映射到统一技能库 skill_id:

- Deployment → SKILL_011 Docker
- Monitoring → SKILL_015 Monitoring
"""

from pathlib import Path

import pytest


def outline_skill(skill_id: str, level: int) -> dict:
    """构造带完整 Evidence 的员工技能记录(等级 → 对应证据)。"""
    return {
        "skill_id": skill_id,
        "level": level,
        "evidence": {
            "assessment_score": level * 22,
            "project_experience": (
                f"参与过 {skill_id} 相关项目,在指导下完成开发任务" if level else "无相关项目经历"
            ),
            "self_assessment": level,
            "training_records": [f"{skill_id} 基础培训已完成"] if level else [],
        },
    }


@pytest.fixture(scope="session")
def training_policy_path() -> Path:
    """企业员工培训制度文档(大纲第九节 RAG 验收用固定 fixture)。"""
    path = (
        Path(__file__).resolve().parent.parent
        / "data"
        / "fixtures"
        / "training_policy.md"
    )
    assert path.is_file(), f"RAG 验收 fixture 缺失: {path}"
    return path


@pytest.fixture()
def outline_employee() -> dict:
    """大纲第二/六节的示例员工:李明(Java 4 / SQL 3 / Python 2 / Docker 2 / ML 1 / GenAI 0 / AI Agent 0)。

    注意:大纲第六节计算 Gap 时 Docker(Deployment)与 Monitoring 取 1,
    这里按第六节的数值构造。
    """
    return {
        "employee_id": "EMP_001",
        "name": "李明",
        "department": "研发中心",
        "current_position_id": "POS_001",
        "target_position_id": "POS_005",
        "years_of_experience": 3,
        "skills": [
            outline_skill("SKILL_002", 4),  # Java(岗位未要求 → 额外技能)
            outline_skill("SKILL_003", 3),  # SQL(同上)
            outline_skill("SKILL_001", 2),  # Python
            outline_skill("SKILL_011", 1),  # Docker = 大纲的 Deployment
            outline_skill("SKILL_004", 1),  # Machine Learning
            outline_skill("SKILL_006", 0),  # Generative AI
            outline_skill("SKILL_009", 0),  # AI Agent
            outline_skill("SKILL_015", 1),  # Monitoring
        ],
    }


@pytest.fixture()
def outline_position() -> dict:
    """大纲第六节的 AI Engineer 岗位要求(重要度取自阶段 1A 策展数据)。"""
    return {
        "position_id": "POS_005",
        "name": "AI Engineer",
        "skills": [
            {"skill_id": "SKILL_001", "importance": 5.0, "required_level": 3},  # Python
            {"skill_id": "SKILL_004", "importance": 4.0, "required_level": 2},  # ML
            {"skill_id": "SKILL_006", "importance": 5.0, "required_level": 3},  # GenAI
            {"skill_id": "SKILL_009", "importance": 5.0, "required_level": 3},  # AI Agent
            {"skill_id": "SKILL_011", "importance": 3.0, "required_level": 2},  # Deployment
            {"skill_id": "SKILL_015", "importance": 3.0, "required_level": 2},  # Monitoring
        ],
    }


# ---------------------------------------------------------------------------
# 独立测试数据库(PostgreSQL 集成测试专用)
#
# 背景:RAG 与培训记录的集成测试需要真实库,但绝不能触碰开发库
# (历史上曾把生产知识库 / 培训记录清空)。以下夹具提供同实例、
# 同凭据、独立 dbname 的 skillbridge_test 库,按需创建。
# ---------------------------------------------------------------------------

import psycopg as _psycopg

from skillbridge.config import get_settings as _get_settings
from skillbridge.db import postgres_connect as _postgres_connect

TEST_DB_NAME = "skillbridge_test"


def ensure_test_database():
    """连接测试库(不存在则创建),返回独立连接(调用方负责 close)。"""
    admin = _postgres_connect()
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (TEST_DB_NAME,))
        if cur.fetchone() is None:
            cur.execute(
                f'''CREATE DATABASE "{TEST_DB_NAME}" TEMPLATE template0 ENCODING 'utf8'''''
            )
    admin.close()
    s = _get_settings()
    conn = _psycopg.connect(
        host=s.postgres_host,
        port=s.postgres_port,
        user=s.postgres_user,
        password=s.postgres_password,
        dbname=TEST_DB_NAME,
    )
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
    conn.commit()
    return conn


@pytest.fixture()
def training_store_test_db():
    """指向测试库的培训记录存储(用例间隔离,开发库零影响)。"""
    from feedback.store import PostgresTrainingStore

    conn = ensure_test_database()
    store = PostgresTrainingStore(connection=conn)
    store.ensure_schema()
    store.reset()
    try:
        yield store
    finally:
        store.close()
        conn.close()
