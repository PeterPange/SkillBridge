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

✅ 阶段 3A(课程推荐)完成:`recommendation/` 实现两步推荐:
**Candidate Generation**(按 Skill Gap 从图谱沿 `TEACHES` 关系召回候选课程,
大纲示例「缺少 AI Agent → Develop AI Agents」)+ **Course Ranking**(五因子
加权打分:Gap 覆盖度 30% / 技能重要性 25% / 难度匹配 20% / 前置满足 15% /
时间成本 10%,排序确定性:总分降序 → course_id 升序)。输出 Top-K 与
逐因子推荐理由数据(覆盖缺口 / 难度匹配 / 前置状态 / 时间成本),
供 LLM 解释「为什么推荐」与 Agent 工具消费;有缺口但无课程覆盖的技能
显式进入 `uncovered_skills`,不会静默丢弃。

```bash
# 李明 → AI Engineer Top-5 推荐(需先 make up 与 make graph)
python -m recommendation EMP_001
python -m recommendation EMP_001 --top-k 3      # 指定 Top-K
python -m recommendation EMP_001 --json       # 结构化 JSON(含分项得分与理由)
```

排序为纯算法(不依赖 LLM / 数据库),可脱离 Neo4j 单测:
`recommend_from_pool()` 接受候选池直接打分排序,五因子逐个可验算。

✅ 阶段 3B(学习路径)完成:`learning_path/` 实现自适应学习路径:
复用第七节候选生成作为种子,课程 DAG 上**剪枝已掌握课程**
(掌握门槛随难度递增:beginner 平均等级 ≥ 2 / intermediate ≥ 3 /
advanced ≥ 4,与推荐模块的难度期望一致)→ **补齐必须前置课程**
(图谱传递闭包,已掌握的前置不再展开)→ **拓扑排序**(Kahn 算法,
就绪集合按「覆盖加权缺口降序 → course_id 升序」选取,核心缺口优先,
环检测兑底 CycleError)→ **每周时间约束分配**(默认每周 4 小时,
装得下整门放入、装不下移下一周、超周预算跨周续学,每周负载恒不超预算)
→ 8 周截止期限校验(超出显式提示,不静默截断)。李明(EMP_001,
每周 4 小时、截止 8 周)剪枝已掌握 2 门(Python / Docker 的 beginner 课),
14 门课程共 754 分钟,4 周完成、可按期完成,输出确定可复现。

```bash
# 李明 → AI Engineer 周计划(需先 make up 与 make graph)
python -m learning_path EMP_001
python -m learning_path EMP_001 --hours-per-week 6   # 每周 6 小时
python -m learning_path EMP_001 --weeks 12           # 截止 12 周
python -m learning_path EMP_001 --json              # 结构化 JSON(供 Agent / LLM)
```

剪枝 / 环检测 / 时间分配均为纯算法,可脱离 Neo4j 单测:
`build_learning_path()` 接受候选池与课程目录直接规划,周计划逐周可验算。

✅ 阶段 4(企业知识库 RAG)完成:`rag/` 实现大纲第九节完整链路:
**文档解析**(Markdown 原生 / Word .docx 按标题样式 / PDF 按编号模式启发式,
首个标题视为文档标题)→ **标题级分块**(块携带完整标题路径与来源,
超长小节按段落/句子边界切分,不跨标题合并)→ **Embedding + pgvector**
(复用 skill_normalization 后端:sentence-transformers 本地多语言模型,
未安装/无网络自动降级词面匹配;HNSW 余弦索引,同文档重复入库幂等替换,
维度不一致显式报错)→ **检索 + 重排**(向量 Top-K 召回 → 查询词覆盖率
线性融合重排,压下「语义相近但答非所问」的候选)→ **带来源引用的上下文**
(编号引用:文档标题 / 标题路径 / 来源文件 / 相关度,直接拼入 LLM 提示词)。

```bash
# 入库企业培训制度并自然语言提问(需先 make up)
python -m rag ingest data/fixtures/training_policy.md   # 也支持目录批量入库
python -m rag ask "新员工入职培训期是多久?"
python -m rag ask "外部培训费用怎么报销?" --top-k 3 --json
python -m rag list                                     # 已入库文档
# 换 Embedding 后端(维度变化)后重建知识库
python -m rag ingest data/fixtures/training_policy.md --reset
```

分块与检索逻辑可脱离数据库单测:`MemoryVectorStore` 与 pgvector
语义对齐(同一问题 Top-1 判定一致),pytest 固定 fixture
`data/fixtures/training_policy.md` 覆盖全部链路;pgvector 集成测试
即验收用例(入库后自然语言提问命中对应章节)。

## HR Training Agent(阶段 4,大纲第十节)

✅ 阶段 4(HR Training Agent)完成:`agent/` 实现大纲第十节——Agent
是**整个系统的智能入口和任务编排层**,LangGraph 状态机四节点:

```text
START → understand(理解需求)→ plan(规划工具调用)
      → execute(执行工具)→ generate(生成回答)→ END
```

五个工具全部委托已有模块,不重复实现业务逻辑:

| 工具 | 委托模块(大纲章节) |
|------|--------------------|
| `get_employee_profile` | `profile/`(第五节:画像 + Evidence) |
| `get_skill_gap` | `profile.gap`(第六节:纯算法差距) |
| `recommend_courses` | `recommendation/`(第七节:图谱召回 + 五因子排序) |
| `generate_learning_path` | `learning_path/`(第八节:DAG + 拓扑排序 + 周计划) |
| `rag_query` | `rag/`(第九节:pgvector 检索 + 重排 + 引用) |

两种执行模式,同一张图:LLM 配置可用(`OPENAI_API_KEY` / `LLM_MODEL`)
时走 **LLM 模式**(结构化意图提取 → function calling 规划 → 引用工具
数据作答);不可用或调用失败时**就地降级规则模式**(规则解析意图、
确定性工具链、直接串联工具输出渲染回答),主流程不中断,结果可复现。

```bash
# 大纲第十节示例问题(默认规则模式,不依赖 LLM)
python -m agent "我是Java后端,想转AI Engineer,每周4小时,帮我规划"

# 强制规则模式 / 结构化输出 / 制度类问题(追加 RAG 工具)
python -m agent "帮我规划" --rule --quiet
python -m agent "帮我规划" --json
python -m agent "为什么给我推荐 AI Agent 课程?公司的培训制度有什么规定?"
```

验收:示例问题走通全链路,回答引用李明的真实数据——岗位准备度
**29.6%**、**12 项**能力缺口、**Top-5** 课程推荐、**8 周**截止同课表;
Neo4j / PostgreSQL 不可用时工具显式报告而非崩溃,RAG 在 Embedding
模型不可用时自动降级「内存库 + 词面编码 + 内置培训制度文档」
(离线防挂起:模块加载即声明 `HF_HUB_OFFLINE=1`,尊重用户显式配置)。
pytest 覆盖工具编排、LLM 模式(桩客户端)、降级链路与 CLI。
