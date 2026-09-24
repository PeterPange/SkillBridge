"""回答生成(规则模式):直接串联工具输出,引用真实数据。

LLM 不可用时的降级方案(大纲第十节「LLM 不可用时降级为规则模式」):
不经过 LLM 改写,把画像 → 差距 → 推荐 → 课表(→ 知识库)的工具
结果按固定模板渲染成最终回答。所有数字(准备度 / 缺口数 / Top-5 /
周计划)均来自工具返回的真实数据,不硬编码、不编造。

LLM 模式同样复用本模块的 :func:`build_llm_context` 构造提示词上下文,
保证两种模式引用同一份工具结果。
"""

from __future__ import annotations

import json
from typing import Any

from agent.intent import Intent

_SEPARATOR = "=" * 62


def render_rule_answer(intent: Intent, tool_results: dict[str, Any]) -> str:
    """规则模式最终回答:按模板串联工具输出。

    :param intent: 需求理解结果(员工 / 岗位 / 时间约束)。
    :param tool_results: 工具名 → payload(``ok`` / ``data`` / ``error``)。
    """
    lines: list[str] = []
    lines.append(_SEPARATOR)
    lines.append(
        f"HR 培训规划:{intent.employee_name} → {intent.target_position_name}"
    )
    lines.append(_SEPARATOR)

    # --- 需求理解 ---
    lines.append("【需求理解】")
    lines.append(
        f"员工 {intent.employee_name}({intent.employee_id}),"
        f"当前 {intent.current_position_name},目标 {intent.target_position_name};"
        f"每周可投入 {intent.hours_per_week:g} 小时,培训截止 {intent.deadline_weeks} 周。"
    )
    lines.append("")

    # --- 工具失败提示(后端不可用时显式说明,不静默) ---
    failures = [
        f"{name}:{payload['error']}"
        for name, payload in tool_results.items()
        if not payload.get("ok")
    ]
    if failures:
        lines.append("【提示】以下工具暂不可用,回答基于其余真实数据:")
        for failure in failures:
            lines.append(f"  - {failure}")
        lines.append("")

    # --- 员工画像(大纲第五节) ---
    profile = tool_results.get("get_employee_profile")
    if profile and profile.get("ok"):
        lines.append("【员工画像】")
        employee = profile["data"]["employee"]
        lines.append(
            f"{employee['name']}({employee['employee_id']}),"
            f"{employee['department']},工作 {employee['years_of_experience']} 年,"
            f"{employee['current_position_name']} → {employee['target_position_name']}。"
        )
        skills = profile["data"]["skills"]
        if skills:
            shown = "、".join(
                f"{item['skill_name']} {item['level']}" for item in skills
            )
            lines.append(f"技能等级:{shown}")
        lines.append("")

    # --- 能力差距(大纲第六节) ---
    gap = tool_results.get("get_skill_gap")
    if gap and gap.get("ok"):
        lines.append("【能力差距】")
        summary = gap["data"]["summary"]
        lines.append(
            f"目标岗位准备度 {summary['readiness_percent']}%,"
            f"缺失 {summary['missing_count']} 项技能"
            f"(总差距 {summary['total_gap']} 级,加权差距 {summary['weighted_total_gap']:g})。"
        )
        for item in gap["data"]["gaps"]:
            lines.append(
                f"  - {item['skill_name']}:{item['current_level']} → "
                f"{item['required_level']}(差 {item['gap']} 级,重要度 {item['importance']:g})"
            )
        if gap["data"]["met"]:
            met = "、".join(f"{m['skill_name']}({m['current_level']})" for m in gap["data"]["met"])
            lines.append(f"已达标:{met}")
        lines.append("")

    # --- 课程推荐(大纲第七节) ---
    recommendation = tool_results.get("recommend_courses")
    if recommendation and recommendation.get("ok"):
        lines.append("【课程推荐 Top-%d】" % recommendation["data"]["top_k"])
        lines.append(
            f"候选课程 {recommendation['data']['candidate_count']} 门"
            "(按缺口技能 TEACHES 关系召回),五因子加权排序后推荐:"
        )
        for rec in recommendation["data"]["recommendations"]:
            course = rec["course"]
            covered = "、".join(
                f"{g['skill_name']}(+{g['gap']})" for g in rec["covered_gaps"]
            ) or "-"
            lines.append(
                f"  {rec['rank']}. {course['name']}({course['course_id']})"
                f"  评分 {rec['score']:.3f}"
            )
            lines.append(
                f"     覆盖缺口:{covered} · {course['difficulty']}"
                f" · 约 {course['duration_minutes']} 分钟"
            )
            if rec["reasons"]:
                lines.append(f"     推荐理由:{rec['reasons'][0]}")
        lines.append("")

    # --- 学习路径(大纲第八节) ---
    path = tool_results.get("generate_learning_path")
    if path and path.get("ok"):
        constraints = path["data"]["constraints"]
        summary = path["data"]["summary"]
        fit = "满足" if summary["fits_deadline"] else "超出"
        lines.append("【学习课表】")
        lines.append(
            f"按每周 {intent.hours_per_week:g} 小时"
            f"(预算 {constraints['weekly_budget_minutes']:g} 分钟)、"
            f"{intent.deadline_weeks} 周截止排课:"
            f"待学 {summary['course_count']} 门,共 {summary['total_hours']:.1f} 小时,"
            f"排期 {summary['planned_weeks']} 周({fit}截止期限)。"
        )
        for week in path["data"]["weeks"]:
            courses = "、".join(
                f"{item['name']}({item['minutes']:g} 分钟)"
                for item in week["courses"]
            )
            lines.append(
                f"  第 {week['week']} 周({week['minutes']:g} / "
                f"{week['budget_minutes']:g} 分钟):{courses}"
            )
        if path["data"]["pruned"]:
            pruned = "、".join(p["name"] for p in path["data"]["pruned"])
            lines.append(f"已掌握剪枝:{pruned}")
        if path["data"]["uncovered_skills"]:
            uncovered = "、".join(g["skill_name"] for g in path["data"]["uncovered_skills"])
            lines.append(f"注意:以下缺口暂无课程覆盖,建议补充资源:{uncovered}")
        lines.append("")

    # --- 知识库引用(大纲第九节) ---
    rag = tool_results.get("rag_query")
    if rag and rag.get("ok") and rag["data"]["hits"]:
        lines.append("【知识库参考】")
        for hit in rag["data"]["hits"]:
            lines.append(f"  《{hit['title']}》{hit['heading']}(相关度 {hit['score']}):")
            snippet = hit["content"].strip().replace("\n", " ")
            if len(snippet) > 120:
                snippet = snippet[:120] + "……"
            lines.append(f"    {snippet}")
        lines.append("")

    # --- 结尾 ---
    lines.append("以上结果由员工画像、能力差距、课程推荐与学习路径模块计算生成,")
    lines.append("数据可经 `python -m profile / recommendation / learning_path` 复现。")
    return "\n".join(lines).rstrip() + "\n"


