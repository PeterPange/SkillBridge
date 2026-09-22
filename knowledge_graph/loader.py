"""``data/processed/`` 标准化数据读取与校验(图谱构建的输入)。

阶段 1A 的 ``python -m data.collect`` 产出四类 JSON;本模块负责读取
并重新执行完整校验(Schema + 跨文件引用完整性),保证进入图谱的
数据从一开始就是一致的——岗位 / 课程 / 员工引用的 skill_id 必须存在,
课程前置关系必须构成 DAG。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from data import schemas as schemas_mod

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "processed"

#: 四类标准化数据文件(skills / positions / courses / employees)
DATA_FILES = ("skills", "positions", "courses", "employees")


@dataclass(frozen=True)
class ProcessedData:
    """四类标准化数据的内存形态(与 data/processed/*.json 一一对应)。"""

    skills: dict[str, Any]
    positions: dict[str, Any]
    courses: dict[str, Any]
    employees: dict[str, Any]


def load_processed(data_dir: Path | None = None) -> ProcessedData:
    """读取并校验 ``data/processed/`` 下的四类 JSON。

    :param data_dir: 数据目录(默认 ``data/processed``)。
    :return: :class:`ProcessedData`,已通过全部校验。
    :raises FileNotFoundError: 任一文件缺失(提示先运行数据采集)。
    :raises ValueError: 数据未通过 Schema / 引用完整性校验。
    """
    directory = Path(data_dir) if data_dir is not None else DEFAULT_DATA_DIR
    docs: dict[str, Any] = {}
    for name in DATA_FILES:
        path = directory / f"{name}.json"
        if not path.is_file():
            raise FileNotFoundError(
                f"找不到 {path};请先运行数据采集生成标准化数据"
                f"(make collect 或 python -m data.collect)"
            )
        docs[name] = json.loads(path.read_text(encoding="utf-8"))

    # 分两阶段校验:先 Schema(结构完整),再跨文件引用完整性;
    # 避免结构残缺的数据在引用校验中触发 KeyError。
    errors: list[str] = []
    for name in DATA_FILES:
        errors.extend(
            f"[{name}] {error}"
            for error in schemas_mod.validate_instance(docs[name], name)
        )
    if not errors:
        errors.extend(
            schemas_mod.validate_referential(
                docs["skills"], docs["positions"], docs["courses"], docs["employees"]
            )
        )
    if errors:
        raise ValueError("数据校验失败:\n" + "\n".join(f"  - {e}" for e in errors))

    return ProcessedData(
        skills=docs["skills"],
        positions=docs["positions"],
        courses=docs["courses"],
        employees=docs["employees"],
    )
