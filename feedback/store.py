"""培训记录存储:PostgreSQL 生产实现 + 内存实现(测试 / 离线演示)。

- :class:`TrainingStore` 协议统一「建表 / 写入 / 查询 / 清空」;
- :class:`PostgresTrainingStore` 落库大纲第十一节的两张表::

      training_record(employee_id, course_id, completed_at, source)
      assessment(record_id, exam_score, passed, level_changes, suggestions)

  一次完成登记 = 一条 training_record + 一条 assessment(同事务写入);
  技能等级变化与建议以 JSONB 挂在 assessment 上,保证「为什么涨级」
  可解释、可回放;
- :class:`MemoryTrainingStore` 纯 Python 列表实现,供无数据库环境下
  的单元测试使用,排序语义与 PostgreSQL 一致(record_id 升序)。
"""

from __future__ import annotations

import itertools
from collections.abc import Iterable, Sequence
from datetime import datetime, timezone
from typing import Protocol

from psycopg import Connection, sql

from feedback.models import Suggestion, SkillLevelChange, TrainingRecord
from skillbridge.config import Settings
from skillbridge.db import postgres_connect

_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS training_record (
        record_id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        employee_id  TEXT        NOT NULL,
        course_id    TEXT        NOT NULL,
        source       TEXT        NOT NULL DEFAULT 'cli',
        completed_at TIMESTAMPTZ  NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS assessment (
        assessment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        record_id     BIGINT  NOT NULL UNIQUE
                              REFERENCES training_record(record_id)
                              ON DELETE CASCADE,
        employee_id   TEXT    NOT NULL,
        course_id     TEXT    NOT NULL,
        exam_score    INTEGER NOT NULL CHECK (exam_score BETWEEN 0 AND 100),
        passed        BOOLEAN NOT NULL,
        level_changes JSONB   NOT NULL DEFAULT '[]'::jsonb,
        suggestions   JSONB   NOT NULL DEFAULT '[]'::jsonb,
        created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_training_record_employee "
    "ON training_record(employee_id)",
    "CREATE INDEX IF NOT EXISTS idx_assessment_employee "
    "ON assessment(employee_id)",
)

_INSERT_RECORD = sql.SQL(
    """
    INSERT INTO training_record (employee_id, course_id, source)
    VALUES (%(employee_id)s, %(course_id)s, %(source)s)
    RETURNING record_id, completed_at
    """
)

_INSERT_ASSESSMENT = sql.SQL(
    """
    INSERT INTO assessment (
        record_id, employee_id, course_id,
        exam_score, passed, level_changes, suggestions
    )
    VALUES (
        %(record_id)s, %(employee_id)s, %(course_id)s,
        %(exam_score)s, %(passed)s, %(level_changes)s, %(suggestions)s
    )
    RETURNING assessment_id
    """
)

_SELECT_RECORDS = sql.SQL(
    """
    SELECT r.record_id, r.employee_id, r.course_id, r.completed_at,
           a.exam_score, a.passed, a.level_changes, a.suggestions
    FROM training_record AS r
    JOIN assessment AS a ON a.record_id = r.record_id
    WHERE r.employee_id = %(employee_id)s
    ORDER BY r.record_id
    """
)


def _changes_to_json(changes: Iterable[SkillLevelChange]) -> list[dict]:
    """等级变化模型 → JSONB 行。"""
    return [change.to_dict() for change in changes]


def _suggestions_to_json(suggestions: Iterable[Suggestion]) -> list[dict]:
    """建议模型 → JSONB 行。"""
    return [item.to_dict() for item in suggestions]


def _changes_from_json(rows: Sequence[dict]) -> tuple[SkillLevelChange, ...]:
    """JSONB 行 → 等级变化模型。"""
    return tuple(
        SkillLevelChange(
            skill_id=row["skill_id"],
            skill_name=row["skill_name"],
            from_level=int(row["from_level"]),
            to_level=int(row["to_level"]),
            flag=row.get("flag"),
            note=row.get("note", ""),
        )
        for row in rows
    )


def _suggestions_from_json(rows: Sequence[dict]) -> tuple[Suggestion, ...]:
    """JSONB 行 → 建议模型。"""
    return tuple(
        Suggestion(
            kind=row["kind"],
            course_id=row["course_id"],
            course_name=row["course_name"],
            reason=row["reason"],
        )
        for row in rows
    )


class TrainingStore(Protocol):
    """培训记录存储协议:写入与查询的统一接口。"""

    def ensure_schema(self) -> None:
        """初始化存储(建表 / 建索引),幂等。"""
        ...

    def add_record(
        self,
        employee_id: str,
        course_id: str,
        exam_score: int,
        *,
        passed: bool,
        level_changes: Iterable[SkillLevelChange] = (),
        suggestions: Iterable[Suggestion] = (),
        source: str = "cli",
    ) -> TrainingRecord:
        """写入一条完成记录(training_record + assessment,同事务)。

        :return: 已落库的 :class:`~feedback.models.TrainingRecord`
            (携带数据库生成的 record_id 与 completed_at)。
        """
        ...

    def list_records(self, employee_id: str) -> list[TrainingRecord]:
        """查询员工全部培训记录(按 record_id 升序,含等级变化与建议)。"""
        ...

    def reset(self) -> None:
        """清空全部培训记录(测试隔离 / 重新演示用)。"""
        ...


# ---------------------------------------------------------------------------
# PostgreSQL 实现
# ---------------------------------------------------------------------------

class PostgresTrainingStore:
    """培训记录的 PostgreSQL 存储(大纲第十一节的落库层)。

    :param settings: 数据库配置,缺省读 ``skillbridge.config``(环境变量);
    :param connection: 已建立的 psycopg 连接(测试注入用);
        传入则由调用方管理生命周期,未传则内部创建并在 ``close()`` 时关闭。
    """

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        connection: Connection | None = None,
    ):
        self._settings = settings
        self._connection = connection
        self._owned = connection is None

    def _connect(self) -> Connection:
        if self._connection is not None and not self._connection.closed:
            return self._connection
        return postgres_connect(self._settings)

    def close(self) -> None:
        """关闭内部创建的连接(注入连接由调用方管理)。"""
        if self._owned and self._connection is not None:
            self._connection.close()

    def ensure_schema(self) -> None:
        """建表与索引(``IF NOT EXISTS``,幂等)。"""
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                for statement in _SCHEMA_STATEMENTS:
                    cur.execute(statement)
            conn.commit()
        finally:
            if self._owned:
                conn.close()

    def add_record(
        self,
        employee_id: str,
        course_id: str,
        exam_score: int,
        *,
        passed: bool,
        level_changes: Iterable[SkillLevelChange] = (),
        suggestions: Iterable[Suggestion] = (),
        source: str = "cli",
    ) -> TrainingRecord:
        """写入一条完成记录:training_record + assessment(同事务)。"""
        from psycopg.types.json import Json

        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    _INSERT_RECORD,
                    {"employee_id": employee_id, "course_id": course_id, "source": source},
                )
                record_id, completed_at = cur.fetchone()
                cur.execute(
                    _INSERT_ASSESSMENT,
                    {
                        "record_id": record_id,
                        "employee_id": employee_id,
                        "course_id": course_id,
                        "exam_score": exam_score,
                        "passed": passed,
                        "level_changes": Json(_changes_to_json(level_changes)),
                        "suggestions": Json(_suggestions_to_json(suggestions)),
                    },
                )
                cur.fetchone()
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            if self._owned:
                conn.close()
        return TrainingRecord(
            record_id=int(record_id),
            employee_id=employee_id,
            course_id=course_id,
            exam_score=exam_score,
            passed=passed,
            completed_at=completed_at.isoformat(),
            level_changes=tuple(level_changes),
            suggestions=tuple(suggestions),
            source=source,
        )

    def list_records(self, employee_id: str) -> list[TrainingRecord]:
        """查询员工全部培训记录(按 record_id 升序)。"""
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(_SELECT_RECORDS, {"employee_id": employee_id})
                rows = cur.fetchall()
        finally:
            if self._owned:
                conn.close()
        return [
            TrainingRecord(
                record_id=int(row[0]),
                employee_id=row[1],
                course_id=row[2],
                completed_at=row[3].isoformat(),
                exam_score=int(row[4]),
                passed=bool(row[5]),
                level_changes=_changes_from_json(row[6]),
                suggestions=_suggestions_from_json(row[7]),
                source="postgres",
            )
            for row in rows
        ]

    def reset(self) -> None:
        """清空培训记录表(测试隔离用;表由本模块专有)。"""
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL(
                        "TRUNCATE TABLE assessment, training_record "
                        "RESTART IDENTITY CASCADE"
                    )
                )
            conn.commit()
        finally:
            if self._owned:
                conn.close()


