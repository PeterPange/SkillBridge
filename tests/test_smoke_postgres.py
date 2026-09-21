"""PostgreSQL 冒烟测试:连接执行 SQL,并确认 pgvector 扩展可用。

前置条件:`make up`(即 docker compose up -d --wait)已启动 PostgreSQL。
"""

from skillbridge.db import postgres_connect


def test_postgres_connect_and_query():
    conn = postgres_connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 AS ok")
            assert cur.fetchone() == (1,)
    finally:
        conn.close()


def test_pgvector_extension_available():
    """验证使用的是 pgvector/pgvector 镜像(vector 扩展可安装)。"""
    conn = postgres_connect()
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cur.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
            row = cur.fetchone()
        conn.commit()
        assert row is not None, "vector 扩展不可用,请确认镜像为 pgvector/pgvector"
        assert row[0]
    finally:
        conn.close()
