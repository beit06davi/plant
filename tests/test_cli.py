import json

import pytest

from garden import __version__
from garden.cli import main


def run(capsys, *args):
    code = main(list(args))
    out = capsys.readouterr()
    return code, out.out, out.err


def edit(tree, rel, old, new):
    p = tree / rel
    p.write_text(p.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")


def test_version(capsys):
    with pytest.raises(SystemExit):
        main(["--version"])
    assert __version__ in capsys.readouterr().out


def test_init_then_check(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("GARDEN_PLUGIN", raising=False)
    code, out, _ = run(capsys, "init", str(tmp_path / "new"), "--plugin")
    assert code == 0 and "생성: SEED.md" in out and "/garden:plant" in out
    assert "Claude Code를 다시 연다" in out
    code, out, _ = run(capsys, "-C", str(tmp_path / "new"), "check")
    assert code == 2 and "(seed-placeholder)" in out
    code, out, _ = run(capsys, "init", str(tmp_path / "new"), "--plugin")
    assert "유지: CLAUDE.md" in out and "다시 연다" not in out


def test_init_plugin_env(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("GARDEN_PLUGIN", "1")
    run(capsys, "init", str(tmp_path / "p"))
    assert not (tmp_path / "p/.claude").exists()
    monkeypatch.delenv("GARDEN_PLUGIN")
    run(capsys, "init", str(tmp_path / "q"))
    assert (tmp_path / "q/.claude/settings.json").is_file()


def test_add_check_map(tree, capsys):
    code, out, _ = run(capsys, "-C", str(tree), "add", "docs", "--purpose", "설계 메모", "--serves", "G2,G3",
                       "--why", "코드와 분리", "--priority", "4", "--needs", "backend/booking")
    assert code == 0 and "생성: docs/NODE.md" in out
    code, out, _ = run(capsys, "-C", str(tree), "check")
    assert code == 0
    code, out, _ = run(capsys, "-C", str(tree), "map")
    assert "├─ docs/" in out and "G2  #4  설계 메모" in out
    code, out, _ = run(capsys, "-C", str(tree), "map", "--order")
    assert "3. " in out and "docs(G2)" in out
    code, out, _ = run(capsys, "-C", str(tree), "map", "--mermaid")
    assert out.startswith("flowchart TD")
    code, out, _ = run(capsys, "-C", str(tree), "map", "--why")
    assert "↳ 이유: 코드와 분리" in out


def test_add_error(tree, capsys):
    code, _, err = run(capsys, "-C", str(tree), "add", "backend", "--purpose", "x")
    assert code == 2 and "이미 카드" in err


def test_check_levels_and_json(tree, capsys):
    edit(tree, "backend/db/NODE.md", "why: 저장 방식이 바뀌어도 예약 규칙이 흔들리지 않게 분리\n", "")
    code, out, _ = run(capsys, "-C", str(tree), "check")
    assert code == 1 and "[경고] backend/db: why" in out
    edit(tree, "frontend/NODE.md", "- G2", "- G8")
    code, out, _ = run(capsys, "-C", str(tree), "check", "--json")
    data = json.loads(out)
    assert code == 2 == data["exit_code"]
    assert data["errors"][0]["code"] == "serves-invalid"


def test_trace_and_context(tree, capsys):
    code, out, _ = run(capsys, "-C", str(tree), "trace", "frontend/seatmap/index.html")
    assert code == 0 and out.startswith("frontend/seatmap — ")
    code, out, _ = run(capsys, "-C", str(tree), "context", "backend/booking", "--detail", "none")
    assert "needs: backend/db\n" in out
    code, out, _ = run(capsys, "-C", str(tree), "context", "backend/booking", "--json", "--budget", "200")
    data = json.loads(out)
    assert data["trimmed"] is True and data["chars"] <= 200
    code, _, err = run(capsys, "-C", str(tree), "trace", "docs")
    assert code == 2 and "카드를 찾지 못했습니다" in err


def test_lock_ack_log_resume(tree, capsys):
    code, out, _ = run(capsys, "-C", str(tree), "lock")
    assert code == 0 and "연결 3개" in out
    edit(tree, "backend/booking/NODE.md", "(id, zone, status)", "(id, zone, status, until)")
    code, out, _ = run(capsys, "-C", str(tree), "check")
    assert code == 1 and "[확인 필요] frontend/seatmap" in out
    code, out, _ = run(capsys, "-C", str(tree), "context", "frontend/seatmap")
    assert "check: frontend/seatmap ← backend/booking" in out
    code, _, err = run(capsys, "-C", str(tree), "lock")
    assert code == 1 and "확인 대기 2건" in err
    code, out, _ = run(capsys, "-C", str(tree), "ack", "frontend/seatmap", "--from", "backend/booking", "--note", "표시 안 함")
    assert code == 0 and "확인 처리: frontend/seatmap ← backend/booking" in out
    code, out, _ = run(capsys, "-C", str(tree), "ack", "reports/weekly", "--all")
    assert "reports/weekly ← backend/booking" in out
    code, out, _ = run(capsys, "-C", str(tree), "ack", "reports/weekly", "--all")
    assert "처리할 변경 없음" in out
    code, _, err = run(capsys, "-C", str(tree), "ack", "reports/weekly", "--from", "backend/db")
    assert code == 2 and "needs에 backend/db가 없음" in err
    code, out, _ = run(capsys, "-C", str(tree), "log", "backend/booking", "종료 시각 추가", "--why", "곧 빌 자리")
    assert code == 0 and "변경: 종료 시각 추가 | 이유: 곧 빌 자리" in out
    code, out, _ = run(capsys, "-C", str(tree), "resume", "backend/booking")
    assert "종료 시각 추가" in out and "## frontend" not in out
    code, out, _ = run(capsys, "-C", str(tree), "resume")
    assert "## frontend/seatmap" in out and "backend/booking 변경 확인" in out


def test_lock_missing(tree, capsys):
    run(capsys, "-C", str(tree), "lock")
    edit(tree, "reports/weekly/NODE.md", "- backend/booking", "- backend/booking\n- backend/db")
    code, out, _ = run(capsys, "-C", str(tree), "lock", "--missing")
    assert code == 0 and "새 연결 1개" in out and "reports/weekly ← backend/db" in out


def test_no_project(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    code, _, err = run(capsys, "map")
    assert code == 2 and "찾지 못했습니다" in err


def test_standalone_init_prints_diff_only_when_merging(tmp_path, capsys):
    root = tmp_path / "s"
    code, out, _ = run(capsys, "init", str(root), "--standalone")
    assert code == 0 and "생성: .claude/settings.json" in out and "@@" not in out
    (root / ".claude/settings.json").write_text('{"permissions": {"allow": []}}', encoding="utf-8")
    code, out, _ = run(capsys, "init", str(root), "--standalone")
    assert "갱신: .claude/settings.json" in out and "@@" in out


def test_init_warns_about_old_version(tmp_path, capsys):
    root = tmp_path / "old"
    (root / ".claude/agents").mkdir(parents=True)
    (root / ".claude/agents/root-worker.md").write_text("x", encoding="utf-8")
    (root / "CLAUDE.md").write_text("# demo\n- 요청은 `garden route <경로>`로 나눈다\n", encoding="utf-8")
    (root / ".claude/skills/route").mkdir(parents=True)
    (root / ".claude/skills/route/SKILL.md").write_text('Bash("py" -m garden *)\n`"py" -m garden route a`\n', encoding="utf-8")
    (root / ".claude/skills/mine").mkdir(parents=True)
    (root / ".claude/skills/mine/SKILL.md").write_text("my own skill\n", encoding="utf-8")
    code, out, _ = run(capsys, "init", str(root), "--plugin", "--dry-run")
    assert code == 0 and "다시 연다" not in out
    assert "주의: CLAUDE.md에 이전 버전(0.3) garden 안내" in out
    assert "주의: 이전 버전(0.3)이 설치한 에이전트" in out and "root-worker.md" in out
    assert "주의: 이전 버전(0.3) 스킬" in out and ".claude/skills/route" in out and "skills/mine" not in out
    code, out, _ = run(capsys, "init", str(root), "--plugin")
    assert "갱신: CLAUDE.md" in out and "주의: CLAUDE.md에 이전 버전" in out
    code, out, _ = run(capsys, "init", str(root), "--plugin")
    assert "유지: CLAUDE.md" in out and "주의: CLAUDE.md에 이전 버전" in out


def test_commands_survive_unreadable_lock(tree, capsys):
    run(capsys, "-C", str(tree), "lock")
    (tree / ".garden/concept.lock").write_text("<<<<<<< HEAD\n", encoding="utf-8")
    for args in (["map"], ["map", "--mermaid"], ["context", "backend/booking"], ["resume"], ["trace", "backend"]):
        code, _, err = run(capsys, "-C", str(tree), *args)
        assert code == 0, (args, err)
    code, out, _ = run(capsys, "-C", str(tree), "check")
    assert code == 2 and "(lock-parse)" in out
    code, _, err = run(capsys, "-C", str(tree), "lock")
    assert code == 1 and "--force" in err
    code, _, err = run(capsys, "-C", str(tree), "lock", "--missing")
    assert code == 2 and "--force" in err
    code, _, err = run(capsys, "-C", str(tree), "ack", "reports/weekly", "--all")
    assert code == 2 and "--force" in err
    code, out, _ = run(capsys, "-C", str(tree), "add", "ops", "--purpose", "운영", "--why", "운영 작업 분리",
                       "--serves", "G3", "--needs", "backend/db", "--create")
    assert code == 0 and (tree / "ops/NODE.md").is_file()
    code, _, _ = run(capsys, "-C", str(tree), "lock", "--force")
    assert code == 0
    code, out, _ = run(capsys, "-C", str(tree), "check")
    assert code == 0, out


def test_add_refuses_a_missing_folder(tree, capsys):
    code, _, err = run(capsys, "-C", str(tree), "add", "bakend", "--purpose", "오타", "--serves", "G1")
    assert code == 2 and "폴더가 없습니다" in err and "--create" in err
    assert not (tree / "bakend").exists()
