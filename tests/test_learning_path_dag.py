"""学习路径 DAG 纯算法测试(大纲第八节,阶段 3B 验收)。

覆盖验收要求的三项之二:**DAG 剪枝**(掌握判定 + 补齐前置)与
**环检测**(拓扑排序兜底)。全部用合成课程数据,不依赖 Neo4j。

掌握判定规则(见 :mod:`learning_path.dag`):

    beginner 平均等级 ≥ 2 / intermediate ≥ 3 / advanced ≥ 4 → 已掌握
"""

from __future__ import annotations

import pytest

from learning_path import (
    CycleError,
    average_skill_level,
    is_mastered,
    mastery_threshold,
    select_path_courses,
    topological_order,
)
from learning_path.dag import MASTERY_THRESHOLDS
from recommendation.models import CandidateCourse


def make_course(
    course_id: str,
    *,
    difficulty: str = "beginner",
    minutes: int = 60,
    skills: tuple[str, ...] = (),
    prerequisites: tuple[str, ...] = (),
) -> CandidateCourse:
    """构造合成课程(默认 beginner / 60 分钟 / 无前置)。"""
    return CandidateCourse(
        course_id=course_id,
        name=f"课程 {course_id}",
        difficulty=difficulty,
        duration_minutes=minutes,
        url="",
        taught_skills=frozenset(skills),
        prerequisites=frozenset(prerequisites),
    )


def level_of(levels: dict[str, int]):
    """技能等级查询(未登记技能按 0 计,与 EmployeeProfile.level_of 一致)。"""
    return lambda skill_id: levels.get(skill_id, 0)


# ---------------------------------------------------------------------------
# 掌握判定(剪枝依据)
# ---------------------------------------------------------------------------

def test_mastery_threshold_by_difficulty():
    """掌握门槛随难度递增:beginner 2 / intermediate 3 / advanced 4。"""
    assert MASTERY_THRESHOLDS == {"beginner": 2.0, "intermediate": 3.0, "advanced": 4.0}
    assert mastery_threshold("beginner") == 2.0
    assert mastery_threshold("intermediate") == 3.0
    assert mastery_threshold("advanced") == 4.0
    with pytest.raises(ValueError, match="课程难度"):
        mastery_threshold("expert")


def test_mastered_beginner_course():
    """Python 2 的员工已掌握 beginner 的「Python 入门」,Python 1 未掌握。"""
    course = make_course("C1", skills=("SKILL_001",), difficulty="beginner")
    assert is_mastered(course, level_of({"SKILL_001": 2}))
    assert not is_mastered(course, level_of({"SKILL_001": 1}))


def test_mastered_scales_with_difficulty():
    """同一技能等级,难度越高越不易视为已掌握(不误剪进阶课程)。"""
    intermediate = make_course(
        "C1", skills=("SKILL_001",), difficulty="intermediate"
    )
    assert not is_mastered(intermediate, level_of({"SKILL_001": 2}))
    assert is_mastered(intermediate, level_of({"SKILL_001": 3}))

    advanced = make_course("C2", skills=("SKILL_001",), difficulty="advanced")
    assert not is_mastered(advanced, level_of({"SKILL_001": 3}))
    assert is_mastered(advanced, level_of({"SKILL_001": 4}))


def test_mastered_uses_average_level():
    """多技能课程按平均等级判定:(2+2)/2 = 2 已掌握,(2+1)/2 = 1.5 未掌握。"""
    balanced = make_course("C1", skills=("S1", "S2"), difficulty="beginner")
    assert is_mastered(balanced, level_of({"S1": 2, "S2": 2}))

    mixed = make_course("C2", skills=("S1", "S2"), difficulty="beginner")
    assert not is_mastered(mixed, level_of({"S1": 2, "S2": 1}))


def test_mastered_requires_taught_skills():
    """无所授技能的课程无法验证掌握,保守保留在路径中。"""
    course = make_course("C1", skills=(), difficulty="beginner")
    assert not is_mastered(course, level_of({"SKILL_001": 4}))
    assert average_skill_level(course, level_of({})) == 0.0


# ---------------------------------------------------------------------------
# 剪枝 + 补齐前置(select_path_courses)
# ---------------------------------------------------------------------------

