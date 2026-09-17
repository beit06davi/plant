import json

from conftest import card, write_tree

from garden.tree import Garden
from garden.validate import check


def codes(tree, level=None, files=None):
    if files:
        write_tree(tree, files)
    return {f.code for f in check(Garden.load(tree)).findings if level is None or f.level == level}


def test_clean_tree(tree):
    r = check(Garden.load(tree))
    assert r.findings == [], [f.msg for f in r.findings]
    assert r.exit_code == 0


def test_seed_missing(tree):
    (tree / "SEED.md").unlink()
    r = check(Garden.load(tree))
    assert "seed-missing" in {f.code for f in r.of("error")} and r.exit_code == 2


def test_required_fields(tree):
    assert {"purpose-missing", "serves-missing"} <= codes(tree, "error", {"backend/db/NODE.md": card(why="x")})


def test_why_missing_is_warning(tree):
    assert "why-missing" in codes(tree, "warning", {"backend/db/NODE.md": card(purpose="x", serves=["G1"])})


def test_invalid_serves(tree):
    assert "serves-invalid" in codes(tree, "error", {"backend/db/NODE.md": card(purpose="x", why="y", serves=["G9"])})


def test_needs_problems(tree):
    files = {
        "backend/db/NODE.md": card(purpose="x", why="y", serves=["G1"], needs=["backend/db", "nowhere"]),
    }
    assert {"needs-self", "needs-missing"} <= codes(tree, "error", files)


def test_needs_cycle(tree):
    files = {"backend/db/NODE.md": card(purpose="x", why="y", serves=["G1"], needs=["backend/booking"])}
    assert "needs-cycle" in codes(tree, "error", files)


def test_priority_rules(tree):
    files = {
        "backend/db/NODE.md": card(purpose="x", why="y", serves=["G1"], priority=1),
        "frontend/NODE.md": card(purpose="x", why="y", serves=["G2"], priority=0),
    }
    found = codes(tree, None, files)
    assert "priority-duplicate" in found and "priority-invalid" in found


def test_unknown_fields_allowed(tree):
    files = {"backend/db/NODE.md": card("## 완료 조건\n- 테스트 통과\n", purpose="x", why="y", serves=["G1"], rigor="strict", owner="kim")}
    assert codes(tree, None, files) == set()


def test_long_card_and_purpose(tree):
    body = "".join(f"- {i}\n" for i in range(80))
    found = codes(tree, "warning", {"backend/db/NODE.md": card(body, purpose="가" * 130, why="y", serves=["G1"])})
    assert {"card-long", "purpose-long"} <= found


def test_config_error(tree):
    (tree / "garden.yaml").write_text("context: everything\n", encoding="utf-8")
    assert "config" in codes(tree, "error")


def test_json(tree):
    write_tree(tree, {"backend/db/NODE.md": card(purpose="x", why="y", serves=["G9"])})
    data = json.loads(check(Garden.load(tree)).to_json())
    assert set(data) == {"errors", "warnings", "reviews", "exit_code"}
    assert data["errors"][0]["code"] == "serves-invalid"
