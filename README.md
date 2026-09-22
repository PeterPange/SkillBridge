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
- **技能归一化**:sentence-transformers(本地多语言 Embedding,离线自动降级)
- **语言**:Python 3.11+

## 项目结构

```text
SkillBridge/
├── prompts/              # 设计文档与大纲
├── data/                 # 岗位/技能/课程/员工数据(阶段 1A)
│   ├── collect.py        # 采集入口:python -m data.collect
│   ├── sources/          # 外部数据源适配(ESCO / O*NET / Microsoft Learn)
│   ├── fixtures/         # 离线 fixture(真实 API 响应裁剪版)
│   ├── raw/              # 外部数据源拉取的原始缓存
│   └── processed/        # 标准化后的 JSON(含 schemas/)
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

## 数据采集(阶段 1A)

```bash
# 采集岗位/技能/课程/员工四类数据(在线优先,断网自动回退)
make collect              # 等价于 uv run python -m data.collect
make collect-offline      # 强制离线:仅用 data/raw/ 缓存与内置 fixture
```

数据源与产出:

| 数据 | 来源 | 产出 |
|------|------|------|
| 岗位与技能 | ESCO API + O*NET Web Services(可选凭据)+ 人工策展 | `data/processed/skills.json`、`positions.json` |
| 课程 | Microsoft Learn Catalog API + 课程页学习目标 | `data/processed/courses.json` |
| 员工 | 模拟生成器(10 名,等级 0-4 + Evidence) | `data/processed/employees.json` |

三级数据源调度:**在线 API → `data/raw/` 缓存 → 内置 fixture**(`data/fixtures/`,
为真实 API 响应裁剪版),断网不阻塞;产出全部通过统一 JSON Schema
(`data/processed/schemas/`)与跨文件引用校验。O*NET API 凭据可选
(`ONET_API_USERNAME` / `ONET_API_PASSWORD`,见 `.env.example`)。

## 知识图谱(阶段 2A)

```bash
make collect && make graph    # 采集数据并导入 Neo4j(需先 make up)
```

图模型(大纲第四节):

```text
(:Employee)-[:HAS_SKILL {level, ...evidence}]->(:Skill)
(:Employee)-[:CURRENT_POSITION / :TARGET_POSITION]->(:Position)
(:Position)-[:REQUIRES {importance, required_level}]->(:Skill)
(:Course)-[:TEACHES]->(:Skill)
(:Course)-[:PREREQUISITE]->(:Course)
```

查询接口(CLI 或 `knowledge_graph.queries` Python API):

| 查询 | CLI | Python API |
|------|-----|------------|
| 岗位技能要求 | `python -m knowledge_graph position "AI Engineer"` | `position_required_skills()` |
| 课程覆盖技能 | `python -m knowledge_graph course "Develop AI Agents"` | `course_taught_skills()` |
| 前置链路(传递闭包,拓扑序) | 同上,`course` 子命令一并输出 | `course_prerequisite_chain()` |
| 教授指定技能的课程 | `python -m knowledge_graph skill "AI Agent"` | `courses_teaching_skill()` |

名称解析支持 ID / 名称(忽略大小写)/ 别名 / 包含 / 词元模糊:
大纲示例「Develop AI Agents」自动解析到真实课程
「Build and extend AI agents with Microsoft Foundry」,中文别名「智能体」
解析到技能 AI Agent。构建脚本可重复执行(MERGE 幂等,默认整库重建)。

## 开发方式

使用 [Emdash](https://github.com/generalaction/emdash) 并行调度 AI 编程 Agent 开发:
每个模块在独立 Git worktree 中并行开发,审阅 diff 后合并。

## 状态

✅ 阶段 0(项目骨架)完成:uv + Python 3.11、docker-compose(Neo4j + PostgreSQL/pgvector,
带健康检查)、冒烟测试与 Makefile 就绪。业务模块按 `prompts/任务拆解.md` 逐阶段实现。

✅ 阶段 1B(技能归一化)完成:`skill_normalization/` 实现
文本标准化(大小写/全半角/标点/中英文别名表与同义词表)、Embedding 相似度匹配
(sentence-transformers 本地多语言模型,未安装或无网络时自动降级词面匹配)、
LLM 语义校验(可选开关,无 API key 自动跳过)与统一 skill_id 映射表输出。
GenAI / Generative AI / 生成式AI 等输入全部归一到同一 `SKILL_004`。

```bash
# 批量归一化并输出映射表(默认 data/processed/skill_id_map.json)
python -m skill_normalization "GenAI" "生成式AI" --no-llm
```

✅ 阶段 2A(知识图谱)完成:`knowledge_graph/` 实现
Employee / Position / Skill / Course 四类节点与 HAS_SKILL / REQUIRES /
TEACHES / PREREQUISITE(及 CURRENT_POSITION / TARGET_POSITION)关系,
`make graph` 从 `data/processed/` 一键导入;查询接口支持
「AI Engineer 需要什么技能」「Develop AI Agents 的前置课程」等验收查询,
名称解析含词元模糊(大纲示例名 → 真实课程名)。

✅ 阶段 2B(画像与 Skill Gap)完成:`profile/` 实现员工画像
(技能等级 0-4 + 四类 Evidence:技能考试 / 项目经历 / 员工自评 / 培训记录,
可解释「为什么认为你是 Level N」)与纯算法 Skill Gap 计算
(目标岗位要求等级 − 当前等级,未登记技能按 0 计),输出结构化差距报告
(缺失技能 + 差距值 + 重要度 + 岗位准备度),作为课程推荐模块的输入。

```bash
# 李明 → AI Engineer 差距报告(优先读 data/processed,缺失时自动回退离线 fixture)
python -m profile EMP_001
python -m profile EMP_001 --json                # 结构化 JSON 报告
python -m profile EMP_001 --explain SKILL_001   # 单项技能 Evidence 解释
python -m profile --list                        # 列出全部员工
```