def _mini_catalog() -> tuple[dict[str, CandidateCourse], tuple[CandidateCourse, ...]]:
    """合成课程目录:AI 链 A→B→C(前置 D 已掌握),Python 链 E→F。

    - A「AI 基础」beginner 60min,授 ML/GenAI,无前置;
    - B「生成式 AI」beginner 90min,授 GenAI,前置 A;
    - C「AI Agent」intermediate 120min,授 AI Agent,前置 B、D;
    - D「Docker」beginner 30min,授 Docker,无前置(非候选,Docker 已达标);
    - E「Python 入门」beginner 30min,授 Python,无前置;
    - F「Python 数据分析」intermediate 60min,授 Python,前置 E。
    """
    a = make_course("A", minutes=60, skills=("SKILL_004", "SKILL_006"))
    b = make_course("B", minutes=90, skills=("SKILL_006",), prerequisites=("A",))
    c = make_course(
        "C", difficulty="intermediate", minutes=120, skills=("SKILL_009",),
        prerequisites=("B", "D"),
    )
    d = make_course("D", minutes=30, skills=("SKILL_011",))
    e = make_course("E", minutes=30, skills=("SKILL_001",))
    f = make_course(
        "F", difficulty="intermediate", minutes=60, skills=("SKILL_001",),
        prerequisites=("E",),
    )
    catalog = {course.course_id: course for course in (a, b, c, d, e, f)}
    return catalog, (a, b, c, e, f)  # 候选 = 教授缺口技能的课程(D 不是)


def test_select_prunes_mastered_and_keeps_rest():
    """验收:DAG 剪枝——已掌握课程(Python/Docker 的 beginner 课)被剪枝。

    Python 2 / Docker 2 的员工:E、D 达到 beginner 门槛 2 → 剪枝;
    F(intermediate,门槛 3)与 AI 链 A/B/C 保留。
    """
    catalog, candidates = _mini_catalog()
    levels = {
        "SKILL_001": 2,  # Python 2 → E 已掌握,F(intermediate)未掌握
        "SKILL_011": 2,  # Docker 2 → D 已掌握
        "SKILL_004": 1, "SKILL_006": 0, "SKILL_009": 0,
    }
    kept, pruned = select_path_courses(candidates, catalog, level_of(levels))

    assert set(kept) == {"A", "B", "C", "F"}
    assert set(pruned) == {"D", "E"}
    # 剪枝明细携带判定依据(平均等级与门槛),供报告解释「为什么跳过」
    assert pruned["E"].average_level == 2.0
    assert pruned["E"].threshold == 2.0
    assert pruned["E"].course.name == "课程 E"
    assert pruned["D"].average_level == 2.0


def test_select_expands_transitive_prerequisites():
    """补齐必须前置课程:候选 C 的传递前置链 B → A 全部入图。"""
    catalog, _ = _mini_catalog()
    levels = {"SKILL_011": 2}  # 前置 D 已掌握 → 剪枝
    kept, pruned = select_path_courses(
        [catalog["C"]], catalog, level_of(levels)
    )

    assert set(kept) == {"A", "B", "C"}  # B、A 均被补齐
    assert set(pruned) == {"D"}


def test_select_mastered_prerequisite_stops_expansion():
    """已掌握的前置被剪枝,且不再展开它的前置(更基础,必然也已掌握)。"""
    g = make_course("G", minutes=10, skills=("SKILL_012",), prerequisites=("H",))
    h = make_course("H", minutes=10, skills=("SKILL_013",))
    d = make_course(
        "D", minutes=30, skills=("SKILL_011",), prerequisites=("G",)
    )
    c = make_course(
        "C", minutes=120, skills=("SKILL_009",), prerequisites=("D",)
    )
    catalog = {"C": c, "D": d, "G": g, "H": h}

    kept, pruned = select_path_courses(
        [c], catalog, level_of({"SKILL_011": 2})  # D 已掌握
    )
    assert set(kept) == {"C"}
    assert set(pruned) == {"D"}
    assert "G" not in kept and "G" not in pruned  # 不再展开


def test_select_mastered_candidate_not_expanded():
    """已掌握的候选课程同样不展开其前置:E 已掌握,F 仍保留。"""
    catalog, _ = _mini_catalog()
    kept, pruned = select_path_courses(
        [catalog["F"]], catalog, level_of({"SKILL_001": 2})
    )
    assert set(kept) == {"F"}
    assert set(pruned) == {"E"}


def test_select_repeated_candidate_visited_once():
    """同一课程既是候选又是前置时只处理一次。"""
    catalog, candidates = _mini_catalog()
    levels = {"SKILL_001": 2, "SKILL_011": 2, "SKILL_004": 1,
              "SKILL_006": 0, "SKILL_009": 0}
    kept, pruned = select_path_courses(
        (*candidates, catalog["B"]), catalog, level_of(levels)  # B 重复出现
    )
    assert set(kept) == {"A", "B", "C", "F"}


def test_select_unknown_candidate_raises():
    """候选不在课程目录中(数据不一致)→ 显式报错。"""
    catalog, _ = _mini_catalog()
    stranger = make_course("X", skills=("SKILL_001",))
    with pytest.raises(ValueError, match="X 不在课程目录"):
        select_path_courses([stranger], catalog, level_of({}))


