"""数据库连接工厂。

骨架阶段供冒烟测试使用;后续各业务模块(knowledge_graph / rag 等)
统一从这里获取连接,避免连接配置散落各处。
"""

from __future__ import annotations

import psycopg
from neo4j import Driver, GraphDatabase

from skillbridge.config import Settings, get_settings


def neo4j_driver(settings: Settings | None = None) -> Driver:
    """创建 Neo4j 驱动(调用方负责 close)。"""
    s = settings or get_settings()
    return GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))


def postgres_connect(settings: Settings | None = None) -> psycopg.Connection:
    """创建 PostgreSQL 连接(调用方负责 close)。"""
    s = settings or get_settings()
    return psycopg.connect(
        host=s.postgres_host,
        port=s.postgres_port,
        user=s.postgres_user,
        password=s.postgres_password,
        dbname=s.postgres_db,
    )
