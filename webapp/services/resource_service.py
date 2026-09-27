"""资源中心服务:视频 / 教材 / 文档,按员工缺口智能匹配。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from profile.__main__ import DEFAULT_DATA_DIR

RESOURCES_JSON = Path(DEFAULT_DATA_DIR) / "resources.json"

TYPE_LABELS = {"video": "视频", "module": "教材", "document": "文档"}


def _load_resources() -> list[dict[str, Any]]:
    if not RESOURCES_JSON.exists():
        return []
    data = json.loads(RESOURCES_JSON.read_text("utf-8"))
    return data.get("resources", [])


def resource_library(employee_id: str) -> dict[str, Any]:
    """资源中心:全部资源 + 按员工缺口技能的「为你推荐」。

    匹配规则:资源技能标签 ∩ 员工缺口技能 → 优先展示。
    """
    from feedback import build_feedback_state
    from feedback.store import PostgresTrainingStore

    store = PostgresTrainingStore()
    store.ensure_schema()
    state = build_feedback_state(store, employee_id)
    store.close()
    gap_skills = {g.skill_name for g in state.gap_after.gaps}

    resources = _load_resources()
    for r in resources:
        r["type_label"] = TYPE_LABELS.get(r["type"], r["type"])
        r["matched"] = bool(gap_skills & set(r.get("skills", [])))

    recommended = [r for r in resources if r["matched"]]
    by_type: dict[str, list[dict[str, Any]]] = {"video": [], "module": [], "document": []}
    for r in resources:
        by_type.setdefault(r["type"], []).append(r)

    return {
        "recommended": recommended[:12],
        "counts": {k: len(v) for k, v in by_type.items()},
        "videos": by_type.get("video", [])[:30],
        "modules": by_type.get("module", [])[:30],
        "documents": by_type.get("document", []),
    }
