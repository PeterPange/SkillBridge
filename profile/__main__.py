"""员工画像与 Skill Gap CLI(阶段 2B 验收入口)。

用法::

    python -m profile                     # 默认员工 EMP_001(李明)
    python -m profile EMP_003 EMP_007     # 多名员工
    python -m profile --list              # 列出全部员工
    python -m profile EMP_001 --json      # 结构化 JSON 差距报告
    python -m profile EMP_001 --explain SKILL_001   # 单项技能 Evidence 解释

数据优先读取 ``data/processed/``(``make collect`` 产出);文件缺失时
自动回退离线管线(内置 fixture 岗位 + 模拟员工生成器),不发起网络
请求,保证开箱可用。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from data import employees as employees_mod
from data import positions as positions_mod
from data import skilllib
from data.collect import ESCO_QUERIES, ONET_CODES
from data.sources import esco as esco_source
from data.sources import onet as onet_source
from profile.gap import build_gap_report
from profile.loader import build_employee_profile
from profile.report import render_evidence_explanation, render_gap_report

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "processed"
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_SEED = 42


def _build_offline(raw_dir: Path, seed: int) -> tuple[list[dict], list[dict]]:
    """离线兜底:内置 fixture 岗位 + 模拟员工生成器(不联网)。"""
    esco_raw, _ = esco_source.load_esco(ESCO_QUERIES, raw_dir=raw_dir, offline=True)
    onet_raw, _ = onet_source.load_onet(ONET_CODES, raw_dir=raw_dir, offline=True)
    positions = positions_mod.build_positions(
        esco_source.parse_esco_positions(esco_raw),
        onet_source.parse_onet_positions(onet_raw),
    )
    employees = employees_mod.generate_employees(seed=seed)
    return positions, employees


def load_data(
    data_dir: Path = DEFAULT_DATA_DIR,
    *,
    raw_dir: Path = DEFAULT_RAW_DIR,
    seed: int = DEFAULT_SEED,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """加载岗位与员工数据,返回 ``(positions, employees)``。

    优先读取 ``data/processed/`` 落盘文件;缺失时离线重建
    (fixture 岗位 + 生成器员工,种子 ``seed`` 保证可复现)。
    """
    employees_file = data_dir / "employees.json"
    positions_file = data_dir / "positions.json"
    if employees_file.is_file() and positions_file.is_file():
        positions = json.loads(positions_file.read_text(encoding="utf-8"))["positions"]
        employees = json.loads(employees_file.read_text(encoding="utf-8"))["employees"]
        return positions, employees
    return _build_offline(raw_dir, seed)


def _skill_display_name(skill_id: str) -> str | None:
    """技能显示名(未知技能回退 ``None``)。"""
    try:
        return skilllib.get_skill(skill_id)["name"]
    except KeyError:
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m profile",
        description="员工画像与 Skill Gap 分析(大纲第五、六节)",
    )
    parser.add_argument(
        "employee_ids", nargs="*",
        help="员工 ID(如 EMP_001),默认 EMP_001",
    )
    parser.add_argument("--list", action="store_true", help="列出全部员工")
    parser.add_argument(
        "--json", dest="as_json", action="store_true",
        help="输出结构化 JSON 差距报告",
    )
    parser.add_argument(
        "--explain", metavar="SKILL_ID",
        help="解释单项技能等级(Evidence:考试 / 项目 / 自评 / 培训记录)",
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

    positions, employees = load_data(args.data_dir, raw_dir=args.raw_dir, seed=args.seed)
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
        report = build_gap_report(
            profile, target,
            current_position=positions_by_id.get(profile.current_position_id),
        )

        if index:
            print()
        if args.as_json:
            print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        else:
            print(render_gap_report(report))
            if args.explain:
                print()
                print(
                    render_evidence_explanation(
                        profile, args.explain,
                        skill_name=_skill_display_name(args.explain),
                    )
                )
    return 0


if __name__ == "__main__":
    sys.exit(main())
