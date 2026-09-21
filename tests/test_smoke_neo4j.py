"""Neo4j 冒烟测试:连接并执行一条 Cypher 查询。

前置条件:`make up`(即 docker compose up -d --wait)已启动 Neo4j。
"""

from skillbridge.db import neo4j_driver


def test_neo4j_connect_and_query():
    driver = neo4j_driver()
    try:
        with driver.session() as session:
            record = session.run("RETURN 1 AS ok").single()
            assert record is not None
            assert record["ok"] == 1
    finally:
        driver.close()
