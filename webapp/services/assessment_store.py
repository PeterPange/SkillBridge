"""技能测评存储:员工 × 技能 的测评记录。

与培训记录(training_record)分工:
- 本表:技能级测评(评测中心,衡量当前能力,作为 Evidence 展示);
- training_record:课程级结业(学习闭环,驱动等级变化)。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import psycopg

from skillbridge.config import Settings, get_settings


@dataclass(frozen=True)
class SkillAssessment:
    """一次技能测评的结果。"""

    employee_id: str
    skill_id: str
    skill_name: str
    score: int
    verdict: str  # excellent / passed / failed
    correct: int
    total: int
    assessed_at: str


class AssessmentStore(Protocol):
    def ensure_schema(self) -> None: ...
    def add(self, record: SkillAssessment) -> None: ...
    def list_for(self, employee_id: str) -> list[SkillAssessment]: ...
    def list_all(self) -> list[SkillAssessment]: ...
    def reset(self, employee_id: str) -> None: ...


class PostgresAssessmentStore:
    """PostgreSQL 实现(与培训记录同库,独立表)。"""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        connection: psycopg.Connection | None = None,
    ) -> None:
        self._settings = settings
        self._connection = connection
        self._owned = connection is None

    def _connect(self) -> psycopg.Connection:
        if self._connection is not None and not self._connection.closed:
            return self._connection
        s = self._settings or get_settings()
        return psycopg.connect(
            host=s.postgres_host,
            port=s.postgres_port,
            user=s.postgres_user,
            password=s.postgres_password,
            dbname=s.postgres_db,
        )

    def ensure_schema(self) -> None:
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS skill_assessments (
                    id           SERIAL PRIMARY KEY,
                    employee_id  TEXT NOT NULL,
                    skill_id     TEXT NOT NULL,
                    skill_name   TEXT NOT NULL,
                    score        INTEGER NOT NULL,
                    verdict      TEXT NOT NULL,
                    correct      INTEGER NOT NULL,
                    total        INTEGER NOT NULL,
                    assessed_at  TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
        conn.commit()
        if self._owned:
            conn.close()

    def add(self, record: SkillAssessment) -> None:
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO skill_assessments
                    (employee_id, skill_id, skill_name, score, verdict, correct, total)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    record.employee_id,
                    record.skill_id,
                    record.skill_name,
                    record.score,
                    record.verdict,
                    record.correct,
                    record.total,
                ),
            )
        conn.commit()
        if self._owned:
            conn.close()

    def _rows_to_records(self, rows: list[tuple]) -> list[SkillAssessment]:
        return [
            SkillAssessment(
                employee_id=r[1],
                skill_id=r[2],
                skill_name=r[3],
                score=int(r[4]),
                verdict=r[5],
                correct=int(r[6]),
                total=int(r[7]),
                assessed_at=r[8].isoformat(),
            )
            for r in rows
        ]

    def list_for(self, employee_id: str) -> list[SkillAssessment]:
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, employee_id, skill_id, skill_name, score, verdict,
                       correct, total, assessed_at
                FROM skill_assessments WHERE employee_id = %s
                ORDER BY assessed_at DESC
                """,
                (employee_id,),
            )
            rows = cur.fetchall()
        if self._owned:
            conn.close()
        return self._rows_to_records(rows)

    def list_all(self) -> list[SkillAssessment]:
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, employee_id, skill_id, skill_name, score, verdict,
                       correct, total, assessed_at
                FROM skill_assessments ORDER BY assessed_at DESC
                """
            )
            rows = cur.fetchall()
        if self._owned:
            conn.close()
        return self._rows_to_records(rows)

    def reset(self, employee_id: str) -> None:
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM skill_assessments WHERE employee_id = %s", (employee_id,))
        conn.commit()
        if self._owned:
            conn.close()

    def close(self) -> None:
        if self._owned and self._connection is not None and not self._connection.closed:
            self._connection.close()
