import io
import json

from conftest import card

from garden import hook, lock
from garden.tree import Garden


def payload(tree, tool="Read", session="s1", agent=None, **tool_input):
    data = {"session_id": session, "cwd": str(tree), "tool_name": tool, "tool_input": tool_input}
    if agent:
        data.update(agent_id=agent, agent_type="general-purpose")
    return data


def text_of(result):
    assert result is not None
    return result["hookSpecificOutput"]["additionalContext"]


def edit(tree, rel, old, new):
    p = tree / rel
    p.write_text(p.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")


def test_pre_injects_once_per_agent(tree):
    first = hook.pre(payload(tree, file_path=str(tree / "backend/booking/service.py")))
    assert first["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert text_of(first).startswith("[garden] backend/booking — 좌석 예약의 중복을 막는다")
    assert hook.pre(payload(tree, file_path=str(tree / "backend/booking/service.py"))) is None
    other = hook.pre(payload(tree, agent="sub1", file_path=str(tree / "backend/booking/service.py")))
    assert text_of(other).startswith("[garden] backend/booking")
    assert hook.pre(payload(tree, session="s2", file_path=str(tree / "backend/booking/service.py"))) is not None


def test_pre_reinjects_after_related_change(tree):
    target = str(tree / "frontend/seatmap/index.html")
    assert hook.pre(payload(tree, file_path=target)) is not None
    assert hook.pre(payload(tree, file_path=target)) is None
    edit(tree, "backend/booking/NODE.md", "(id, zone, status)", "(id, zone, status, until)")
    assert "until" in text_of(hook.pre(payload(tree, file_path=target)))


def test_pre_paths(tree):
    grep = hook.pre(payload(tree, tool="Grep", pattern="x", path=str(tree / "frontend")))
    assert text_of(grep).startswith("[garden] frontend — 이용자 화면")
    nb = hook.pre(payload(tree, tool="NotebookEdit", notebook_path="reports/weekly/a.ipynb"))
    assert text_of(nb).startswith("[garden] reports/weekly")
    assert hook.pre(payload(tree, tool="Glob", pattern="**/*.py")) is None
    assert hook.pre(payload(tree, file_path=str(tree / "docs/notes.md"))) is None
    assert hook.pre(payload(tree, file_path=str(tree / "SEED.md"))) is None
    assert hook.pre(payload(tree, file_path=str(tree.parent / "elsewhere.py"))) is None


def test_pre_outside_project(tmp_path):
    assert hook.pre({"cwd": str(tmp_path), "tool_input": {"file_path": str(tmp_path / "a.py")}}) is None


def test_pre_shows_pending_check(tree):
    lock.lock_all(Garden.load(tree), today="2026-09-20")
    edit(tree, "backend/booking/NODE.md", "(id, zone, status)", "(id, zone, status, until)")
    text = text_of(hook.pre(payload(tree, file_path=str(tree / "reports/weekly/r.py"))))
    assert "check: reports/weekly ← backend/booking" in text


def test_post_card_change_alerts_dependents(tree):
    lock.lock_all(Garden.load(tree), today="2026-09-20")
    edit(tree, "backend/booking/NODE.md", "(id, zone, status)", "(id, zone, status, until)")
    result = hook.post(payload(tree, tool="Edit", file_path=str(tree / "backend/booking/NODE.md")))
    assert result["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    text = text_of(result)
    assert text.startswith("[garden] 확인 필요 2건")
    assert "- frontend/seatmap ← backend/booking" in text and "- reports/weekly ← backend/booking" in text


def test_post_body_change_is_quiet(tree):
    lock.lock_all(Garden.load(tree), today="2026-09-20")
    edit(tree, "backend/booking/NODE.md", "확정 예약은", "확정된 예약은")
    assert hook.post(payload(tree, tool="Edit", file_path=str(tree / "backend/booking/NODE.md"))) is None
    assert hook.post(payload(tree, tool="Edit", file_path=str(tree / "backend/booking/service.py"))) is None


def test_post_reports_card_problems(tree):
    (tree / "frontend/seatmap/NODE.md").write_text(card(purpose="x", serves=["G7"]), encoding="utf-8")
    text = text_of(hook.post(payload(tree, tool="Write", file_path=str(tree / "frontend/seatmap/NODE.md"))))
    assert "카드 error frontend/seatmap: SEED에 없는 목표: G7" in text
    assert "카드 warning frontend/seatmap: why" in text
    (tree / "frontend/seatmap/NODE.md").write_text("---\npurpose: [\n---\n", encoding="utf-8")
    text = text_of(hook.post(payload(tree, tool="Write", file_path=str(tree / "frontend/seatmap/NODE.md"))))
    assert "카드 error frontend/seatmap: frontmatter YAML 오류" in text


def test_post_seed_change(tree):
    edit(tree, "SEED.md", "- G3: 운영자용 주간 보고서\n", "")
    text = text_of(hook.post(payload(tree, tool="Edit", file_path=str(tree / "SEED.md"))))
    assert text.startswith("[garden] SEED.md가 바뀜")
    assert "reports/weekly: SEED에 없는 목표: G3" in text


def test_compact_clears_session_cache(tree):
    target = str(tree / "backend/db/store.py")
    assert hook.pre(payload(tree, file_path=target)) is not None
    assert hook.pre(payload(tree, file_path=target)) is None
    assert hook.compact({"cwd": str(tree), "session_id": "s1"}) is None
    assert hook.pre(payload(tree, file_path=target)) is not None


def test_run_is_fail_open(tree, monkeypatch, capsys):
    out = io.StringIO()
    assert hook.run("pre", stdin=io.BytesIO(b"not json"), stdout=out) == 0
    assert out.getvalue() == ""

    def boom(data):
        raise RuntimeError("broken")

    monkeypatch.setitem(hook.HANDLERS, "pre", boom)
    assert hook.run("pre", stdin=io.BytesIO(b"{}"), stdout=out) == 0
    assert "broken" in capsys.readouterr().err


def test_run_writes_ascii_json(tree):
    out = io.StringIO()
    data = json.dumps(payload(tree, file_path=str(tree / "backend/db/store.py")), ensure_ascii=False)
    assert hook.run("pre", stdin=io.BytesIO(("﻿" + data).encode("utf-8")), stdout=out) == 0
    raw = out.getvalue()
    assert raw.isascii()
    assert json.loads(raw)["hookSpecificOutput"]["additionalContext"].startswith("[garden] backend/db")
