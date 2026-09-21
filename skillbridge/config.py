"""集中式配置:从环境变量(可选 .env)读取。

默认值与 docker-compose.yml 中的默认值保持一致,
因此 `docker compose up -d` 之后无需创建 .env 即可运行测试。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# 加载项目根目录下的 .env(若存在;不覆盖已导出的环境变量)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _env(key: str, default: str) -> str:
    """读取环境变量,空字符串视为未设置。"""
    value = os.getenv(key)
    return default if value is None or value == "" else value


@dataclass(frozen=True)
class Settings:
    """SkillBridge 全局配置。

    骨架阶段仅包含基础设施连接项;后续阶段的配置
    (LLM、数据目录等)在此统一扩展。
    """

    # --- Neo4j ---
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "skillbridge"
    neo4j_database: str = "neo4j"

    # --- PostgreSQL(pgvector)---
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "skillbridge"
    postgres_password: str = "skillbridge"
    postgres_db: str = "skillbridge"

    # --- LLM(阶段 1B / 4 使用,可选)---
    openai_api_key: str = ""
    openai_base_url: str = ""
    llm_model: str = ""
    embedding_model: str = ""

    # --- 应用 ---
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            neo4j_uri=_env("NEO4J_URI", cls.neo4j_uri),
            neo4j_user=_env("NEO4J_USER", cls.neo4j_user),
            neo4j_password=_env("NEO4J_PASSWORD", cls.neo4j_password),
            neo4j_database=_env("NEO4J_DATABASE", cls.neo4j_database),
            postgres_host=_env("POSTGRES_HOST", cls.postgres_host),
            postgres_port=int(_env("POSTGRES_PORT", str(cls.postgres_port))),
            postgres_user=_env("POSTGRES_USER", cls.postgres_user),
            postgres_password=_env("POSTGRES_PASSWORD", cls.postgres_password),
            postgres_db=_env("POSTGRES_DB", cls.postgres_db),
            openai_api_key=_env("OPENAI_API_KEY", ""),
            openai_base_url=_env("OPENAI_BASE_URL", ""),
            llm_model=_env("LLM_MODEL", ""),
            embedding_model=_env("EMBEDDING_MODEL", ""),
            log_level=_env("LOG_LEVEL", cls.log_level),
        )


_SETTINGS: Settings | None = None


def get_settings() -> Settings:
    """返回全局 Settings 单例(首次调用时从环境读取)。"""
    global _SETTINGS
    if _SETTINGS is None:
        _SETTINGS = Settings.from_env()
    return _SETTINGS
