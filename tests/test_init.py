import json

import pytest
import yaml

from garden import lock
from garden.cards import split_frontmatter
from garden.initcmd import BLOCK_START, InitError, add, init, merge_settings
from garden.tree import Garden
from garden.validate import check


def meta_of(path):
    meta, body, error = split_frontmatter(path.read_text(encoding="utf-8"))
    assert error is None
    return meta, body


def test_init_is_idempotent(tmp_path):
    root = tmp_path / "shop"
    root.mkdir()
    first = init(root, python="C:/py/python.exe")
    assert {"SEED.md", "garden.yaml", "CLAUDE.md", ".garden/.gitignore", ".claude/settings.json",
            ".claude/skills/garden-guide/SKILL.md", ".claude/skills/garden-resume/SKILL.md"} <= set(first.created)
    assert yaml.safe_load((root / "garden.yaml").read_text(encoding="utf-8"))["project"] == "shop"
    assert yaml.safe_load((root / "garden.yaml").read_text(encoding="utf-8"))["context"] == "concept"
    (root / "SEED.md").write_text("# SEED\n- G1: 내 목표\n", encoding="utf-8")
    second = init(root, python="C:/py/python.exe")
    assert second.created == [] and second.updated == []
    assert (root / "SEED.md").read_text(encoding="utf-8") == "# SEED\n- G1: 내 목표\n"


def test_init_appends_block_to_existing_claude_md(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    (root / "CLAUDE.md").write_text("# 기존 지시\n- 한국어로 답한다\n", encoding="utf-8")
    result = init(root, plugin=True)
    assert result.updated == ["CLAUDE.md"]
    text = (root / "CLAUDE.md").read_text(encoding="utf-8")
    assert text.startswith("# 기존 지시\n- 한국어로 답한다\n\n" + BLOCK_START)
    assert "@SEED.md" in text
    init(root, plugin=True)
    assert (root / "CLAUDE.md").read_text(encoding="utf-8") == text


def test_init_dry_run_writes_nothing(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    result = init(root, dry_run=True)
    assert "SEED.md" in result.created and result.settings_diff
    assert list(root.iterdir()) == []


def test_templates_have_no_old_vocabulary(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    init(root, python="py")
    text = "\n".join(p.read_text(encoding="utf-8") for p in root.rglob("*") if p.is_file())
    for word in ("root-worker", "shoot", "stem", "rigor", "sprout", "harvest", "나이테", "{{"):
        assert word not in text, word


def test_merge_settings_keeps_user_hooks():
    user = {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "mine"}]}]}, "x": 1}
    merged = merge_settings(merge_settings(user, python="py"), python="py")
    assert merged["x"] == 1
    pre = merged["hooks"]["PreToolUse"]
    assert pre[0]["hooks"][0]["command"] == "mine"
    assert len(pre) == 2 and pre[1]["hooks"][0]["command"] == '"py" -m garden hook pre'


def test_init_rejects_broken_settings(tmp_path):
    root = tmp_path / "p"
    (root / ".claude").mkdir(parents=True)
    (root / ".claude/settings.json").write_text("{broken", encoding="utf-8")
    with pytest.raises(InitError):
        init(root)


def test_add_writes_ordered_card(tree):
    g = Garden.load(tree)
    path = add(g, tree / "backend" / "payments", purpose="환불  규칙을 모은다", why="예약과 돈을 분리",
               priority=3, needs=["backend/db"], provides="환불 가능 여부")
    meta, body = meta_of(path)
    assert list(meta) == ["purpose", "why", "serves", "priority", "needs", "provides"]
    assert meta["purpose"] == "환불 규칙을 모은다"
    assert meta["serves"] == ["G1"]
    assert body == ""
    g = Garden.load(tree)
    assert g.nodes["backend/payments"].parent == "backend"
    assert check(g).exit_code == 0


def test_add_minimal_top_level(tree):
    path = add(Garden.load(tree), "ops", purpose="운영 스크립트", serves=["G3"])
    meta, _ = meta_of(path)
    assert meta == {"purpose": "운영 스크립트", "serves": ["G3"]}


@pytest.mark.parametrize("kwargs,message", [
    ({"folder": "backend", "purpose": "x"}, "이미 카드"),
    ({"folder": "", "purpose": "x", "serves": ["G1"]}, "하위 폴더"),
    ({"folder": "../out", "purpose": "x", "serves": ["G1"]}, "하위 폴더"),
    ({"folder": ".claude/x", "purpose": "x", "serves": ["G1"]}, "ignore"),
    ({"folder": "ops", "purpose": " ", "serves": ["G1"]}, "purpose"),
    ({"folder": "ops", "purpose": "x"}, "serves"),
    ({"folder": "ops", "purpose": "x", "serves": ["G9"]}, "SEED에 없는 목표: G9"),
    ({"folder": "ops", "purpose": "x", "serves": ["G1"], "priority": 0}, "priority"),
    ({"folder": "ops", "purpose": "x", "serves": ["G1"], "needs": ["nowhere"]}, "needs 대상"),
    ({"folder": "ops", "purpose": "x", "serves": ["G1"], "needs": ["ops"]}, "자기 자신"),
])
def test_add_rejects(tree, kwargs, message):
    with pytest.raises(InitError, match=message):
        add(Garden.load(tree), **kwargs)
    assert not (tree / "ops/NODE.md").exists()


def test_add_records_new_links_when_locked(tree):
    lock.lock_all(Garden.load(tree), today="2026-09-20")
    add(Garden.load(tree), "frontend/admin", purpose="관리 화면", needs=["backend/booking"], today="2026-09-21")
    data = json.loads((tree / ".garden/concept.lock").read_text(encoding="utf-8"))
    assert data["edges"]["frontend/admin <- backend/booking"]["at"] == "2026-09-21"
    assert lock.status(Garden.load(tree)) == []
