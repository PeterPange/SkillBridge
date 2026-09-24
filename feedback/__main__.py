"""培训反馈闭环 CLI(大纲第十一节验收入口)。

用法::

    # 培训完成登记:落库 + Evidence 追加 + 自动闭环重算
    # (显示技能提升、培训历史与当前准备度)
    python -m feedback complete EMP_001 CRS_001 --score 85

    # 培训档案:培训历史 + 画像变化 + 准备度前后对比
    python -m feedback status EMP_001

    # 学习路径前后对比:原路径 vs 培训后重排路径(已完成课程剪枝)
    python -m feedback plan-diff EMP_001

    # 结构化 JSON(供 Agent / LLM 消费)
    python -m feedback status EMP_001 --json

前置条件:``make up``(Neo4j + PostgreSQL);complete / plan-diff
还需 ``make graph`` 导入课程图谱。员工与岗位数据优先读取
``data/processed/``,缺失时自动回退离线管线(与其他 CLI 一致)。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import psycopg
from neo4j.exceptions import AuthError, ServiceUnavailable

from feedback import build_feedback_state, build_plan_diff, record_completion
from feedback.loop import load_course_catalog
from feedback.report import render_completion, render_plan_diff, render_status
from feedback.store import PostgresTrainingStore
from learning_path.path import DEFAULT_DEADLINE_WEEKS, DEFAULT_HOURS_PER_WEEK
from profile.__main__ import (
    DEFAULT_DATA_DIR,
    DEFAULT_RAW_DIR,
    DEFAULT_SEED,
)
from recommendation import DEFAULT_TOP_K
from skillbridge.db import neo4j_driver

_PG_HINT = "无法连接 PostgreSQL;请先 make up 启动服务"
_NEO4J_HINT = (
    "无法连接 Neo4j;请先 make up 启动服务,并 make graph 导入图谱"
)


def _add_common_options(parser: argparse.ArgumentParser) -> None:
    """公共参数:数据目录 / 离线兜底 / JSON 输出。"""
    parser.add_argument(
        "--data-dir", type=Path, default=DEFAULT_DATA_DIR,
        help="标准化数据目录(默认 data/processed)",
    )
    parser.add_argument(
        "--raw-dir", type=Path, default=DEFAULT_RAW_DIR,
        help="离线兜底时的原始数据缓存目录(默认 data/raw)",
    )
    parser.add_argument(
        "--seed", type=int, default=DEFAULT_SEED,
        help="离线兜底时的员工生成种子(默认 42)",
    )
    parser.add_argument(
        "--json", dest="as_json", action="store_true",
        help="输出结构化 JSON(供 Agent / LLM 消费)",
    )


def _add_plan_options(parser: argparse.ArgumentParser) -> None:
    """课表时间约束(与 python -m learning_path 默认一致)。"""
    parser.add_argument(
        "--top-k", type=int, default=DEFAULT_TOP_K,
        help=f"闭环重算的推荐数量(默认 {DEFAULT_TOP_K})",
    )
    parser.add_argument(
        "--hours-per-week", type=float, default=DEFAULT_HOURS_PER_WEEK,
        help=f"每周可学习小时数(默认 {DEFAULT_HOURS_PER_WEEK:g})",
    )
    parser.add_argument(
        "--weeks", type=int, default=DEFAULT_DEADLINE_WEEKS,
        help=f"培训截止周数(默认 {DEFAULT_DEADLINE_WEEKS})",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m feedback",
        description=(
            "培训反馈闭环(大纲第十一节):完成登记 → 画像刷新 → "
            "Skill Gap 重算 → 推荐刷新 → 课表重排"
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    complete_parser = subparsers.add_parser(
        "complete",
        help="登记一次培训完成(落库 + Evidence 追加 + 自动闭环重算)",
    )
    complete_parser.add_argument("employee_id", help="员工 ID,如 EMP_001")
    complete_parser.add_argument("course_id", help="课程 ID,如 CRS_001")
    complete_parser.add_argument(
        "--score", type=int, required=True,
        help="考试分数(0-100;≥85 提升 1 级,70-84 提升 1 级并标记需巩固,"
        "<70 不提升并生成补基础建议)",
    )
    _add_plan_options(complete_parser)
    _add_common_options(complete_parser)

    status_parser = subparsers.add_parser(
        "status", help="培训档案:培训历史 + 画像变化 + 当前准备度"
    )
    status_parser.add_argument("employee_id", help="员工 ID,如 EMP_001")
    _add_common_options(status_parser)

    diff_parser = subparsers.add_parser(
        "plan-diff", help="学习路径前后对比(原路径 vs 培训后重排路径)"
    )
    diff_parser.add_argument("employee_id", help="员工 ID,如 EMP_001")
    _add_plan_options(diff_parser)
    _add_common_options(diff_parser)

    args = parser.parse_args(argv)
    data_kwargs = {
        "data_dir": Path(args.data_dir),
        "raw_dir": Path(args.raw_dir),
        "seed": args.seed,
    }

    store = PostgresTrainingStore()
    try:
        store.ensure_schema()
    except psycopg.OperationalError as exc:
        print(f"错误:{_PG_HINT}({exc})", file=sys.stderr)
        return 1

    try:
        if args.command == "complete":
            if not 0 <= args.score <= 100:
                print(
                    f"考试分数必须在 0-100 之间,得到 {args.score}",
                    file=sys.stderr,
                )
                return 1
            driver = neo4j_driver()
            try:
                # 先验证连通再落库:闭环重算依赖图谱,避免登记成功但重算失败
                driver.verify_connectivity()
                result = record_completion(
                    driver,
                    store,
                    args.employee_id,
                    args.course_id,
                    args.score,
                    top_k=args.top_k,
                    hours_per_week=args.hours_per_week,
                    deadline_weeks=args.weeks,
                    source="cli",
                    **data_kwargs,
                )
            finally:
                driver.close()
            if args.as_json:
                print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
            else:
                catalog = load_course_catalog(**data_kwargs)
                print(render_completion(result, catalog))
            return 0

        if args.command == "status":
            state = build_feedback_state(store, args.employee_id, **data_kwargs)
            if args.as_json:
                print(json.dumps(state.to_dict(), ensure_ascii=False, indent=2))
            else:
                catalog = load_course_catalog(**data_kwargs)
                print(render_status(state, catalog))
            return 0

        if args.command == "plan-diff":
            state = build_feedback_state(store, args.employee_id, **data_kwargs)
            driver = neo4j_driver()
            try:
                driver.verify_connectivity()
                diff = build_plan_diff(
                    driver,
                    state,
                    hours_per_week=args.hours_per_week,
                    deadline_weeks=args.weeks,
                )
            finally:
                driver.close()
            if args.as_json:
                print(json.dumps(diff.to_dict(), ensure_ascii=False, indent=2))
            else:
                print(render_plan_diff(diff))
            return 0
    except (LookupError, ValueError) as exc:
        print(f"错误:{exc}", file=sys.stderr)
        return 1
    except psycopg.OperationalError as exc:
        print(f"错误:{_PG_HINT}({exc})", file=sys.stderr)
        return 1
    except (ServiceUnavailable, AuthError, OSError) as exc:
        print(f"错误:{_NEO4J_HINT}({exc})", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
