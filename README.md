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

## 项目结构(规划)

```text
SkillBridge/
├── prompts/            # 设计文档与大纲
├── data/               # 岗位/技能/课程/员工数据
├── skill_normalization/# 技能归一化模块
├── knowledge_graph/    # Neo4j 图谱构建与查询
├── profile/            # 员工画像与 Skill Gap
├── recommendation/     # 课程推荐
├── learning_path/      # 学习路径规划
├── rag/                # 企业知识库 RAG
├── agent/              # HR Training Agent (LangGraph)
└── platform/           # HR 管理平台(员工端/HR端)
```

## 开发方式

使用 [Emdash](https://github.com/generalaction/emdash) 并行调度 AI 编程 Agent 开发:
每个模块在独立 Git worktree 中并行开发,审阅 diff 后合并。

## 状态

🚧 项目启动阶段,当前仅有设计大纲,见 `prompts/大纲.md`。
