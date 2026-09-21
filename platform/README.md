# platform/ —— HR 管理平台(占位)

对应大纲第十二节:员工端(个人画像 / Skill Gap / 推荐课程 / 学习路径 / AI Agent)
与 HR 端(员工管理 / 岗位能力模型 / 培训计划 / 团队能力分析)。

当前为空目录占位,后续阶段实现。

> ⚠️ 实现注意:本目录**不要**添加 `__init__.py` 做成顶层 Python 包。
> `platform` 与 Python 标准库模块同名,从项目根目录运行 Python
> (`python -m ...`、`python -c ...`)时会遮蔽标准库,导致 pytest、
> pip 等工具崩溃。建议将本目录作为纯前端工程,后端 API 放到
> `agent/` 或独立命名的包(如 `platform_api/`)中。
