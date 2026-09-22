"""端到端采集流程测试(阶段 1A 验收)。

强制离线模式跑通完整 ``collect_all``,验证:
1. 一次跑通产出三类 JSON 文件(岗位与技能 / 课程 / 员工);
2. 产出全部通过统一 JSON Schema 与引用完整性校验;
3. 断网(无缓存)时使用内置 fixture,不阻塞;
4. 已有缓存时离线模式优先复用缓存;
5. 员工种子可复现。
"""

import json

import pytest

from data.collect import collect_all


@pytest.fixture()
def run_offline(tmp_path):
    """在隔离目录中执行离线采集,返回 (stats, out_dir, raw_dir)。"""

    def _run(**kwargs):
        raw_dir = tmp_path / "raw"
        out_dir = tmp_path / "processed"
        stats = collect_all(
            raw_dir=raw_dir, out_dir=out_dir, offline=True, **kwargs
        )
        return stats, out_dir, raw_dir

    return _run


def test_collect_offline_produces_all_files(run_offline):
    stats, out_dir, raw_dir = run_offline()
    expected = ["skills.json", "positions.json", "courses.json", "employees.json"]
    for name in expected:
        assert (out_dir / name).is_file(), f"缺少 {name}"
    # Schema 文件一并落盘
    for name in expected:
        assert (out_dir / "schemas" / f"{name.replace('.json', '')}.schema.json").is_file()
    # 离线无缓存 → 全部来自内置 fixture
    assert set(stats["sources"].values()) == {"fixture"}


def test_collect_offline_output_counts(run_offline):
    stats, out_dir, _ = run_offline()
    assert stats["skills"] == 18
    assert stats["positions"] == 5
    assert stats["courses"] == 17
    assert stats["employees"] == 10


def test_collected_output_passes_schema_validation(run_offline, tmp_path):
    """对落盘文件重新执行完整校验(模拟下游模块读取)。"""
    import data.schemas as schemas

    _, out_dir, _ = run_offline()
    skills = json.loads((out_dir / "skills.json").read_text(encoding="utf-8"))
    positions = json.loads((out_dir / "positions.json").read_text(encoding="utf-8"))
    courses = json.loads((out_dir / "courses.json").read_text(encoding="utf-8"))
    employees = json.loads((out_dir / "employees.json").read_text(encoding="utf-8"))

    assert schemas.validate_all(skills, positions, courses, employees) == []

    # 关键业务断言:AI Engineer 岗位存在且含 AI Agent 要求
    ai = next(p for p in positions["positions"] if p["name"] == "AI Engineer")
    assert any(s["skill_id"] == "SKILL_009" for s in ai["skills"])
    # 课程覆盖 AI Agent 技能(大纲第七节推荐链路的输入)
    assert any("SKILL_009" in c["skills"] for c in courses["courses"])
    # 员工全部以 AI Engineer 为目标
    assert all(e["target_position_id"] == "POS_005" for e in employees["employees"])


def test_collect_is_reproducible_with_same_seed(tmp_path):
    def _run(out_dir):
        collect_all(raw_dir=tmp_path / "raw", out_dir=out_dir, offline=True, seed=42)
        return json.loads((out_dir / "employees.json").read_text(encoding="utf-8"))

    first = _run(tmp_path / "out1")
    second = _run(tmp_path / "out2")
    assert first["employees"] == second["employees"]


def test_collect_respects_seed_argument(run_offline):
    _, out_dir, _ = run_offline(seed=99)
    employees = json.loads((out_dir / "employees.json").read_text(encoding="utf-8"))
    assert employees["seed"] == 99
    # 与默认种子 42 的输出不同
    _, out_dir_42, _ = run_offline(seed=42)
    employees_42 = json.loads((out_dir_42 / "employees.json").read_text(encoding="utf-8"))
    assert employees["employees"] != employees_42["employees"]


def test_offline_mode_prefers_existing_cache(tmp_path):
    """已有 API 缓存时,离线模式复用缓存而不是 fixture。"""
    raw_dir = tmp_path / "raw"
    out_dir = tmp_path / "processed"
    # 第一次:在线拉取(此处用 fixture 伪造一份「API 缓存」)
    stats = collect_all(raw_dir=raw_dir, out_dir=out_dir, offline=True)
    assert set(stats["sources"].values()) == {"fixture"}

    # 手动把 manifest 标记为 api,模拟「昨天在线拉取过」
    manifest_path = raw_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in manifest.values():
        entry["source"] = "api"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    stats2 = collect_all(raw_dir=raw_dir, out_dir=out_dir, offline=True)
    assert set(stats2["sources"].values()) == {"cache"}


def test_network_failure_falls_back_without_blocking(tmp_path, monkeypatch):
    """模拟完全断网(在线模式 + 请求全部失败):回退 fixture,流程不中断。"""
    from data.httpclient import NetworkError

    def _no_network(*args, **kwargs):
        raise NetworkError("模拟断网")

    monkeypatch.setattr("data.sources.esco.fetch_esco_live", _no_network)
    monkeypatch.setattr("data.sources.microsoft_learn.fetch_catalog_live", _no_network)
    monkeypatch.setattr("data.sources.microsoft_learn.fetch_objectives_live", _no_network)

    stats = collect_all(
        raw_dir=tmp_path / "raw", out_dir=tmp_path / "out", offline=False
    )
    assert set(stats["sources"].values()) == {"fixture"}
    assert (tmp_path / "out" / "employees.json").is_file()


def test_invalid_data_raises_validation_error(tmp_path, monkeypatch):
    """采集产出不符合 Schema 时应显式失败(而不是静默写盘)。"""
    from data import employees as employees_mod

    original = employees_mod.generate_employees

    def _broken(seed=42, count=None):
        people = original(seed=seed, count=count)
        # 注入越界等级
        people[0]["skills"][0]["level"] = 9
        return people

    monkeypatch.setattr(employees_mod, "generate_employees", _broken)
    with pytest.raises(ValueError, match="校验失败"):
        collect_all(raw_dir=tmp_path / "raw", out_dir=tmp_path / "out", offline=True)
