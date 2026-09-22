"""岗位数据构建(大纲第二节「岗位数据」)。

岗位 = ESCO 岗位 ∪ O*NET 岗位 ∪ 人工策展岗位,按统一技能库合并:

- ESCO:岗位描述 + essential/optional 技能(重要度 5/3);
- O*NET:任务陈述(岗位职责)+ 技能重要度 + 技术技能;
- 策展:AI Engineer 等新兴岗位无标准职业编码,按大纲第六节的
  岗位要求人工定义(来源标记 ``curated``)。

同一技能多来源时取「重要度最大、要求等级最大」,并保留来源列表,
供后续解释「这个岗位要求为什么来自哪里」。
"""

from __future__ import annotations

from typing import Any

#: 岗位配置:position_id 稳定分配,员工画像与图谱导入都依赖它。
POSITION_CONFIGS: list[dict[str, Any]] = [
    {
        "position_id": "POS_001",
        "name": "Software Developer",
        "esco_query": {"query": "software developer", "title": "software developer"},
        "onet_code": "15-1252.00",
        "responsibilities_fallback": [
            "分析需求并设计、开发软件系统",
            "修复缺陷、重构并持续改进既有系统",
            "编写技术文档并参与代码评审",
        ],
    },
    {
        "position_id": "POS_002",
        "name": "Data Scientist",
        "esco_query": {"query": "data scientist", "title": "data scientist"},
        "onet_code": "15-2051.00",
        "responsibilities_fallback": [
            "分析与建模业务数据,输出洞察",
            "构建与评估机器学习模型",
            "与工程团队协作将模型落地到生产环境",
        ],
    },
    {
        "position_id": "POS_003",
        "name": "DevOps Engineer",
        # ESCO 无对应标准职业;O*NET 以 15-1244.00(网络与系统管理员)近似映射
        "esco_query": None,
        "onet_code": "15-1244.00",
        "description_override": (
            "负责持续集成 / 持续部署流水线、容器化与云基础设施的建设、"
            "自动化与监控,保障研发交付效率与系统可用性。"
        ),
        "responsibilities_fallback": [
            "维护 CI/CD 流水线与发布流程",
            "建设与管理容器化及云基础设施",
            "搭建监控告警体系,保障系统可用性",
        ],
    },
    {
        "position_id": "POS_004",
        "name": "Database Developer",
        "esco_query": {"query": "database developer", "title": "database developer"},
        "onet_code": None,
        "responsibilities_fallback": [
            "设计数据库结构与数据模型",
            "开发与优化 SQL、存储过程和数据管道",
            "保障数据质量、备份与安全",
        ],
    },
    {
        "position_id": "POS_005",
        "name": "AI Engineer",
        # 新兴岗位:无 ESCO/O*NET 标准编码,按大纲第六节人工定义
        "esco_query": None,
        "onet_code": None,
        "description_override": (
            "设计、开发与部署基于大模型的应用:包括 RAG 检索增强系统、"
            "AI Agent 智能体、提示词工程,以及生成式 AI 应用的监控与治理。"
        ),
        "responsibilities_fallback": [
            "设计与实现基于 LLM 的应用(RAG / Agent / 提示词工程)",
            "将 AI 能力集成进现有后端服务并完成部署与监控",
            "评估生成式 AI 应用的效果、成本与风险,落实 AI 治理要求",
        ],
        "curated_skills": [
            # (skill_id, importance 1-5, required_level 0-4) —— 大纲第六节
            ("SKILL_001", 5.0, 3),  # Python
            ("SKILL_004", 4.0, 3),  # Machine Learning
            ("SKILL_006", 5.0, 3),  # Generative AI
            ("SKILL_007", 4.0, 2),  # Large Language Models
            ("SKILL_008", 5.0, 3),  # RAG
            ("SKILL_009", 5.0, 3),  # AI Agent
            ("SKILL_010", 4.0, 2),  # Prompt Engineering
            ("SKILL_011", 3.0, 2),  # Docker
            ("SKILL_012", 3.0, 2),  # Kubernetes
            ("SKILL_013", 4.0, 3),  # API Development
            ("SKILL_014", 3.0, 2),  # Cloud Computing
            ("SKILL_015", 3.0, 2),  # Monitoring
            ("SKILL_016", 3.0, 2),  # CI/CD
            ("SKILL_018", 4.0, 3),  # AI Governance
        ],
    },
]


def _merge_skill_maps(*skill_lists: list[dict]) -> list[dict]:
    """按 skill_id 合并多来源技能:重要度/要求等级取最大,来源取并集。"""
    merged: dict[str, dict] = {}
    for skills in skill_lists:
        for skill in skills:
            skill_id = skill["skill_id"]
            current = merged.get(skill_id)
            if current is None:
                merged[skill_id] = {
                    "skill_id": skill_id,
                    "importance": skill["importance"],
                    "required_level": skill["required_level"],
                    "sources": [skill["source"]],
                }
                continue
            current["importance"] = max(current["importance"], skill["importance"])
            current["required_level"] = max(current["required_level"], skill["required_level"])
            if skill["source"] not in current["sources"]:
                current["sources"].append(skill["source"])
    return sorted(merged.values(), key=lambda s: s["skill_id"])


def build_positions(
    esco_positions: list[dict],
    onet_positions: list[dict],
) -> list[dict]:
    """合并 ESCO / O*NET / 策展数据,输出统一岗位记录。

    :param esco_positions: :func:`data.sources.esco.parse_esco_positions` 的输出。
    :param onet_positions: :func:`data.sources.onet.parse_onet_positions` 的输出。
    """
    esco_by_name = {p["name"].lower(): p for p in esco_positions}
    onet_by_code = {p["external_id"].get("onet_code", ""): p for p in onet_positions}

    positions = []
    for config in POSITION_CONFIGS:
        esco = (
            esco_by_name.get(config["esco_query"]["title"].lower())
            if config.get("esco_query")
            else None
        )
        onet = onet_by_code.get(config["onet_code"]) if config.get("onet_code") else None

        # --- 描述与职责 ---
        if config.get("description_override"):
            description = config["description_override"]
        elif esco and esco.get("description"):
            description = esco["description"]
        elif onet and onet.get("description"):
            description = onet["description"]
        else:
            description = ""

        if onet and onet.get("responsibilities"):
            responsibilities = onet["responsibilities"]
        else:
            responsibilities = list(config["responsibilities_fallback"])

        # --- 技能要求 ---
        skill_lists = []
        if esco:
            skill_lists.append(esco["skills"])
        if onet:
            skill_lists.append(onet["skills"])
        curated = [
            {
                "skill_id": skill_id,
                "importance": float(importance),
                "required_level": int(level),
                "source": "curated",
            }
            for skill_id, importance, level in config.get("curated_skills", [])
        ]
        if curated:
            skill_lists.append(curated)
        skills = _merge_skill_maps(*skill_lists)

        # --- 外部编码与来源 ---
        external_ids: dict[str, str] = {}
        if esco:
            external_ids.update(esco.get("external_id", {}))
        if onet:
            external_ids.update(onet.get("external_id", {}))
        sources = [src for src, present in (
            ("esco", esco), ("onet", onet), ("curated", True),
        ) if present]

        positions.append(
            {
                "position_id": config["position_id"],
                "name": config["name"],
                "description": description,
                "responsibilities": responsibilities,
                "sources": sources,
                "external_ids": external_ids,
                "skills": skills,
            }
        )
    return positions
