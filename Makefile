# SkillBridge 常用命令
# 依赖:uv(https://docs.astral.sh/uv/)、Docker(含 compose 插件)

COMPOSE ?= docker compose

.PHONY: up down test

up: ## 启动 Neo4j + PostgreSQL,等待健康检查通过
	$(COMPOSE) up -d --wait

down: ## 停止并移除容器(保留数据卷)
	$(COMPOSE) down

test: ## 运行测试(需先 make up)
	uv run pytest
