from conftest import card, write_tree

from garden import lock
from garden.report import map_mermaid, map_order, map_tree, order_levels
from garden.tree import Garden


def test_tree(tree):
    lines = map_tree(Garden.load(tree)).splitlines()
    assert lines[0].startswith("demo   G1 이중 예약 없는 예약 > G2")
    assert lines[1].startswith("├─ backend/") and "G1  #1  예약 도메인과 저장소" in lines[1]
    assert lines[2].startswith("│  ├─ booking/") and "← backend/db" in lines[2]
    assert lines[3].startswith("│  └─ db/") and "#2" in lines[3]
    assert lines[4].startswith("├─ frontend/")
    assert lines[5].startswith("│  └─ seatmap/")
    assert lines[6].startswith("└─ reports/weekly/")
    assert "카드 없는 최상위 폴더: docs/" in lines


def test_tree_why_and_principles(tree):
    text = map_tree(Garden.load(tree), show_why=True)
    assert "\n│  │    ↳ 이유: 예약 판단을 한곳에 모아" in text
    assert "구조 원칙 (SEED)\n- 데이터를 만드는 폴더가 먼저" in text
    assert "↳ 이유" not in map_tree(Garden.load(tree))


def test_tree_flags(tree):
    lock.lock_all(Garden.load(tree), today="2026-09-20")
    p = tree / "backend/booking/NODE.md"
    p.write_text(p.read_text(encoding="utf-8").replace("(id, zone, status)", "(id, zone, status, until)"), encoding="utf-8")
    write_tree(tree, {"docs/NODE.md": card(purpose="문서", why="x", serves=["G9"])})
    text = map_tree(Garden.load(tree))
    seat = next(l for l in text.splitlines() if "seatmap/" in l)
    assert "⚠ 확인 필요(← backend/booking)" in seat
    docs = next(l for l in text.splitlines() if l.startswith("├─ docs/") or l.startswith("└─ docs/"))
    assert "⚠ 목표 연결 없음" in docs
    assert "카드 없는 최상위 폴더" not in text


def test_order(tree):
    g = Garden.load(tree)
    levels, unlinked, stuck = order_levels(g)
    assert levels == [["backend/db"], ["backend/booking"], ["frontend/seatmap", "reports/weekly"]]
    assert unlinked == ["backend", "frontend"] and stuck == []
    text = map_order(g)
    assert "1. backend/db(G1)" in text
    assert "3. frontend/seatmap(G2), reports/weekly(G3)" in text
    assert "순서 연결 없음: backend, frontend" in text


def test_order_cycle(tree):
    p = tree / "backend/db/NODE.md"
    p.write_text(p.read_text(encoding="utf-8").replace("priority: 2", "priority: 2\nneeds:\n- backend/booking"), encoding="utf-8")
    text = map_order(Garden.load(tree))
    assert "⚠ 순환 때문에 순서를 정할 수 없음" in text and "backend/booking" in text


def test_order_parent_before_child_in_same_step(tmp_path):
    root = write_tree(tmp_path / "p", {
        "SEED.md": "# SEED\n- G1: x\n",
        "src/NODE.md": card(purpose="s", serves=["G1"]),
        "data/NODE.md": card(purpose="d", serves=["G1"], priority=2, needs=["src"]),
        "data/raw/NODE.md": card(purpose="r", serves=["G1"], priority=1, needs=["src"]),
    })
    levels, _, _ = order_levels(Garden.load(root))
    assert levels == [["src"], ["data", "data/raw"]]


def test_order_empty(tmp_path):
    root = write_tree(tmp_path / "p", {"SEED.md": "# SEED\n- G1: x\n", "a/NODE.md": card(purpose="x", serves=["G1"])})
    assert "(needs로 연결된 폴더 없음)" in map_order(Garden.load(root))


def test_mermaid(tree):
    text = map_mermaid(Garden.load(tree))
    assert text.startswith("flowchart TD")
    # ids follow sorted folder ids: backend n1, backend/booking n2, backend/db n3, frontend n4, frontend/seatmap n5
    assert "seed --> n1\n" in text
    assert "n1 --> n2\n" in text
    assert "n3 -. 먼저 .-> n2\n" in text
    assert 'n5["frontend/seatmap<br/>G2 · 빈 좌석을 3초 안에 파악하게 한다"]' in text


def test_mermaid_non_ascii_folders_stay_apart(tmp_path):
    root = write_tree(tmp_path / "p", {
        "SEED.md": "# SEED\n- G1: x\n",
        "문서/NODE.md": card(purpose="a", serves=["G1"]),
        "자료/NODE.md": card(purpose="b", serves=["G1"], needs=["문서"]),
    })
    text = map_mermaid(Garden.load(root))
    assert 'n1["문서<br/>G1 · a"]' in text and 'n2["자료<br/>G1 · b"]' in text
    assert "seed --> n1\n" in text and "seed --> n2\n" in text
    assert text.endswith("n1 -. 먼저 .-> n2")


def test_top_level_folder_named_seed(tmp_path):
    root = write_tree(tmp_path / "p", {
        "SEED.md": "# SEED\n- G1: x\n",
        "seed/NODE.md": card(purpose="씨앗 데이터", serves=["G1"]),
        "seed/raw/NODE.md": card(purpose="원본", serves=["G1"]),
    })
    g = Garden.load(root)
    assert g.nodes["seed/raw"].parent == "seed" and g.nodes["seed"].parent == ""
    lines = map_tree(g).splitlines()
    assert lines[1].startswith("└─ seed/") and lines[2].startswith("   └─ raw/")
    assert "seed --> n1\n" in map_mermaid(g) and "n1 --> n2" in map_mermaid(g)
