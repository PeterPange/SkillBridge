"""需求理解(大纲第十节「理解需求」节点)。

把自然语言问题解析为结构化意图:**谁**(员工)、**去哪**(目标岗位)、
**多快**(每周可学时长 / 截止周数)、**要什么**(规划 / 推荐 / 问答)。

两套实现,接口一致:

- :func:`parse_intent_rules`  规则模式(正则 + 名称匹配,零依赖,
  LLM 不可用时的降级方案,也是 LLM 结果的校验兜底);
- :func:`parse_intent_llm`    LLM 模式(结构化输出 JSON,失败自动
  回退规则模式)。

示例(大纲第十节验收问题)::

    "我是Java后端,想转AI Engineer,每周4小时,帮我规划"
      → 李明(EMP_001) → AI Engineer,每周 4 小时,截止 8 周,要完整规划
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from agent.llm import LLMClient, LLMError
from agent.tools import load_business_data

#: 未指明员工时的默认演示员工(大纲验收:李明 EMP_001)
DEFAULT_EMPLOYEE_ID = "EMP_001"

#: 常见中文岗位说法 → 统一岗位库 position_id(大小写 / 空格已归一)
POSITION_ALIASES: dict[str, str] = {
    "ai工程师": "AI Engineer",
    "人工智能工程师": "AI Engineer",
    "aiengineer": "AI Engineer",
    "后端开发": "Software Developer",
    "后端工程师": "Software Developer",
    "java后端": "Software Developer",
    "软件开发": "Software Developer",
    "数据科学家": "Data Scientist",
    "运维工程师": "DevOps Engineer",
    "devops": "DevOps Engineer",
    "数据库开发": "Database Developer",
}

#: 每周时长模式,如「每周4小时」「每星期 4.5 个小时」
_HOURS_RE = re.compile(
    r"每(?:周|星期)\s*(\d+(?:\.\d+)?)\s*(?:个)?\s*(?:小时|h|hour)", re.IGNORECASE
)
#: 截止周数模式,如「8周」「8 周」(先剔除「每周X小时」避免误匹配)
_WEEKS_RE = re.compile(r"(\d+)\s*周")
#: 规划类意图关键词
_PLAN_KEYWORDS = ("规划", "计划", "路径", "课表", "安排", "帮我规划")
#: 推荐类意图关键词
_RECOMMEND_KEYWORDS = ("推荐", "学什么", "课程", "top")
#: 知识库问答类意图关键词(企业制度 / 岗位说明 / 为什么)
_QA_KEYWORDS = ("制度", "规定", "政策", "报销", "手册", "为什么", "岗位说明", "职责")


def _normalize(text: str) -> str:
    """归一化文本用于匹配:小写 + 去空白与常见分隔符。"""
    return re.sub(r"[\s\-_/·,，。:：]+", "", text or "").lower()


@dataclass(frozen=True)
class Intent:
    """结构化需求意图(规划工具调用与渲染回答的依据)。"""

    employee_id: str
    employee_name: str
    current_position_id: str
    current_position_name: str
    target_position_id: str
    target_position_name: str
    hours_per_week: float = 4.0
    deadline_weeks: int = 8
    wants_plan: bool = False
    wants_recommendation: bool = False
    wants_qa: bool = False
    question: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "employee_id": self.employee_id,
            "employee_name": self.employee_name,
            "current_position_id": self.current_position_id,
            "current_position_name": self.current_position_name,
            "target_position_id": self.target_position_id,
            "target_position_name": self.target_position_name,
            "hours_per_week": self.hours_per_week,
            "deadline_weeks": self.deadline_weeks,
            "wants_plan": self.wants_plan,
            "wants_recommendation": self.wants_recommendation,
            "wants_qa": self.wants_qa,
            "question": self.question,
        }


def _resolve_employee(
    question: str,
    employees: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any]:
    """从问题中解析员工:员工 ID → 姓名精确匹配 → 默认演示员工。"""
    normalized = _normalize(question)
    # 1) 显式员工 ID(如 EMP_001 / emp001)
    id_match = re.search(r"emp[_\-]?\d+", normalized)
    if id_match:
        compact = id_match.group().replace("_", "").replace("-", "")
        for employee in employees:
            if employee["employee_id"].lower().replace("_", "") == compact:
                return employee
    # 2) 姓名精确匹配(如「李明」)
    for employee in employees:
        if employee["name"] in question:
            return employee
    # 3) 未指明 → 默认演示员工(李明)
    default = next(
        (e for e in employees if e["employee_id"] == DEFAULT_EMPLOYEE_ID), employees[0]
    )
    return default


def _resolve_target_position(
    question: str,
    positions: Sequence[Mapping[str, Any]],
    employee: Mapping[str, Any],
) -> Mapping[str, Any]:
    """解析目标岗位:岗位名 / 中文别名匹配 → 员工档案里的目标岗位。"""
    normalized = _normalize(question)
    for position in positions:
        if _normalize(position["name"]) in normalized:
            return position
    for alias, position_name in POSITION_ALIASES.items():
        if alias in normalized:
            for position in positions:
                if position["name"] == position_name:
                    return position
    # 未识别出目标岗位 → 用员工档案登记的目标岗位(如李明 → AI Engineer)
    for position in positions:
        if position["position_id"] == employee["target_position_id"]:
            return position
    raise LookupError(
        f"员工 {employee['employee_id']} 的目标岗位 "
        f"{employee['target_position_id']} 不在岗位库中"
    )


def parse_intent_rules(question: str) -> Intent:
    """规则模式需求理解:正则 + 名称匹配(零依赖,确定性输出)。

    :param question: 用户原始问题。
    :raises LookupError: 员工档案的目标岗位不在岗位库中(数据异常)。
    """
    positions, employees = load_business_data()
    positions_by_id = {position["position_id"]: position for position in positions}
    employee = _resolve_employee(question, employees)
    target = _resolve_target_position(question, positions, employee)
    current = positions_by_id.get(employee["current_position_id"], {})

    # 每周可学时长(默认 4 小时,大纲第八节)
    hours = 4.0
    if match := _HOURS_RE.search(question):
        hours = float(match.group(1))

    # 截止周数:剔除「每周X小时」后取「N周」(默认 8 周,大纲第八节示例)
    weeks = 8
    residual = _HOURS_RE.sub("", question)
    if match := _WEEKS_RE.search(residual):
        weeks = max(1, int(match.group(1)))

    wants_plan = any(k in question for k in _PLAN_KEYWORDS)
    wants_recommendation = any(k in question for k in _RECOMMEND_KEYWORDS)
    wants_qa = any(k in question for k in _QA_KEYWORDS)
    # 「帮我规划」隐含推荐 + 课表;纯推荐问题不强制排课表
    if wants_plan:
        wants_recommendation = True

    return Intent(
        employee_id=employee["employee_id"],
        employee_name=employee["name"],
        current_position_id=employee["current_position_id"],
        current_position_name=str(current.get("name", employee["current_position_id"])),
        target_position_id=target["position_id"],
        target_position_name=target["name"],
        hours_per_week=hours,
        deadline_weeks=weeks,
        wants_plan=wants_plan,
        wants_recommendation=wants_recommendation,
        wants_qa=wants_qa,
        question=question,
    )


def parse_intent_llm(question: str, client: LLMClient) -> Intent:
    """LLM 模式需求理解:结构化输出 JSON,解析 / 校验失败回退规则模式。

    :param question: 用户原始问题。
    :param client: 可用的 LLM 客户端。
    :raises LLMError: LLM 调用失败(调用方捕获后降级规则模式)。
    """
    positions, employees = load_business_data()
    employee_lines = [
        f"- {e['employee_id']}: {e['name']}({e['department']},"
        f"当前 {e['current_position_id']})"
        for e in employees
    ]
    position_lines = [
        f"- {p['position_id']}: {p['name']}" for p in positions
    ]
    system = (
        "你是企业 HR 培训系统的需求理解模块。从用户问题中提取结构化意图,"
        "只输出 JSON,不要输出其他内容。"
    )
    user = (
        f"用户问题:{question}\n\n"
        f"员工列表:\n" + "\n".join(employee_lines) + "\n\n"
        f"岗位列表:\n" + "\n".join(position_lines) + "\n\n"
        "规则:\n"
        "- employee_id 必须来自员工列表;问题未指明员工时选择最匹配的一位,"
        "  无法判断时用 EMP_001;\n"
        "- target_position 必须是岗位列表中的岗位名;未提及目标岗位时输出空;\n"
        "- hours_per_week 为每周可学习小时数(数字,未提及用 4);\n"
        "- deadline_weeks 为培训截止周数(数字,未提及用 8);\n"
        "- wants_plan:是否需要完整学习规划(课表);wants_recommendation:是否需要课程推荐;"
        "wants_qa:是否在问公司制度 / 岗位说明 / 为什么这类知识库问题。\n\n"
        '输出 JSON:{"employee_id": "EMP_XXX", "target_position": "岗位名或空",'
        '"hours_per_week": 4, "deadline_weeks": 8,'
        '"wants_plan": true, "wants_recommendation": true, "wants_qa": false}'
    )
    response = client.chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}]
    )
    data = _extract_json(response.content)
    if data is None:
        raise LLMError(f"LLM 需求理解输出不是合法 JSON: {response.content!r:.200}")

    # 规则模式结果作为校验兜底:LLM 字段非法时逐项回退
    fallback = parse_intent_rules(question)
    known_employees = {e["employee_id"]: e for e in employees}
    employee = known_employees.get(str(data.get("employee_id", "")).strip())
    if employee is None:
        employee = known_employees[fallback.employee_id]

    target = fallback.target_position_id
    target_name = fallback.target_position_name
    raw_position = str(data.get("target_position") or "").strip()
    if raw_position:
        for position in positions:
            if _normalize(position["name"]) == _normalize(raw_position):
                target, target_name = position["position_id"], position["name"]
                break

    try:
        hours = float(data.get("hours_per_week", fallback.hours_per_week))
    except (TypeError, ValueError):
        hours = fallback.hours_per_week
    if not 0 < hours <= 40:
        hours = fallback.hours_per_week
    try:
        weeks = int(data.get("deadline_weeks", fallback.deadline_weeks))
    except (TypeError, ValueError):
        weeks = fallback.deadline_weeks
    if not 1 <= weeks <= 52:
        weeks = fallback.deadline_weeks

    return Intent(
        employee_id=employee["employee_id"],
        employee_name=employee["name"],
        current_position_id=employee["current_position_id"],
        current_position_name=fallback.current_position_name,
        target_position_id=target,
        target_position_name=target_name,
        hours_per_week=hours,
        deadline_weeks=weeks,
        wants_plan=bool(data.get("wants_plan", fallback.wants_plan)),
        wants_recommendation=bool(
            data.get("wants_recommendation", fallback.wants_recommendation)
        ),
        wants_qa=bool(data.get("wants_qa", fallback.wants_qa)),
        question=question,
    )


def _extract_json(content: str) -> dict[str, Any] | None:
    """从 LLM 输出中提取第一个 JSON 对象(容忍 ```json 围栏)。"""
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if match is None:
        return None
    try:
        data = json.loads(match.group())
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None
