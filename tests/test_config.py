"""配置加载测试(不依赖数据库)。"""

from skillbridge.config import Settings, get_settings


def test_defaults_match_compose_defaults():
    """代码内默认值必须与 docker-compose.yml / .env.example 一致。"""
    s = Settings()
    assert s.neo4j_uri == "bolt://localhost:7687"
    assert s.neo4j_user == "neo4j"
    assert s.neo4j_password == "skillbridge"
    assert s.neo4j_database == "neo4j"
    assert s.postgres_host == "localhost"
    assert s.postgres_port == 5432
    assert s.postgres_user == "skillbridge"
    assert s.postgres_password == "skillbridge"
    assert s.postgres_db == "skillbridge"


def test_from_env_reads_overrides(monkeypatch):
    monkeypatch.setenv("NEO4J_URI", "bolt://neo4j.example:7687")
    monkeypatch.setenv("NEO4J_PASSWORD", "secret")
    monkeypatch.setenv("POSTGRES_PORT", "6543")
    s = Settings.from_env()
    assert s.neo4j_uri == "bolt://neo4j.example:7687"
    assert s.neo4j_password == "secret"
    assert s.postgres_port == 6543


def test_empty_env_value_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("NEO4J_PASSWORD", "")
    s = Settings.from_env()
    assert s.neo4j_password == "skillbridge"


def test_get_settings_is_cached():
    assert get_settings() is get_settings()
