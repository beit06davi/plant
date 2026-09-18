import json
import shutil

import pytest

from conftest import card, write_tree

from garden import lock
from garden.history import log, read_history, resume_text
from garden.tree import Garden
from garden.validate import check

DAY1, DAY2 = "2026-09-20", "2026-09-21"


def locked(tree):
    ok, _ = lock.lock_all(Garden.load(tree), today=DAY1)
    assert ok
    return Garden.load(tree)


def pend(tree):
    return {(p.a, p.b) for p in lock.pending(Garden.load(tree))}


def edit(tree, rel, old, new):
    p = tree / rel
    p.write_text(p.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")


def test_edges_follow_needs(tree):
    assert lock.edges(Garden.load(tree)) == [
        ("backend/booking", "backend/db"),
        ("frontend/seatmap", "backend/booking"),
        ("reports/weekly", "backend/booking"),
    ]


def test_lock_then_clean(tree):
    g = locked(tree)
    assert lock.status(g) == []
    assert check(g).exit_code == 0
    data = json.loads((tree / ".garden/concept.lock").read_text(encoding="utf-8"))
    assert data["edges"]["frontend/seatmap <- backend/booking"]["at"] == DAY1


def test_without_a_lock_check_is_quiet(tree):
    g = Garden.load(tree)
    assert lock.status(g) == []
    assert check(g).findings == []


@pytest.mark.parametrize("old,new", [
    ("좌석 상태 목록 (id, zone, status)", "좌석 상태 목록 (id, zone, status, until)"),
    ("좌석 예약의 중복을 막는다", "좌석 예약의 중복과 취소를 관리한다"),
    ("예약 판단을 한곳에 모아", "예약 판단을 서버에만 두어"),
])
def test_concept_change_flags_dependents(tree, old, new):
    locked(tree)
    edit(tree, "backend/booking/NODE.md", old, new)
    assert pend(tree) == {("frontend/seatmap", "backend/booking"), ("reports/weekly", "backend/booking")}
    assert {f.code for f in check(Garden.load(tree)).findings} == {"change-pending"}


def test_body_priority_and_whitespace_changes_ignored(tree):
    locked(tree)
    edit(tree, "backend/booking/NODE.md", "확정 예약은", "확정된 예약은")
    edit(tree, "backend/booking/NODE.md", "priority: 1", "priority: 3")
    edit(tree, "backend/booking/NODE.md", "좌석 예약의 중복을 막는다", "좌석   예약의 **중복**을  막는다")
    assert pend(tree) == set()


def test_ack_resolves_and_logs(tree):
    locked(tree)
    edit(tree, "backend/booking/NODE.md", "(id, zone, status)", "(id, zone, status, until)")
    done = lock.ack(Garden.load(tree), "frontend/seatmap", source="backend/booking", note="until 표시 안 함", today=DAY2)
    assert done == ["backend/booking"]
    assert pend(tree) == {("reports/weekly", "backend/booking")}
    g = Garden.load(tree)
    entry = read_history(g, g.nodes["frontend/seatmap"])[-1]
    assert entry.date == DAY2 and "backend/booking 변경 확인" in entry.text and "until 표시 안 함" in entry.text


def test_ack_all_and_errors(tree):
    locked(tree)
    edit(tree, "backend/booking/NODE.md", "(id, zone, status)", "(id, zone, status, until)")
    assert lock.ack(Garden.load(tree), "reports/weekly", all_pending=True, today=DAY2) == ["backend/booking"]
    assert lock.ack(Garden.load(tree), "reports/weekly", all_pending=True, today=DAY2) == []
    with pytest.raises(lock.LockError):
        lock.ack(Garden.load(tree), "reports/weekly", source="backend/db")
    with pytest.raises(lock.LockError):
        lock.ack(Garden.load(tree), "nowhere", all_pending=True)
    with pytest.raises(lock.LockError):
        lock.ack(Garden.load(tree), "reports/weekly")


def test_alert_text(tree):
    locked(tree)
    edit(tree, "backend/booking/NODE.md", "(id, zone, status)", "(id, zone, status, until)")
    g = Garden.load(tree)
    log(g, g.nodes["backend/booking"], "종료 시각 추가", why="곧 빌 자리 표시", today=DAY2)
    log(g, g.nodes["backend/booking"], "옛 변경", today="2026-09-01")
    text = lock.alert_text(g, [p for p in lock.pending(g) if p.a == "frontend/seatmap"])
    assert text.startswith("[garden] 확인 필요 1건")
    assert "- frontend/seatmap ← backend/booking" in text
    assert "- provides: 좌석 상태 목록 (id, zone, status)" in text
    assert "+ provides: 좌석 상태 목록 (id, zone, status, until)" in text
    assert "종료 시각 추가" in text and "옛 변경" not in text
    assert "garden ack frontend/seatmap --from backend/booking" in text


def test_structure_changes(tree):
    locked(tree)
    shutil.move(tree / "backend" / "db", tree / "db")
    edit(tree, "backend/booking/NODE.md", "- backend/db", "- db")
    (tree / "frontend/NODE.md").unlink()
    write_tree(tree, {"reports/weekly/NODE.md": card(purpose="운영자가 한 주 흐름을 본다", why="x", serves=["G3"], needs=["backend/booking", "db"])})
    found = {f.code for f in lock.status(Garden.load(tree))}
    assert {"edge-unlocked", "edge-stale", "parent-changed"} <= found
    added = lock.lock_missing(Garden.load(tree))
    assert set(added) == {("backend/booking", "db"), ("reports/weekly", "db")}
    assert lock.status(Garden.load(tree)) == []


def test_lock_refuses_with_pending(tree):
    locked(tree)
    edit(tree, "backend/db/NODE.md", "예약 저장·조회 함수", "예약 저장·조회·삭제 함수")
    ok, msg = lock.lock_all(Garden.load(tree), today=DAY2)
    assert not ok and "확인 대기" in msg
    ok, _ = lock.lock_all(Garden.load(tree), force=True, today=DAY2)
    assert ok and pend(tree) == set()


def test_history_and_resume(tree):
    g = locked(tree)
    n = g.nodes["frontend/seatmap"]
    line = log(g, n, "첫 시안 | 모바일", why="데모", evidence="index.html", today=DAY1)
    assert line == "- 2026-09-20 | 변경: 첫 시안 / 모바일 | 이유: 데모 | 목표: G2 | 근거: index.html"
    assert (tree / "frontend/seatmap/HISTORY.md").read_text(encoding="utf-8").startswith("# HISTORY — frontend/seatmap")
    edit(tree, "backend/booking/NODE.md", "(id, zone, status)", "(id, zone, status, until)")
    text = resume_text(Garden.load(tree), "frontend/seatmap", today=DAY2)
    assert text.startswith("[resume] demo — 2026-09-21")
    assert "## frontend/seatmap — 빈 좌석을 3초 안에 파악하게 한다" in text
    assert "needs backend/booking" in text and "이유: 첫 화면에서" in text
    assert "첫 시안 / 모바일" in text
    assert "확인 필요: frontend/seatmap ← backend/booking" in text
    assert "## backend/booking" not in text


def break_lock(tree, text="<<<<<<< HEAD\n{}\n"):
    (tree / ".garden/concept.lock").write_text(text, encoding="utf-8")


@pytest.mark.parametrize("text", ["<<<<<<< HEAD\n{}\n", "[]", '{"edges": []}', '{"edges": {"a <- b": 3}}'])
def test_unreadable_lock_is_reported_not_raised(tree, text):
    locked(tree)
    break_lock(tree, text)
    g = Garden.load(tree)
    assert lock.safe_pending(g) == []
    found = [f for f in check(g).findings if f.code == "lock-parse"]
    assert found and "garden lock --force" in found[0].msg
    with pytest.raises(lock.LockError, match="lock --force"):
        lock.pending(g)


def test_unreadable_lock_recovery(tree):
    locked(tree)
    break_lock(tree)
    ok, msg = lock.lock_all(Garden.load(tree), today=DAY2)
    assert not ok and "--force" in msg
    with pytest.raises(lock.LockError):
        lock.lock_missing(Garden.load(tree))
    with pytest.raises(lock.LockError):
        lock.ack(Garden.load(tree), "reports/weekly", all_pending=True)
    ok, _ = lock.lock_all(Garden.load(tree), force=True, today=DAY2)
    assert ok and lock.status(Garden.load(tree)) == []


def test_top_level_parent_is_empty_and_old_marker_is_accepted(tree):
    locked(tree)
    data = json.loads((tree / ".garden/concept.lock").read_text(encoding="utf-8"))
    assert data["nodes"]["backend"]["parent"] == ""
    data["nodes"]["backend"]["parent"] = "seed"
    (tree / ".garden/concept.lock").write_text(json.dumps(data), encoding="utf-8")
    assert lock.status(Garden.load(tree)) == []


def test_resume_keeps_project_level_findings(tree):
    locked(tree)
    (tree / ".garden/concept.lock").write_text("<<<<<<< HEAD\n", encoding="utf-8")
    text = resume_text(Garden.load(tree), "frontend/seatmap", today=DAY2)
    assert "lock을 읽을 수 없음" in text or "concept.lock`을 읽을 수 없음" in text
