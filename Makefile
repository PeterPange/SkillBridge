# SkillBridge 常用命令
# 依赖:uv(https://docs.astral.sh/uv/)、Docker(含 compose 插件)

COMPOSE ?= docker compose

.PHONY: up down test collect collect-offline graph recommend path rag agent feedback

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

path: ## 自适应学习路径周计划(需先 make up 与 make graph)
	uv run python -m learning_path EMP_001

rag: ## 企业知识库 RAG 演示:入库培训制度并示例提问(需先 make up)
	uv run python -m rag ingest data/fixtures/training_policy.md data/fixtures/ai_engineer_position.md
	uv run python -m rag ask "新员工入职培训期是多久?"

agent: ## HR Training Agent 演示:大纲第十节示例问题(需先 make up 与 make graph)
	uv run python -m agent "我是Java后端,想转AI Engineer,每周4小时,帮我规划"

feedback: ## 培训反馈闭环演示:完成 3 门课程并对比学习路径(需先 make up 与 make graph)
	uv run python -m feedback complete EMP_001 CRS_001 --score 85
	uv run python -m feedback complete EMP_001 CRS_003 --score 85
	uv run python -m feedback complete EMP_001 CRS_004 --score 85
	uv run python -m feedback status EMP_001
	uv run python -m feedback plan-diff EMP_001
