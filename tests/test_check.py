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
    files = {"backend/db/NODE.md": card("## 완료 조건\n- 테스트 통과\n", purpose="x", why="y", serves=["G1"], team="data", deadline="2026-10")}
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


def test_template_goals_are_errors(tree):
    seed = (tree / "SEED.md").read_text(encoding="utf-8")
    (tree / "SEED.md").write_text(seed.replace("- G2: 3초 안에 빈 좌석 파악", "- G2: <다음 목표> — 측정 기준: <확인 방법>"),
                                  encoding="utf-8")
    r = check(Garden.load(tree))
    found = [f for f in r.of("error") if f.code == "seed-placeholder"]
    assert found and "G2" in found[0].msg and r.exit_code == 2


def test_template_text_outside_goals_is_warning(tree):
    seed = (tree / "SEED.md").read_text(encoding="utf-8")
    (tree / "SEED.md").write_text(seed.replace("- 결제", "- <하지 않기로 한 것>"), encoding="utf-8")
    assert "seed-template" in codes(tree, "warning")
    (tree / "SEED.md").write_text(seed.replace("- 결제", "- List<int> 같은 코드 표기, <br> 태그"), encoding="utf-8")
    assert "seed-template" not in codes(tree)


def test_legacy_config_and_card_keys(tree):
    (tree / "garden.yaml").write_text("garden_version: 0.3\nproject: demo\nread_scope: block\nroles: {a: root}\n",
                                      encoding="utf-8")
    write_tree(tree, {"backend/db/NODE.md": card(purpose="x", why="y", serves=["G1"], name="db", zone="root",
                                                 uses=["root.booking"])})
    r = check(Garden.load(tree))
    by_code = {f.code: f for f in r.of("warning")}
    assert "garden_version, read_scope, roles" in by_code["config-legacy"].msg
    assert by_code["card-legacy"].where == "backend/db"
    assert "zone, uses, name" in by_code["card-legacy"].msg and "needs" in by_code["card-legacy"].msg
    assert not r.of("error")


def test_top_level_priority_duplicate_names_seed(tree):
    edit = tree / "frontend/NODE.md"
    edit.write_text(edit.read_text(encoding="utf-8").replace("priority: 2", "priority: 1"), encoding="utf-8")
    found = [f for f in check(Garden.load(tree)).of("warning") if f.code == "priority-duplicate"]
    assert found[0].where == "SEED"


def test_placeholder_only_when_the_whole_value_is_a_blank(tree):
    seed = (tree / "SEED.md").read_text(encoding="utf-8")
    keep = seed.replace("- G2: 3초 안에 빈 좌석 파악", "- G2: 이용자가 <검색> 화면에서 3초 안에 찾는다 — 측정 기준: List<좌석> 길이")
    (tree / "SEED.md").write_text(keep, encoding="utf-8")
    assert "seed-placeholder" not in codes(tree)
    blank = seed.replace("- G2: 3초 안에 빈 좌석 파악", "- G2: <다음 목표>")
    (tree / "SEED.md").write_text(blank, encoding="utf-8")
    assert "seed-placeholder" in codes(tree, "error")
