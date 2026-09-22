"""数据采集入口:``python -m data.collect``(阶段 1A 验收命令)。

流程(大纲第二节「真实数据体系建设」):

1. ESCO / O*NET 岗位与技能拉取(在线 API → ``data/raw/`` 离线缓存 → fixture);
2. Microsoft Learn 课程元数据采集(目录 API + 课程页学习目标);
3. 模拟员工数据生成(10 名,技能等级 0-4,含 Evidence);
4. 统一 JSON Schema 校验后落盘 ``data/processed/``。

用法::

    python -m data.collect                 # 在线优先,断网自动回退
    python -m data.collect --offline       # 强制离线(缓存/fixture)
    python -m data.collect --refresh       # 忽略缓存新鲜度,强制重新拉取
    python -m data.collect --seed 7        # 指定员工生成种子
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import sys
from pathlib import Path
from typing import Any

from data import employees as employees_mod
from data import positions as positions_mod
from data import schemas as schemas_mod
from data import skilllib
from data.sources import esco as esco_source
from data.sources import microsoft_learn as learn_source
from data.sources import onet as onet_source

logger = logging.getLogger("data.collect")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_OUT_DIR = PROJECT_ROOT / "data" / "processed"

#: ESCO 岗位查询(与 positions.POSITION_CONFIGS 对应)
ESCO_QUERIES = [
    config["esco_query"]
    for config in positions_mod.POSITION_CONFIGS
    if config.get("esco_query")
]

#: O*NET SOCP 编码(与 positions.POSITION_CONFIGS 对应)
ONET_CODES = [
    config["onet_code"]
    for config in positions_mod.POSITION_CONFIGS
    if config.get("onet_code")
]


def _utcnow_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _onet_credentials() -> tuple[str, str] | None:
    """从环境变量读取 O*NET Web Services 凭据(可选)。"""
    import os

    username = os.getenv("ONET_API_USERNAME", "").strip()
    password = os.getenv("ONET_API_PASSWORD", "").strip()
    if username and password:
        return username, password
    return None


def collect_all(
    *,
    raw_dir: Path = DEFAULT_RAW_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
    offline: bool = False,
    refresh: bool = False,
    seed: int = 42,
) -> dict[str, Any]:
    """执行完整采集流程,返回统计信息。

    :param offline: 强制离线(不发起网络请求,使用缓存 / fixture)。
    :param refresh: 强制重新拉取在线 API(忽略缓存 TTL)。
    :param seed: 员工数据生成种子。
    """
    stats: dict[str, Any] = {"sources": {}}

    # ---------- 1. ESCO 岗位与技能 ----------
    esco_raw, esco_src = esco_source.load_esco(
        ESCO_QUERIES, raw_dir=raw_dir, offline=offline, refresh=refresh
    )
    stats["sources"]["esco"] = esco_src
    esco_positions = esco_source.parse_esco_positions(esco_raw)
    esco_provenance = esco_source.collect_skill_provenance(esco_raw)

    # ---------- 2. O*NET 岗位与技能 ----------
    onet_raw, onet_src = onet_source.load_onet(
        ONET_CODES,
        raw_dir=raw_dir,
        credentials=_onet_credentials(),
        offline=offline,
        refresh=refresh,
    )
    stats["sources"]["onet"] = onet_src
    onet_positions = onet_source.parse_onet_positions(onet_raw)
    onet_provenance = onet_source.collect_skill_provenance(onet_raw)

    # ---------- 3. Microsoft Learn 课程 ----------
    catalog, catalog_src = learn_source.load_catalog(
        raw_dir=raw_dir, offline=offline, refresh=refresh
    )
    stats["sources"]["microsoft_learn_catalog"] = catalog_src

    selected_modules = [
        module
        for module in catalog.get("modules", [])
        if module.get("uid") in {entry["uid"] for entry in learn_source.CURRICULUM}
    ]
    objectives, objectives_src = learn_source.load_objectives(
        selected_modules, raw_dir=raw_dir, offline=offline, refresh=refresh
    )
    stats["sources"]["microsoft_learn_objectives"] = objectives_src
    courses = learn_source.parse_courses(catalog, objectives)

    # ---------- 4. 统一技能库(ESCO + O*NET + curated 来源标注)----------
    provenance: dict[str, set[str]] = {}
    for source_provenance in (esco_provenance, onet_provenance):
        for skill_id, sources in source_provenance.items():
            provenance.setdefault(skill_id, set()).update(sources)
    skills = skilllib.build_skill_library(provenance)

    # ---------- 5. 岗位合并(ESCO ∪ O*NET ∪ curated)----------
    positions = positions_mod.build_positions(esco_positions, onet_positions)

    # ---------- 6. 模拟员工 ----------
    employee_list = employees_mod.generate_employees(seed=seed)

    generated_at = _utcnow_iso()
    skills_doc = {"generated_at": generated_at, "skills": skills}
    positions_doc = {"generated_at": generated_at, "positions": positions}
    courses_doc = {"generated_at": generated_at, "courses": courses}
    employees_doc = {
        "generated_at": generated_at, "seed": seed, "employees": employee_list
    }

    # ---------- 7. 校验后落盘 ----------
    errors = schemas_mod.validate_all(
        skills_doc, positions_doc, courses_doc, employees_doc
    )
    if errors:
        raise ValueError("数据校验失败:\n" + "\n".join(f"  - {e}" for e in errors))

    _write_json(out_dir / "skills.json", skills_doc)
    _write_json(out_dir / "positions.json", positions_doc)
    _write_json(out_dir / "courses.json", courses_doc)
    _write_json(out_dir / "employees.json", employees_doc)
    for name, schema in schemas_mod.SCHEMAS.items():
        _write_json(out_dir / "schemas" / f"{name}.schema.json", schema)

    stats.update(
        {
            "generated_at": generated_at,
            "skills": len(skills),
            "positions": len(positions),
            "courses": len(courses),
            "employees": len(employee_list),
            "out_dir": str(out_dir),
        }
    )
    return stats


def _print_summary(stats: dict[str, Any]) -> None:
    source_labels = {
        "api": "在线 API",
        "cache": "本地缓存",
        "fixture": "内置 fixture",
    }
    print("=" * 62)
    print("SkillBridge 数据采集完成")
    print("=" * 62)
    print(f"生成时间 : {stats['generated_at']}")
    print(f"输出目录 : {stats['out_dir']}")
    print(
        "数据源   : "
        + ", ".join(
            f"{name}({source_labels.get(src, src)})"
            for name, src in stats["sources"].items()
        )
    )
    print("-" * 62)
    print(f"技能库   : {stats['skills']} 项        → skills.json")
    print(f"岗位     : {stats['positions']} 个        → positions.json")
    print(f"课程     : {stats['courses']} 门        → courses.json")
    print(f"员工     : {stats['employees']} 名        → employees.json")
    print("Schema   : 4 份          → schemas/*.schema.json")
    print("=" * 62)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m data.collect",
        description="SkillBridge 数据采集(ESCO / O*NET / Microsoft Learn / 模拟员工)",
    )
    parser.add_argument(
        "--offline", action="store_true",
        help="强制离线模式:不发起网络请求,依次使用 data/raw/ 缓存与内置 fixture",
    )
    parser.add_argument(
        "--refresh", action="store_true",
        help="忽略缓存新鲜度,强制重新拉取在线 API",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="模拟员工数据生成种子(默认 42,保证可复现)",
    )
    parser.add_argument(
        "--raw-dir", type=Path, default=DEFAULT_RAW_DIR,
        help="原始数据缓存目录(默认 data/raw)",
    )
    parser.add_argument(
        "--out-dir", type=Path, default=DEFAULT_OUT_DIR,
        help="标准化数据输出目录(默认 data/processed)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    try:
        stats = collect_all(
            raw_dir=args.raw_dir,
            out_dir=args.out_dir,
            offline=args.offline,
            refresh=args.refresh,
            seed=args.seed,
        )
    except Exception as exc:
        logger.error("采集失败: %s", exc)
        return 1

    _print_summary(stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
