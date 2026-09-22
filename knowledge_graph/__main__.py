"""命令行入口:图谱构建与查询(阶段 2A 验收命令)。

用法::

    python -m knowledge_graph build                          # 导入 data/processed/ 构建图谱
    python -m knowledge_graph build --data-dir DIR --no-wipe # 指定数据目录,增量 MERGE
    python -m knowledge_graph position "AI Engineer"         # 岗位技能要求
    python -m knowledge_graph course "Develop AI Agents"     # 课程覆盖技能 + 前置链路
    python -m knowledge_graph skill "AI Agent"                # 教授该技能的课程
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from knowledge_graph import builder, queries
from skillbridge.db import neo4j_driver


def _run_build(driver, args: argparse.Namespace) -> None:
    counts = builder.build_graph(driver, args.data_dir, wipe=not args.no_wipe)
    nodes = " / ".join(
        f"{counts.get(label, 0)} {label}"
        for label in ("Skill", "Position", "Course", "Employee")
    )
    relations = ", ".join(
        f"{rel} {counts.get(rel, 0)}"
        for rel in (
            "HAS_SKILL", "REQUIRES", "TEACHES", "PREREQUISITE",
            "CURRENT_POSITION", "TARGET_POSITION",
        )
    )
    print(f"知识图谱构建完成:{nodes}")
    print(f"关系:{relations}")


def _run_position(driver, args: argparse.Namespace) -> None:
    result = queries.position_required_skills(driver, args.name)
    position, skills = result["position"], result["skills"]
    print(
        f"岗位「{position['name']}」({position['position_id']})"
        f"技能要求(共 {len(skills)} 项,按重要度降序):"
    )
    for index, skill in enumerate(skills, start=1):
        print(
            f"  {index:>2}. {skill['name']:<24}"
            f"重要度 {skill['importance']:.1f}  "
            f"要求等级 {skill['required_level']}/4  "
            f"来源 {','.join(skill['sources'])}"
        )


def _run_course(driver, args: argparse.Namespace) -> None:
    taught = queries.course_taught_skills(driver, args.name)
    chain = queries.course_prerequisite_chain(driver, args.name)
    course = chain["course"]
    skill_names = ", ".join(s["name"] for s in taught["skills"]) or "(无)"
    print(
        f"课程「{course['name']}」({course['course_id']},"
        f"{course['difficulty']},{course['duration_minutes']} 分钟)"
    )
    print(f"  覆盖技能:{skill_names}")
    prerequisites = chain["prerequisites"]
    if prerequisites:
        print(
            f"  前置链路(根在前,共 {len(prerequisites)} 门,"
            f"合计 {chain['total_duration_minutes']} 分钟):"
        )
        for index, step in enumerate(prerequisites, start=1):
            print(
                f"    {index}. [深度{step['depth']}] {step['name']}"
                f"({step['course_id']},{step['difficulty']},"
                f"{step['duration_minutes']} 分钟)"
            )
    else:
        print("  前置链路:无(可直接学习)")


def _run_skill(driver, args: argparse.Namespace) -> None:
    result = queries.courses_teaching_skill(driver, args.name)
    skill, courses = result["skill"], result["courses"]
    print(f"教授技能「{skill['name']}」({skill['skill_id']})的课程(共 {len(courses)} 门):")
    for index, course in enumerate(courses, start=1):
        print(
            f"  {index}. {course['name']}"
            f"({course['course_id']},{course['difficulty']},"
            f"{course['duration_minutes']} 分钟)"
        )
        print(f"     {course['url']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m knowledge_graph",
        description="HR 培训知识图谱:构建(Neo4j)与查询",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser(
        "build", help="从 data/processed/ 导入,构建知识图谱"
    )
    build_parser.add_argument(
        "--data-dir", type=Path, default=None,
        help="标准化数据目录(默认 data/processed)",
    )
    build_parser.add_argument(
        "--no-wipe", action="store_true",
        help="不清空数据库,按 MERGE 幂等导入(默认整库重建)",
    )

    position_parser = subparsers.add_parser(
        "position", help="查询岗位技能要求(岗位需要什么能力?)"
    )
    position_parser.add_argument("name", help="岗位名称或 position_id")

    course_parser = subparsers.add_parser(
        "course", help="查询课程覆盖技能与前置链路"
    )
    course_parser.add_argument("name", help="课程名称或 course_id")

    skill_parser = subparsers.add_parser(
        "skill", help="查询教授指定技能的课程"
    )
    skill_parser.add_argument("name", help="技能名称、别名或 skill_id")

    args = parser.parse_args(argv)

    driver = neo4j_driver()
    try:
        if args.command == "build":
            _run_build(driver, args)
        elif args.command == "position":
            _run_position(driver, args)
        elif args.command == "course":
            _run_course(driver, args)
        else:
            _run_skill(driver, args)
    except (FileNotFoundError, ValueError, LookupError) as exc:
        print(f"错误:{exc}", file=sys.stderr)
        return 1
    finally:
        driver.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
