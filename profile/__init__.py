"""员工画像与 Skill Gap 分析模块(大纲第五、六节,阶段 2B)。

Knowledge Graph 是公共知识,Employee Profile 是个人状态:

- **员工画像**:技能等级(0-4)+ 四类 Evidence(技能考试 / 项目经历 /
  员工自评 / 培训记录),可解释「为什么认为你是 Level N」;
- **Skill Gap**:纯算法(不使用 LLM)计算目标岗位要求等级与当前等级
  的差距,输出结构化差距报告(缺失技能 + 差距值),作为课程推荐
  模块(大纲第七节)的输入。

入口::

    python -m profile EMP_001            # 李明 → AI Engineer 差距报告
    python -m profile --list             # 列出全部员工
    python -m profile EMP_001 --json     # 结构化 JSON 输出
    python -m profile EMP_001 --explain SKILL_001   # 单项技能 Evidence 解释

结构::

    profile/
    ├── models.py    领域模型(Evidence / 画像 / 岗位要求 / 差距 / 报告)
    ├── loader.py    JSON 记录 → 领域对象(校验 + skilllib 补全)
    ├── gap.py       Skill Gap 纯算法计算 + 结构化报告
    ├── report.py    文本渲染(差距报告 / Evidence 解释)
    └── __main__.py  CLI 入口
"""

from profile.gap import build_gap_report, calculate_skill_gaps
from profile.loader import build_employee_profile, build_position_requirements
from profile.models import (
    EmployeeProfile,
    ExtraSkill,
    GapReport,
    MetSkill,
    PositionRequirement,
    SkillAssessment,
    SkillEvidence,
    SkillGap,
)
from profile.report import render_evidence_explanation, render_gap_report

__all__ = [
    "EmployeeProfile",
    "SkillAssessment",
    "SkillEvidence",
    "PositionRequirement",
    "SkillGap",
    "MetSkill",
    "ExtraSkill",
    "GapReport",
    "build_employee_profile",
    "build_position_requirements",
    "calculate_skill_gaps",
    "build_gap_report",
    "render_gap_report",
    "render_evidence_explanation",
]
