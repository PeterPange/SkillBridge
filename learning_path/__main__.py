"""命令行入口:自适应学习路径周计划(阶段 3B 验收命令)。

用法::

    python -m learning_path                        # 默认员工 EMP_001(李明),
                                                  # 每周 4 小时,8 周截止
    python -m learning_path EMP_003 EMP_007       # 多名员工
    python -m learning_path --list                 # 列出全部员工
    python -m learning_path EMP_001 --hours-per-week 6   # 每周 6 小时
    python -m learning_path EMP_001 --weeks 12     # 截止 12 周
    python -m learning_path EMP_001 --json         # 结构化 JSON(供 LLM / Agent 消费)

前置条件:``make up``(Neo4j)与 ``make graph``(图谱导入)。
员工与岗位数据优先读取 ``data/processed/``,缺失时自动回退离线管线
(与 ``python -m profile`` / ``python -m recommendation`` 一致);
候选课程一律从图谱 TEACHES 关系召回(复用第七节逻辑)。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from neo4j.exceptions import AuthError, ServiceUnavailable

from learning_path import generate_learning_path
from learning_path.path import DEFAULT_DEADLINE_WEEKS, DEFAULT_HOURS_PER_WEEK
from learning_path.report import render_learning_path_report
from profile import build_employee_profile, build_gap_report
from profile.__main__ import (
    DEFAULT_DATA_DIR,
    DEFAULT_RAW_DIR,
    DEFAULT_SEED,
    load_data,
)
from skillbridge.db import neo4j_driver


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m learning_path",
        description="自适应学习路径(大纲第八节:DAG 剪枝 + 拓扑排序 + 周计划)",
    )
    parser.add_argument(
        "employee_ids", nargs="*",
        help="员工 ID(如 EMP_001),默认 EMP_001",
    )
    parser.add_argument("--list", action="store_true", help="列出全部员工")
    parser.add_argument(
        "--hours-per-week", type=float, default=DEFAULT_HOURS_PER_WEEK,
        help=f"每周可学习小时数(默认 {DEFAULT_HOURS_PER_WEEK:g})",
    )
    parser.add_argument(
        "--weeks", type=int, default=DEFAULT_DEADLINE_WEEKS,
        help=f"培训截止周数(默认 {DEFAULT_DEADLINE_WEEKS})",
    )
    parser.add_argument(
        "--json", dest="as_json", action="store_true",
        help="输出结构化 JSON 学习路径",
    )
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
    args = parser.parse_args(argv)

    positions, employees = load_data(
        Path(args.data_dir), raw_dir=Path(args.raw_dir), seed=args.seed
    )
    positions_by_id = {position["position_id"]: position for position in positions}

    if args.list:
        for employee in employees:
            print(
                f"{employee['employee_id']}  {employee['name']}  "
                f"{employee['department']}  工龄 {employee['years_of_experience']} 年"
            )
        return 0

    ids = args.employee_ids or ["EMP_001"]
    known_ids = {employee["employee_id"] for employee in employees}
    unknown = [employee_id for employee_id in ids if employee_id not in known_ids]
    if unknown:
        print(
            f"未知员工: {', '.join(unknown)}(可用 --list 查看)",
            file=sys.stderr,
        )
        return 1
    if args.hours_per_week <= 0:
        print(
            f"每周可学时间必须大于 0 小时,得到 {args.hours_per_week}",
            file=sys.stderr,
        )
        return 1
    if args.weeks < 1:
        print(f"截止周数必须大于等于 1,得到 {args.weeks}", file=sys.stderr)
        return 1

    driver = neo4j_driver()
    try:
        for index, employee_id in enumerate(ids):
            record = next(e for e in employees if e["employee_id"] == employee_id)
            profile = build_employee_profile(record)
            target = positions_by_id.get(profile.target_position_id)
            if target is None:
                print(
                    f"员工 {employee_id} 的目标岗位 {profile.target_position_id} 不存在",
                    file=sys.stderr,
                )
                return 1
            gap_report = build_gap_report(
                profile, target,
                current_position=positions_by_id.get(profile.current_position_id),
            )
            report = generate_learning_path(
                driver, profile, gap_report,
                hours_per_week=args.hours_per_week,
                deadline_weeks=args.weeks,
            )

            if index:
                print()
            if args.as_json:
                print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
            else:
                print(render_learning_path_report(report))
    except (FileNotFoundError, ValueError, LookupError) as exc:
        print(f"错误:{exc}", file=sys.stderr)
        return 1
    except (ServiceUnavailable, AuthError) as exc:
        print(
            f"无法连接 Neo4j({exc});请先 make up 启动服务,"
            "并 make graph 导入图谱",
            file=sys.stderr,
        )
        return 1
    finally:
        driver.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