def test_select_unknown_prerequisite_raises():
    """前置不在课程目录中(前置关系不完整)→ 显式报错。"""
    orphan = make_course("Y", skills=("SKILL_001",), prerequisites=("Z",))
    with pytest.raises(ValueError, match="前置 Z 不在课程目录"):
        select_path_courses([orphan], {"Y": orphan}, level_of({}))


# ---------------------------------------------------------------------------
# 拓扑排序
# ---------------------------------------------------------------------------

def test_topological_order_respects_prerequisites():
    """菱形依赖 A→B,C;B,C→D:前置恒在前。"""
    a = make_course("A")
    b = make_course("B", prerequisites=("A",))
    c = make_course("C", prerequisites=("A",))
    d = make_course("D", prerequisites=("B", "C"))
    order = [course.course_id for course in topological_order(
        {"A": a, "B": b, "C": c, "D": d}
    )]
    assert order.index("A") < order.index("B") < order.index("D")
    assert order.index("A") < order.index("C") < order.index("D")


def test_topological_order_ignores_pruned_prerequisites():
    """不在节点集内的前置(已剪枝)不阻塞:课程视为立即可学。"""
    course = make_course("C", prerequisites=("D",))  # D 已被剪枝,不在节点集
    order = topological_order({"C": course})
    assert [c.course_id for c in order] == ["C"]


def test_topological_order_priority_prefers_core_gaps():
    """就绪集合中,覆盖加权缺口大的课程先学(核心缺口优先)。"""
    low = make_course("A1", skills=("SKILL_001",))
    high = make_course("A2", skills=("SKILL_006",))
    weights = {"A1": 5.0, "A2": 15.0}
    order = [c.course_id for c in topological_order(
        {"A1": low, "A2": high}, priority=lambda course: weights[course.course_id]
    )]
    assert order == ["A2", "A1"]


def test_topological_order_priority_within_constraints():
    """优先级不能破坏拓扑约束:高优先级课程仍需等其前置完成。"""
    root = make_course("R", skills=("SKILL_001",))
    leaf = make_course("L", skills=("SKILL_006",), prerequisites=("R",))
    weights = {"R": 0.0, "L": 100.0}
    order = [c.course_id for c in topological_order(
        {"R": root, "L": leaf}, priority=lambda course: weights[course.course_id]
    )]
    assert order == ["R", "L"]


def test_topological_order_tie_breaks_by_course_id():
    """同优先级按 course_id 升序,输出确定可复现。"""
    courses = {cid: make_course(cid) for cid in ("C3", "C1", "C2")}
    order = [c.course_id for c in topological_order(courses)]
    assert order == ["C1", "C2", "C3"]
    again = [c.course_id for c in topological_order(courses)]
    assert order == again


# ---------------------------------------------------------------------------
# 环检测(验收要求)
# ---------------------------------------------------------------------------

def test_cycle_detected_three_nodes():
    """三节点环 A→C→B→A:抛 CycleError,环序列首尾相同。"""
    a = make_course("A", prerequisites=("C",), skills=("SKILL_001",))
    b = make_course("B", prerequisites=("A",), skills=("SKILL_001",))
    c = make_course("C", prerequisites=("B",), skills=("SKILL_001",))
    with pytest.raises(CycleError) as excinfo:
        topological_order({"A": a, "B": b, "C": c})

    error = excinfo.value
    assert error.cycle[0] == error.cycle[-1]  # 首尾相同
    assert set(error.cycle) == {"A", "B", "C"}
    assert "存在环" in str(error)
    assert "A" in str(error) and "B" in str(error) and "C" in str(error)


def test_cycle_detected_two_nodes():
    """两节点环 A⇄B:抛 CycleError。"""
    a = make_course("A", prerequisites=("B",))
    b = make_course("B", prerequisites=("A",))
    with pytest.raises(CycleError):
        topological_order({"A": a, "B": b})


def test_cycle_detected_self_loop():
    """自环 A→A:抛 CycleError,环为 [A, A]。"""
    a = make_course("A", prerequisites=("A",))
    with pytest.raises(CycleError) as excinfo:
        topological_order({"A": a})
    assert excinfo.value.cycle == ["A", "A"]


def test_cycle_in_subgraph_with_valid_tail():
    """环之外的合法课程不掩盖环:整体排序仍抛 CycleError。"""
    ok_root = make_course("OK")
    ok_leaf = make_course("OK2", prerequisites=("OK",))
    a = make_course("A", prerequisites=("B",))
    b = make_course("B", prerequisites=("A",))
    with pytest.raises(CycleError):
        topological_order(
            {"OK": ok_root, "OK2": ok_leaf, "A": a, "B": b}
        )


def test_cycle_error_is_value_error():
    """CycleError 是 ValueError 的子类(CLI 统一按数据错误处理)。"""
    assert issubclass(CycleError, ValueError)