def build_llm_context(intent: Intent, tool_results: dict[str, Any]) -> list[dict[str, str]]:
    """LLM 模式生成回答的消息上下文(system + 工具结果 + 用户问题)。

    工具结果以 JSON 形式注入(截断超长字段),system 提示词约束 LLM
    只引用工具返回的真实数据,不得编造数字。
    """
    payload = {
        name: {
            "ok": result.get("ok"),
            "summary": result.get("summary", ""),
            **({"data": _bound(result["data"])} if result.get("ok") else {}),
            **({} if result.get("ok") else {"error": result.get("error")}),
        }
        for name, result in tool_results.items()
    }
    system = (
        "你是企业 HR 培训 Agent。基于下方工具返回的真实数据回答用户问题,"
        "要求:\n"
        "- 所有数字(准备度、缺口数、评分、周数等)必须来自工具结果,"
        "  禁止编造或修改;\n"
        "- 回答用中文,结构清晰,先给结论再给依据;\n"
        "- 工具失败的项要显式说明数据缺失,不要猜测;\n"
        "- 适当引用课程名称与知识库来源。"
    )
    user = (
        f"用户问题:{intent.question}\n\n"
        f"需求理解:{json.dumps(intent.to_dict(), ensure_ascii=False)}\n\n"
        f"工具返回结果(JSON):\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _bound(data: Any, max_chars: int = 6000) -> Any:
    """截断超长字符串字段,防止工具结果撑爆提示词。"""
    text = json.dumps(data, ensure_ascii=False)
    if len(text) <= max_chars:
        return data
    return {"_truncated": text[:max_chars] + "……(已截断)"}
