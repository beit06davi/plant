import shutil

from conftest import card, write_tree

from garden.model import TOP, find_root
from garden.tree import Garden


def test_nodes_are_folder_paths(tree):
    g = Garden.load(tree)
    assert set(g.nodes) == {"backend", "backend/booking", "backend/db", "frontend", "frontend/seatmap", "reports/weekly"}
    assert g.issues == []


def test_parents_follow_folders(tree):
    g = Garden.load(tree)
    assert g.nodes["backend/booking"].parent == "backend"
    assert g.nodes["backend"].parent == TOP
    assert g.nodes["reports/weekly"].parent == TOP
    assert [n.id for n in g.ancestors("frontend/seatmap")] == ["frontend"]


def test_children_sorted_by_priority(tree):
    g = Garden.load(tree)
    assert [n.id for n in g.children(TOP)] == ["backend", "frontend", "reports/weekly"]
    assert [n.id for n in g.children("backend")] == ["backend/booking", "backend/db"]


def test_fields(tree):
    n = Garden.load(tree).nodes["backend/booking"]
    assert n.purpose == "좌석 예약의 중복을 막는다"
    assert n.why.startswith("예약 판단을")
    assert n.serves == ["G1"] and n.priority == 1
    assert n.needs == ["backend/db"]
    assert n.provides == "좌석 상태 목록 (id, zone, status)"
    assert "확정 예약은" in n.body


def test_dependents_and_goals(tree):
    g = Garden.load(tree)
    assert {n.id for n in g.dependents("backend/booking")} == {"frontend/seatmap", "reports/weekly"}
    assert g.top_goal(g.nodes["frontend/seatmap"]) == "G2"


def test_node_for(tree):
    g = Garden.load(tree)
    assert g.node_for("backend/booking/service.py").id == "backend/booking"
    assert g.node_for("backend/booking").id == "backend/booking"
    assert g.node_for("backend/NODE.md").id == "backend"
    assert g.node_for("docs/notes.md") is None
    assert g.node_for("SEED.md") is None
    assert g.node_for(".git/config") is None


def test_windows_paths(tree):
    g = Garden.load(tree)
    absolute = str(tree).replace("/", "\\") + "\\backend\\booking\\service.py"
    assert g.node_for(absolute).id == "backend/booking"
    assert g.node_for("BACKEND\\Booking\\service.py").id == "backend/booking"
    assert g.node_for(str(tree.parent / "elsewhere" / "x.py")) is None


def test_get_accepts_ids_and_paths(tree):
    g = Garden.load(tree)
    assert g.get("backend/booking").id == "backend/booking"
    assert g.get("backend/booking/").id == "backend/booking"
    assert g.get("frontend/seatmap/index.html").id == "frontend/seatmap"


def test_ignored_and_root_card(tree):
    write_tree(tree, {
        "node_modules/pkg/NODE.md": card(purpose="x", serves=["G1"]),
        "NODE.md": card(purpose="x", serves=["G1"]),
    })
    g = Garden.load(tree)
    assert "node_modules/pkg" not in g.nodes
    assert any(i.code == "root-card" for i in g.issues)


def test_card_parse_error(tree):
    write_tree(tree, {"backend/broken/NODE.md": "no frontmatter\n"})
    assert any(i.code == "card-parse" for i in Garden.load(tree).issues)


def test_moved_folder_changes_parent(tree):
    shutil.move(tree / "backend" / "db", tree / "backend" / "booking" / "db")
    g = Garden.load(tree)
    assert g.nodes["backend/booking/db"].parent == "backend/booking"


def test_priority_parsing(tree):
    write_tree(tree, {
        "a/NODE.md": card(purpose="x", serves=["G1"], priority="3"),
        "b/NODE.md": card(purpose="x", serves=["G1"], priority=True),
        "c/NODE.md": card(purpose="x", serves=["G1"], priority="high"),
    })
    g = Garden.load(tree)
    assert g.nodes["a"].priority == 3
    assert g.nodes["b"].priority is None
    assert g.nodes["c"].priority is None


def test_find_root(tree):
    assert find_root(tree / "backend" / "booking") == tree
