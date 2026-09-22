"""统一技能库(大纲第二节「技能数据」+ 第三节「统一 Skill ID」)。

SkillBridge 的岗位、员工、课程、培训记录全部引用统一的 ``skill_id``,
本模块维护技能注册表与「外部技能标签 → 统一技能」的别名匹配。

数据来源(与大纲一致):
- ESCO Skill(岗位详情中的 essential/optional 技能标签)
- O*NET Technology Skill(technology_skills 中的工具/语言示例)
- 人工补充的企业技能(curated)

完整的模糊归一化(Embedding 相似度 + LLM 校验)属于阶段 1B
``skill_normalization/`` 模块;本阶段使用精确别名表完成归一,
保证三类数据从一开始就落在统一技能体系上。
"""

from __future__ import annotations

import re
from functools import lru_cache

#: 技能类别(用于分组展示与检索)
CATEGORIES = (
    "programming-language",  # 编程语言
    "database",  # 数据库
    "ai-ml",  # AI / 机器学习
    "platform",  # 基础设施与平台
    "engineering-practice",  # 工程实践
    "data",  # 数据工程
    "governance",  # 治理与合规
)

#: 统一技能注册表。
#: aliases 为小写标准化后的外部标签(ESCO/O*NET/常见写法),用于精确匹配。
SKILL_REGISTRY: list[dict] = [
    {
        "skill_id": "SKILL_001",
        "name": "Python",
        "category": "programming-language",
        "description": "使用 Python 进行软件开发、数据处理与 AI 应用编程。",
        "aliases": ["python", "python3", "python (computer programming)", "python 语言"],
    },
    {
        "skill_id": "SKILL_002",
        "name": "Java",
        "category": "programming-language",
        "description": "使用 Java 进行企业级后端服务开发。",
        "aliases": ["java", "java (computer programming)", "java 语言"],
    },
    {
        "skill_id": "SKILL_003",
        "name": "SQL",
        "category": "database",
        "description": "关系型数据库查询、建模与优化(SQL/Transact-SQL/PostgreSQL 等)。",
        "aliases": [
            "sql", "query languages", "transact-sql", "t-sql", "postgresql", "mysql",
            "sql server", "oracle database", "oracle relational database", "db2",
            "database management systems", "mongodb", "cassandra",
        ],
    },
    {
        "skill_id": "SKILL_004",
        "name": "Machine Learning",
        "category": "ai-ml",
        "description": "机器学习:模型训练、评估与特征工程。",
        "aliases": [
            "machine learning", "ml", "ml (computer programming)", "utilise machine learning",
            "apply machine learning techniques", "tensorflow", "pytorch", "scikit-learn", "xgboost",
        ],
    },
    {
        "skill_id": "SKILL_005",
        "name": "Deep Learning",
        "category": "ai-ml",
        "description": "深度学习:神经网络结构与训练。",
        "aliases": ["deep learning", "neural networks", "神经网络"],
    },
    {
        "skill_id": "SKILL_006",
        "name": "Generative AI",
        "category": "ai-ml",
        "description": "生成式 AI:生成模型原理、能力边界与典型应用场景。",
        "aliases": [
            "generative ai", "genai", "generative artificial intelligence",
            "生成式人工智能", "生成式ai",
        ],
    },
    {
        "skill_id": "SKILL_007",
        "name": "Large Language Models",
        "category": "ai-ml",
        "description": "大语言模型:提示词、Token、补全与模型能力调优。",
        "aliases": ["large language models", "large language model", "llm", "llms"],
    },
    {
        "skill_id": "SKILL_008",
        "name": "RAG",
        "category": "ai-ml",
        "description": "检索增强生成:向量检索、知识接地与 RAG 管道构建。",
        "aliases": [
            "rag", "retrieval augmented generation", "retrieval-augmented generation",
            "检索增强生成",
        ],
    },
    {
        "skill_id": "SKILL_009",
        "name": "AI Agent",
        "category": "ai-ml",
        "description": "AI 智能体:工具调用、多智能体协作与 Agent 工作流编排。",
        "aliases": [
            "ai agent", "ai agents", "agent development", "agentic ai", "build ai agents",
            "智能体", "ai 智能体",
        ],
    },
    {
        "skill_id": "SKILL_010",
        "name": "Prompt Engineering",
        "category": "ai-ml",
        "description": "提示词工程:面向 LLM 的提示设计与优化。",
        "aliases": ["prompt engineering", "prompt design", "提示词工程"],
    },
    {
        "skill_id": "SKILL_011",
        "name": "Docker",
        "category": "platform",
        "description": "容器化:镜像构建、容器运行与分发。",
        "aliases": ["docker", "docker containers", "containerization", "containers", "容器"],
    },
    {
        "skill_id": "SKILL_012",
        "name": "Kubernetes",
        "category": "platform",
        "description": "容器编排:集群、工作负载与弹性伸缩。",
        "aliases": [
            "kubernetes", "k8s", "container orchestration", "azure kubernetes service", "aks",
        ],
    },
    {
        "skill_id": "SKILL_013",
        "name": "API Development",
        "category": "engineering-practice",
        "description": "API 设计与开发(REST/OpenAPI/Web 服务)。",
        "aliases": [
            "api", "rest api", "rest apis", "restful apis", "web api", "api development",
            "web services", "restful web services", "openapi",
        ],
    },
    {
        "skill_id": "SKILL_014",
        "name": "Cloud Computing",
        "category": "platform",
        "description": "云计算:云服务、部署与云原生架构(Azure/AWS/GCP)。",
        "aliases": [
            "cloud computing", "cloud technologies", "use ict cloud", "cloud", "microsoft azure",
            "azure", "amazon web services", "aws", "google cloud platform", "gcp", "云计算",
        ],
    },
    {
        "skill_id": "SKILL_015",
        "name": "Monitoring",
        "category": "engineering-practice",
        "description": "可观测性与监控:指标、告警与性能分析。",
        "aliases": [
            "monitoring", "observability", "application monitoring", "prometheus", "grafana",
            "nagios", "zabbix", "datadog", "azure monitor",
        ],
    },
    {
        "skill_id": "SKILL_016",
        "name": "CI/CD",
        "category": "engineering-practice",
        "description": "持续集成 / 持续部署:流水线与配置管理。",
        "aliases": [
            "ci/cd", "cicd", "continuous integration", "continuous delivery",
            "continuous deployment", "devops", "jenkins", "ansible", "terraform", "github actions",
            "puppet (tools for software configuration management)",
            "salt (tools for software configuration management)",
        ],
    },
    {
        "skill_id": "SKILL_017",
        "name": "Data Engineering",
        "category": "data",
        "description": "数据工程:ETL、数据管道与大数据处理。",
        "aliases": [
            "data engineering", "etl", "data pipelines", "data processing", "big data",
            "data mining", "perform data mining", "data models", "create data models",
            "develop data processing applications", "business intelligence", "manage data",
            "unstructured data", "integrate ict data",
            "data extraction, transformation and loading tools", "apache spark", "spark", "hadoop",
        ],
    },
    {
        "skill_id": "SKILL_018",
        "name": "AI Governance",
        "category": "governance",
        "description": "AI 治理:负责任 AI、风险评估与合规。",
        "aliases": [
            "ai governance", "responsible ai", "responsible artificial intelligence", "ai ethics",
            "ai safety", "ai risk management",
        ],
    },
]


