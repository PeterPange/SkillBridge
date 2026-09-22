"""CLI 入口测试(``python -m profile``,阶段 2B 验收命令)。"""

import json

from profile.__main__ import main


def _write_processed(tmp_path, employee, position):
    """把员工与岗位记录写成 data/processed 形状的目录。"""
    data_dir = tmp_path / "processed"
    data_dir.mkdir()
    (data_dir / "employees.json").write_text(
        json.dumps({"employees": [employee]}, ensure_ascii=False), encoding="utf-8"
    )
    (data_dir / "positions.json").write_text(
        json.dumps({"positions": [position]}, ensure_ascii=False), encoding="utf-8"
    )
    return data_dir


def test_cli_renders_report_from_processed_files(
    tmp_path, capsys, outline_employee, outline_position
):
    data_dir = _write_processed(tmp_path, outline_employee, outline_position)
    exit_code = main(["EMP_001", "--data-dir", str(data_dir)])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "李明" in out
    assert "AI Engineer" in out
    assert "Generative AI" in out
    assert "+3" in out
    assert "岗位准备度" in out


def test_cli_json_output(tmp_path, capsys, outline_employee, outline_position):
    data_dir = _write_processed(tmp_path, outline_employee, outline_position)
    exit_code = main(["EMP_001", "--data-dir", str(data_dir), "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["employee"]["employee_id"] == "EMP_001"
    assert payload["target_position"]["name"] == "AI Engineer"
    assert payload["summary"]["missing_count"] == 6
    assert payload["summary"]["total_gap"] == 10
    assert [(gap["skill_id"], gap["gap"]) for gap in payload["gaps"]][:2] == [
        ("SKILL_006", 3),
        ("SKILL_009", 3),
    ]


def test_cli_explain_evidence(tmp_path, capsys, outline_employee, outline_position):
    data_dir = _write_processed(tmp_path, outline_employee, outline_position)
    exit_code = main(
        ["EMP_001", "--data-dir", str(data_dir), "--explain", "SKILL_001"]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "为什么认为你的 Python 是 Level 2?" in out
    assert "技能考试" in out
    assert "员工自评" in out


def test_cli_list(tmp_path, capsys, outline_employee, outline_position):
    data_dir = _write_processed(tmp_path, outline_employee, outline_position)
    exit_code = main(["--list", "--data-dir", str(data_dir)])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "EMP_001" in out
    assert "李明" in out


def test_cli_unknown_employee_fails(
    tmp_path, capsys, outline_employee, outline_position
):
    data_dir = _write_processed(tmp_path, outline_employee, outline_position)
    exit_code = main(["EMP_999", "--data-dir", str(data_dir)])

    assert exit_code == 1
    assert "未知员工" in capsys.readouterr().err


def test_cli_falls_back_to_offline_pipeline(tmp_path, capsys):
    """data/processed 缺失时回退离线管线(fixture 岗位 + 生成器员工)。"""
    exit_code = main(
        [
            "EMP_001",
            "--data-dir", str(tmp_path / "no-such-dir"),
            "--raw-dir", str(tmp_path / "raw"),
        ]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "李明" in out
    assert "AI Engineer" in out
    # 后端出身的李明:GenAI / AI Agent 是最大缺口
    assert "Generative AI" in out
    assert "AI Agent" in out


def test_cli_multiple_employees(tmp_path, capsys, outline_employee, outline_position):
    data_dir = _write_processed(tmp_path, outline_employee, outline_position)
    exit_code = main(
        ["EMP_001", "EMP_001", "--data-dir", str(data_dir)]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert out.count("Skill Gap 差距报告") == 2