# ---------------------------------------------------------------------------
# 内存实现(测试 / 离线)
# ---------------------------------------------------------------------------

class MemoryTrainingStore:
    """培训记录的内存实现(排序语义与 PostgreSQL 一致)。

    供无数据库环境的单元测试使用;``record_id`` 从 1 自增。
    """

    def __init__(self) -> None:
        self._records: list[TrainingRecord] = []
        self._counter = itertools.count(start=1)

    def ensure_schema(self) -> None:
        """内存存储无需建表(协议兼容)。"""

    def add_record(
        self,
        employee_id: str,
        course_id: str,
        exam_score: int,
        *,
        passed: bool,
        level_changes: Iterable[SkillLevelChange] = (),
        suggestions: Iterable[Suggestion] = (),
        source: str = "cli",
    ) -> TrainingRecord:
        """追加一条完成记录(record_id 自增)。"""
        record = TrainingRecord(
            record_id=next(self._counter),
            employee_id=employee_id,
            course_id=course_id,
            exam_score=exam_score,
            passed=passed,
            completed_at=datetime.now(timezone.utc).isoformat(),
            level_changes=tuple(level_changes),
            suggestions=tuple(suggestions),
            source=source,
        )
        self._records.append(record)
        return record

    def list_records(self, employee_id: str) -> list[TrainingRecord]:
        """查询员工全部培训记录(按 record_id 升序)。"""
        return [
            record
            for record in self._records
            if record.employee_id == employee_id
        ]

    def reset(self) -> None:
        """清空全部记录。"""
        self._records.clear()
        self._counter = itertools.count(start=1)
