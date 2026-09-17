import json

from conftest import card, write_tree

from garden.lineage import context, context_data, trace_text
from garden.tree import Garden

BOOKING = "좌석 예약의 중복을 막는다"
DB = "예약 데이터를 저장한다"


def ctx(tree, node_id, **kw):
    g = Garden.load(tree)
    return context(g, g.nodes[node_id], **kw)


def test_concept_context(tree):
    t = ctx(tree, "backend/booking", budget=10000)
    lines = t.splitlines()
    assert lines[0] == f"[garden] backend/booking — {BOOKING}"
    assert "goal: G1 이중 예약 없는 예약" in t
    assert "higher:" not in t
    assert "lineage: SEED > backend(예약 도메인과 저장소) > backend/booking" in t
    assert "why: 예약 판단을 한곳에 모아 화면이 규칙을 모르게 한다" in t
    assert "siblings: backend 아래 중요도 순 — backend/booking(1) > backend/db(2) (이 폴더: 1번째)" in t
    assert f"needs: backend/db — {DB} · 주는 것: 예약 저장·조회 함수" in t
    assert "provides: 좌석 상태 목록 (id, zone, status)" in t
    assert "needed by: frontend/seatmap — 빈 좌석을 3초 안에 파악하게 한다" in t
    assert "needed by: reports/weekly — 운영자가 한 주 흐름을 본다" in t
    assert "notes:\n  ## 규칙\n  - 확정 예약은 좌석·시간마다 하나" in t
    assert "저장 방식이 바뀌어도" not in t


def test_detail_none_and_full(tree):
    none = ctx(tree, "backend/booking", detail="none", budget=10000)
    assert "needs: backend/db\n" in none + "\n"
    assert DB not in none
    assert "needed by: frontend/seatmap, reports/weekly" in none
    full = ctx(tree, "frontend/seatmap", detail="full", budget=10000)
    assert f"needs: backend/booking — {BOOKING} · 주는 것: 좌석 상태 목록" in full
    assert "    이유: 예약 판단을 한곳에 모아" in full
    assert "    ## 규칙" in full


def test_config_sets_default_detail(tree):
    (tree / "garden.yaml").write_text("project: demo\ncontext: none\n", encoding="utf-8")
    assert BOOKING not in ctx(tree, "frontend/seatmap", budget=10000)


def test_higher_goals_and_pending(tree):
    t = ctx(tree, "reports/weekly", budget=10000, pending=["reports/weekly ← backend/booking: …"])
    assert "higher: G1 이중 예약 없는 예약 | G2 3초 안에 빈 좌석 파악" in t
    assert "check: reports/weekly ← backend/booking" in t
    assert "siblings: SEED 아래 중요도 순 — backend(1) > frontend(2) > reports/weekly (이 폴더: 3번째)" in t


def test_budget_drops_far_ancestors_first(tree):
    write_tree(tree, {"frontend/seatmap/mobile/NODE.md": card(purpose="모바일 화면", why="작은 화면 따로", serves=["G2"])})
    g = Garden.load(tree)
    node = g.nodes["frontend/seatmap/mobile"]
    full = context(g, node, budget=10000)
    assert "frontend(이용자 화면)" in full
    trimmed = context(g, node, budget=len(full) - 3)
    assert "frontend(이용자 화면)" not in trimmed
    assert "frontend/seatmap(빈 좌석을 3초 안에 파악하게 한다)" in trimmed


def test_budget_keeps_notes_longest(tree):
    g = Garden.load(tree)
    node = g.nodes["backend/booking"]
    full = context(g, node, budget=10000)
    t = context(g, node, budget=len(full) - 200)
    for kept in ("[garden]", "goal:", "why:", "needs:", "provides:", "notes:"):
        assert kept in t
    assert "more:" not in t and "needed by:" not in t


def test_budget_hard_truncation(tree):
    t = ctx(tree, "backend/booking", budget=120)
    assert len(t) <= 120 and t.endswith("`garden context backend/booking`)")


def test_trace(tree):
    g = Garden.load(tree)
    t = trace_text(g, g.nodes["backend/booking"])
    assert t.splitlines()[0] == f"backend/booking — {BOOKING}"
    assert "└─ backend — 예약 도메인과 저장소 (중요도 1)" in t
    assert "   이유: 예약 판단을" in t
    assert "needs: backend/db" in t
    assert "needed by: frontend/seatmap, reports/weekly" in t


def test_context_data(tree):
    g = Garden.load(tree)
    data = context_data(g, g.nodes["frontend/seatmap"], budget=10000)
    json.dumps(data, ensure_ascii=False)
    assert (data["node"], data["goal"], data["detail"], data["trimmed"]) == ("frontend/seatmap", "G2", "concept", False)
    assert data["chars"] == len(data["text"])
