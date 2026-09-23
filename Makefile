# SkillBridge 常用命令
# 依赖:uv(https://docs.astral.sh/uv/)、Docker(含 compose 插件)

COMPOSE ?= docker compose

.PHONY: up down test collect collect-offline graph recommend

up: ## 启动 Neo4j + PostgreSQL,等待健康检查通过
	$(COMPOSE) up -d --wait

down: ## 停止并移除容器(保留数据卷)
	$(COMPOSE) down

test: ## 运行测试(需先 make up)
	uv run pytest

collect: ## 数据采集:在线优先,断网自动回退缓存/fixture
	uv run python -m data.collect

collect-offline: ## 数据采集:强制离线(缓存/fixture,不发起网络请求)
	uv run python -m data.collect --offline

graph: ## 构建知识图谱(需先 make up 和 make collect)
	uv run python -m knowledge_graph build

recommend: ## 个性化课程推荐 Top-K(需先 make up 与 make graph)
	uv run python -m recommendation EMP_001
