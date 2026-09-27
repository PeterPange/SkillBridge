"""站内学习进度存储:员工 × 课程 × 单元 的完成记录。

与 feedback.store 的培训记录(training_record)分工:
- 本表:学习过程中的细粒度进度(读单元、解锁测验);
- feedback:结业事实(课程完成 + 考试),由结业测验自动写入。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

import psycopg

from skillbridge.config import Settings, get_settings


@dataclass(frozen=True)
class UnitProgress:
    """一个单元的完成状态。"""

    course_id: str
    unit_index: int
    completed_at: str


class LearningProgressStore(Protocol):
    """学习进度存储协议。"""

    def ensure_schema(self) -> None: ...
    def mark_unit(self, employee_id: str, course_id: str, unit_index: int) -> None: ...
    def completed_units(self, employee_id: str, course_id: str) -> list[int]: ...
    def reset(self, employee_id: str) -> None: ...


class PostgresLearningProgressStore:
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
        conn = psycopg.connect(
            host=s.postgres_host,
            port=s.postgres_port,
            user=s.postgres_user,
            password=s.postgres_password,
            dbname=s.postgres_db,
        )
        return conn

    def ensure_schema(self) -> None:
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS learning_progress (
                    employee_id TEXT NOT NULL,
                    course_id   TEXT NOT NULL,
                    unit_index  INTEGER NOT NULL,
                    completed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    PRIMARY KEY (employee_id, course_id, unit_index)
                )
                """
            )
        conn.commit()
        if self._owned:
            conn.close()

    def mark_unit(self, employee_id: str, course_id: str, unit_index: int) -> None:
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO learning_progress (employee_id, course_id, unit_index)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (employee_id, course_id, unit_index),
            )
        conn.commit()
        if self._owned:
            conn.close()

    def completed_units(self, employee_id: str, course_id: str) -> list[int]:
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT unit_index FROM learning_progress
                WHERE employee_id = %s AND course_id = %s
                ORDER BY unit_index
                """,
                (employee_id, course_id),
            )
            rows = [r[0] for r in cur.fetchall()]
        if self._owned:
            conn.close()
        return rows

    def reset(self, employee_id: str) -> None:
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM learning_progress WHERE employee_id = %s", (employee_id,))
        conn.commit()
        if self._owned:
            conn.close()

    def close(self) -> None:
        if self._owned and self._connection is not None and not self._connection.closed:
            self._connection.close()
