import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import base_files, write_tree

from garden.initcmd import init

ROOT = Path(__file__).resolve().parents[1]
SH = shutil.which("sh")


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def test_manifest_and_marketplace():
    plugin = load(".claude-plugin/plugin.json")
    assert plugin["name"] == "garden"
    assert re.fullmatch(r"\d+\.\d+\.\d+", plugin["version"])
    market = load(".claude-plugin/marketplace.json")
    assert re.fullmatch(r"[a-z0-9-]+", market["name"])
    assert market["owner"]["name"]
    assert market["plugins"][0]["name"] == "garden"
    assert market["plugins"][0]["source"] == "./"


def test_version_matches_package():
    from garden import __version__

    assert load(".claude-plugin/plugin.json")["version"] == __version__


def test_hooks_use_plugin_wrapper():
    hooks = load("hooks/hooks.json")["hooks"]
    assert set(hooks) == {"PreToolUse", "PostToolUse", "PostCompact"}
    for event, entries in hooks.items():
        command = entries[0]["hooks"][0]["command"]
        assert "${CLAUDE_PLUGIN_ROOT}/bin/garden" in command
        assert command.endswith({"PreToolUse": "pre", "PostToolUse": "post", "PostCompact": "compact"}[event])
    assert "Bash" not in hooks["PreToolUse"][0]["matcher"]


def test_plugin_hooks_match_standalone_hooks():
    from garden.initcmd import garden_hooks

    plugin = load("hooks/hooks.json")["hooks"]
    for event, entries in garden_hooks().items():
        assert plugin[event][0].get("matcher") == entries[0].get("matcher"), event


def test_plugin_files_are_built():
    r = subprocess.run([sys.executable, str(ROOT / "scripts/build_plugin.py"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout


def test_no_agents_shipped():
    assert not (ROOT / "agents").exists()


def test_plugin_skills_use_bare_command():
    skills = sorted(p.parent.name for p in (ROOT / "skills").glob("*/SKILL.md"))
    assert skills == ["guide", "map", "plant", "resume"]
    for name in skills:
        text = (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
        assert "-m garden" not in text and "{{" not in text, name
        assert "Bash(garden *)" in text, name
    guide = (ROOT / "skills/guide/SKILL.md").read_text(encoding="utf-8")
    assert "garden add" in guide and "이 형식이 정하지 않는 것" in guide


def test_init_plugin_mode_writes_only_project_files(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    result = init(root, plugin=True)
    assert set(result.created) == {"SEED.md", "garden.yaml", "CLAUDE.md", ".garden/.gitignore"}
    assert not (root / ".claude").exists()
    claude = (root / "CLAUDE.md").read_text(encoding="utf-8")
    assert "/garden:guide" in claude and "-m garden" not in claude
    assert "구조 원칙" in (root / "SEED.md").read_text(encoding="utf-8")


def test_init_standalone_includes_prefixed_skills(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    init(root, python="C:/py/python.exe")
    guide = (root / ".claude/skills/garden-guide/SKILL.md").read_text(encoding="utf-8")
    assert '"C:/py/python.exe" -m garden add' in guide
    assert "/garden-guide" in (root / "CLAUDE.md").read_text(encoding="utf-8")


def _payload(proj, rel="backend/booking/service.py", **extra):
    return json.dumps({
        "session_id": "w", "cwd": str(proj), "tool_name": "Read",
        "tool_input": {"file_path": str(proj / rel)}, **extra,
    }).encode()


@pytest.mark.skipif(SH is None, reason="sh not available")
class TestWrapper:
    def run(self, *args, cwd, stdin=b"", **extra_env):
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
        env.update(extra_env)
        return subprocess.run([SH, str(ROOT / "bin/garden"), *args], cwd=cwd, input=stdin, capture_output=True, env=env, timeout=60)

    def injected(self, r):
        assert r.returncode == 0, r.stderr
        return json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]

    def test_version(self, tmp_path):
        r = self.run("--version", cwd=tmp_path)
        assert r.returncode == 0 and b"garden 0.4" in r.stdout

    def test_hook_outside_project_is_silent(self, tmp_path):
        r = self.run("hook", "pre", cwd=tmp_path, stdin=b'{"tool_name": "Read"}')
        assert r.returncode == 0 and r.stdout == b""

    def test_hook_inside_project(self, tmp_path):
        proj = write_tree(tmp_path / "proj", base_files())
        r = self.run("hook", "pre", cwd=proj / "backend", stdin=_payload(proj, agent_type="garden:x", agent_id="x"))
        assert self.injected(r).startswith("[garden] backend/booking")

    def test_cli_inside_project(self, tmp_path):
        proj = write_tree(tmp_path / "proj", base_files())
        r = self.run("map", cwd=proj)
        assert r.returncode == 0, r.stderr
        assert "booking/" in r.stdout.decode("utf-8")

    def test_hook_survives_msys_no_pathconv(self, tmp_path):
        proj = write_tree(tmp_path / "proj", base_files())
        r = self.run("hook", "pre", cwd=proj, stdin=_payload(proj), MSYS_NO_PATHCONV="1")
        assert "[garden] backend/booking" in self.injected(r)

    def test_hook_uses_windows_project_dir(self, tmp_path):
        proj = write_tree(tmp_path / "proj", base_files())
        r = self.run("hook", "pre", cwd=tmp_path, stdin=_payload(proj), CLAUDE_PROJECT_DIR=str(proj / "backend"))
        assert "[garden] backend/booking" in self.injected(r)

    def test_hook_failure_never_blocks(self, tmp_path):
        proj = write_tree(tmp_path / "proj", base_files())
        r = self.run("hook", "pre", cwd=proj, stdin=_payload(proj), GARDEN_PYTHON="false")
        assert r.returncode == 0
        assert r.stdout == b""
        assert b"hook failed" in r.stderr

    def test_cli_failure_keeps_exit_code(self, tmp_path):
        r = self.run("--version", cwd=tmp_path, GARDEN_PYTHON="false")
        assert r.returncode != 0
