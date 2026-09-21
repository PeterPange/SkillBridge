# SkillBridge AI

企业员工智能培训与能力发展 Agent 平台。

通过员工画像、岗位能力模型、课程资源、企业知识库和 AI Agent,实现
**能力差距分析 → 个性化课程推荐 → 学习路径规划 → 培训问答 → 学习反馈 → 动态调整** 的完整闭环。

## 核心业务模块

| # | 模块 | 说明 |
|---|------|------|
| ① | HR 业务调研与真实数据建设 | ESCO / O*NET / Microsoft Learn 数据接入,模拟员工数据 |
| ② | 统一岗位—技能体系构建 | Skill Normalization(文本标准化 + Alias + Embedding + LLM 校验) |
| ③ | HR 培训知识图谱 | Neo4j:Employee / Position / Skill / Course 及关系 |
| ④ | 员工技能画像与 Skill Gap 分析 | 技能等级 + Evidence,传统算法计算差距 |
| ⑤ | 个性化培训课程推荐 | Candidate Generation + Course Ranking |
| ⑥ | 自适应 Learning Path 生成 | 课程 DAG + 拓扑排序 + 时间约束 |
| ⑦ | 企业知识 RAG + HR Training Agent | pgvector + LangGraph Tool Calling |
| ⑧ | 培训反馈、效果评估与动态优化 | 学习记录 → 更新画像 → 重算 Gap → 动态推荐 |

## 技术栈

- **Agent 编排**:LangGraph
- **知识图谱**:Neo4j
- **向量检索**:PostgreSQL + pgvector
- **语言**:Python 3.11+

## 项目结构

```text
SkillBridge/
├── prompts/              # 设计文档与大纲
├── data/                 # 岗位/技能/课程/员工数据(阶段 1A)
│   ├── raw/              # 外部数据源拉取的原始缓存
│   └── processed/        # 标准化后的 JSON
├── skill_normalization/  # 技能归一化模块(阶段 1B)
├── knowledge_graph/      # Neo4j 图谱构建与查询(阶段 2A)
├── profile/              # 员工画像与 Skill Gap(阶段 2B)
├── recommendation/       # 课程推荐(阶段 3A)
├── learning_path/        # 学习路径规划(阶段 3B)
├── rag/                  # 企业知识库 RAG(阶段 4)
├── agent/                # HR Training Agent(LangGraph,阶段 4)
├── platform/             # HR 管理平台(占位,后续阶段)
├── skillbridge/          # 共享核心:配置与数据库连接
├── tests/                # 测试(含基础设施冒烟测试)
├── docker-compose.yml    # Neo4j + PostgreSQL(pgvector),带健康检查
├── pyproject.toml        # uv 管理的依赖与构建配置
├── .env.example          # 环境变量模板
├── Makefile              # make up / down / test
└── uv.lock               # 锁定依赖
```

## 快速开始

依赖:[uv](https://docs.astral.sh/uv/)、Docker(含 compose 插件)。

```bash
# 1. 安装依赖(Python 3.11,由 .python-version 指定)
uv sync

# 2. (可选)配置环境变量,默认值与 docker-compose.yml 一致
cp .env.example .env

# 3. 启动 Neo4j + PostgreSQL,等待健康检查通过
make up

# 4. 运行测试(含数据库冒烟测试)
make test

# 停止服务(保留数据卷)
make down
```

服务地址(默认):Neo4j Browser `http://localhost:7474`(bolt `:7687`),
PostgreSQL `localhost:5432`。

## 开发方式

使用 [Emdash](https://github.com/generalaction/emdash) 并行调度 AI 编程 Agent 开发:
每个模块在独立 Git worktree 中并行开发,审阅 diff 后合并。

## 状态

✅ 阶段 0(项目骨架)完成:uv + Python 3.11、docker-compose(Neo4j + PostgreSQL/pgvector,
带健康检查)、冒烟测试与 Makefile 就绪。业务模块按 `prompts/任务拆解.md` 逐阶段实现。