def normalize_label(label: str) -> str:
    """外部技能标签的文本标准化:小写、压缩空白、去首尾标点。"""
    text = label.strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip(" .;:,")


@lru_cache(maxsize=1)
def _alias_index() -> dict[str, str]:
    """alias(标准化后)→ skill_id。"""
    index: dict[str, str] = {}
    for skill in SKILL_REGISTRY:
        index[normalize_label(skill["name"])] = skill["skill_id"]
        for alias in skill["aliases"]:
            index[normalize_label(alias)] = skill["skill_id"]
    return index


def match_skill(label: str) -> str | None:
    """将外部技能标签精确匹配到统一 skill_id;未命中返回 ``None``。

    匹配规则:标准化(大小写/空白)后查别名表。
    模糊与语义匹配由阶段 1B 的 ``skill_normalization`` 负责。
    """
    return _alias_index().get(normalize_label(label))


def get_skill(skill_id: str) -> dict:
    """按 skill_id 取技能定义;不存在抛 ``KeyError``。"""
    for skill in SKILL_REGISTRY:
        if skill["skill_id"] == skill_id:
            return skill
    raise KeyError(f"未知技能: {skill_id}")


def all_skill_ids() -> list[str]:
    """全部统一技能 ID(按注册顺序)。"""
    return [skill["skill_id"] for skill in SKILL_REGISTRY]


def build_skill_library(provenance: dict[str, set[str]] | None = None) -> list[dict]:
    """输出统一技能库记录(供 ``skills.json`` 落盘)。

    :param provenance: ``skill_id → 来源集合``,如
        ``{"SKILL_001": {"esco", "onet"}}``;未出现的技能默认来源为 ``curated``。
    """
    provenance = provenance or {}
    records = []
    for skill in SKILL_REGISTRY:
        sources = provenance.get(skill["skill_id"], set()) | {"curated"}
        records.append(
            {
                "skill_id": skill["skill_id"],
                "name": skill["name"],
                "category": skill["category"],
                "description": skill["description"],
                "aliases": sorted(skill["aliases"]),
                "sources": sorted(sources),
            }
        )
    return records
