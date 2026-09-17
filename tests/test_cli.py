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
    code, out, _ = run(capsys, "-C", str(tmp_path / "new"), "check")
    assert code == 0 and "이상 없음" in out


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
