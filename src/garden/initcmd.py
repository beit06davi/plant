from __future__ import annotations

import copy
import difflib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from garden import lock
from garden.cards import read_text
from garden.tree import Garden

TEMPLATES = Path(__file__).parent / "templates"
SKILLS = ("guide", "plant", "map", "resume")
STANDALONE_SKILL_PREFIX = "garden-"
HOOK_MARK = "-m garden hook"
BLOCK_START = "<!-- garden:start -->"
BLOCK_END = "<!-- garden:end -->"
CARD_KEYS = ("purpose", "why", "serves", "priority", "needs", "provides")


class InitError(Exception):
    pass


def python_path(python: str | None = None) -> str:
    return (python or sys.executable).replace("\\", "/")


def garden_command(python: str | None = None, plugin: bool = False) -> str:
    return "garden" if plugin else f'"{python_path(python)}" -m garden'


def hook_command(kind: str, python: str | None = None) -> str:
    return f"{garden_command(python)} hook {kind}"


def garden_hooks(python: str | None = None) -> dict:
    return {
        "PreToolUse": [{
            "matcher": "Read|Edit|Write|MultiEdit|NotebookEdit|Grep|Glob",
            "hooks": [{"type": "command", "command": hook_command("pre", python), "timeout": 10}],
        }],
        "PostToolUse": [{
            "matcher": "Edit|Write|MultiEdit",
            "hooks": [{"type": "command", "command": hook_command("post", python), "timeout": 30}],
        }],
        "PostCompact": [{
            "hooks": [{"type": "command", "command": hook_command("compact", python), "timeout": 10}],
        }],
    }


def _is_garden_entry(entry) -> bool:
    return isinstance(entry, dict) and any(
        HOOK_MARK in str(h.get("command", "")) for h in entry.get("hooks", []) if isinstance(h, dict)
    )


def merge_settings(existing: dict, python: str | None = None) -> dict:
    result = copy.deepcopy(existing) if existing else {}
    hooks = result.setdefault("hooks", {})
    for event, entries in garden_hooks(python).items():
        current = [e for e in hooks.get(event, []) if not _is_garden_entry(e)]
        hooks[event] = current + entries
    return result


def skill_name(skill: str, plugin: bool) -> str:
    return skill if plugin else STANDALONE_SKILL_PREFIX + skill


def render(template: str, project: str = "", python: str | None = None, plugin: bool = False) -> str:
    cmd = garden_command(python, plugin)
    guide = "/garden:guide" if plugin else f"/{skill_name('guide', False)}"
    if plugin:
        note = "`garden` 명령은 garden 플러그인이 제공한다 (Bash 도구에서 바로 실행)."
    else:
        note = f"이 문서에서 `garden`은 `{cmd}`을 뜻한다. Bash로 실행할 때는 이 전체 명령을 쓴다."
    text = (TEMPLATES / template).read_text(encoding="utf-8")
    return (text.replace("{{project}}", project).replace("{{garden_note}}", note)
            .replace("{{garden}}", cmd).replace("{{guide}}", guide)
            .replace("{{skill_prefix}}", "" if plugin else STANDALONE_SKILL_PREFIX))


def claude_block(project: str, python: str | None, plugin: bool) -> str:
    return f"{BLOCK_START}\n{render('CLAUDE.md', project, python, plugin).strip()}\n{BLOCK_END}\n"


@dataclass
class InitResult:
    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    settings_diff: str = ""


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def init(
    root: Path,
    project: str | None = None,
    python: str | None = None,
    dry_run: bool = False,
    plugin: bool = False,
) -> InitResult:
    """Create whatever is missing. Existing files are never overwritten; CLAUDE.md only gains a marked block.
    plugin=True: the plugin supplies hooks and skills, so only project files are written."""
    root = Path(root).resolve()
    if project is None and (root / "garden.yaml").is_file():
        from garden.model import load_config

        project = load_config(root).project
    project = project or root.name
    plan: dict[str, str] = {
        "SEED.md": render("SEED.md", project, python, plugin),
        "garden.yaml": render("garden.yaml", project, python, plugin),
        ".garden/.gitignore": "cache/\n",
    }
    if not plugin:
        for skill in SKILLS:
            plan[f".claude/skills/{skill_name(skill, False)}/SKILL.md"] = render(f"skills/{skill}/SKILL.md", project, python)

    result = InitResult()
    for rel, content in plan.items():
        path = root / rel
        if path.exists():
            result.skipped.append(rel)
            continue
        result.created.append(rel)
        if not dry_run:
            _write(path, content)

    claude_md = root / "CLAUDE.md"
    block = claude_block(project, python, plugin)
    if not claude_md.exists():
        result.created.append("CLAUDE.md")
        if not dry_run:
            _write(claude_md, block)
    elif BLOCK_START in read_text(claude_md):
        result.skipped.append("CLAUDE.md")
    else:
        result.updated.append("CLAUDE.md")
        if not dry_run:
            before = read_text(claude_md).rstrip("\n")
            _write(claude_md, f"{before}\n\n{block}")

    if plugin:
        return result
    settings_path = root / ".claude" / "settings.json"
    before = read_text(settings_path) if settings_path.is_file() else ""
    try:
        existing = json.loads(before) if before.strip() else {}
    except json.JSONDecodeError as e:
        raise InitError(f".claude/settings.json을 읽을 수 없음 (JSON 오류: {e})") from e
    after = json.dumps(merge_settings(existing, python), ensure_ascii=False, indent=2) + "\n"
    if after != before:
        result.settings_diff = "".join(difflib.unified_diff(
            before.splitlines(keepends=True), after.splitlines(keepends=True),
            ".claude/settings.json (before)", ".claude/settings.json (after)",
        ))
        (result.updated if before else result.created).append(".claude/settings.json")
        if not dry_run:
            _write(settings_path, after)
    else:
        result.skipped.append(".claude/settings.json")
    return result


def card_text(meta: dict, body: str = "") -> str:
    ordered = {k: meta[k] for k in CARD_KEYS if meta.get(k) not in (None, "", [])}
    ordered.update({k: v for k, v in meta.items() if k not in CARD_KEYS and v not in (None, "", [])})
    front = yaml.safe_dump(ordered, allow_unicode=True, sort_keys=False, width=1000)
    body = body.strip()
    return f"---\n{front}---\n" + (f"{body}\n" if body else "")


def add(
    g: Garden,
    folder,
    purpose: str,
    serves: list[str] | None = None,
    why: str = "",
    priority: int | None = None,
    needs: list[str] | None = None,
    provides: str = "",
    body: str = "",
    today: str | None = None,
) -> Path:
    """Write <folder>/NODE.md. serves defaults to the nearest parent card's goals."""
    rel = g.rel(folder)
    if rel is None or rel == "":
        raise InitError(f"프로젝트 안의 하위 폴더여야 합니다: {folder}")
    if g.ignored(rel):
        raise InitError(f"garden.yaml의 ignore에 걸리는 폴더입니다: {rel}")
    if (g.root / rel / "NODE.md").exists():
        raise InitError(f"이미 카드가 있습니다: {rel}/NODE.md")
    purpose = " ".join(purpose.split())
    if not purpose:
        raise InitError("purpose(이 폴더가 있는 이유 한 줄)가 필요합니다")
    parent = g.owner(rel)
    serves = list(serves or (parent.serves if parent else []))
    if not serves:
        raise InitError("serves(이 폴더가 섬기는 SEED 목표 id)가 필요합니다 — 예: --serves G1")
    if g.seed is not None:
        known = [x.id for x in g.seed.goals]
        unknown = [s for s in serves if s not in known]
        if unknown:
            raise InitError(f"SEED에 없는 목표: {', '.join(unknown)} (있는 목표: {', '.join(known) or '없음'})")
    if priority is not None and priority < 1:
        raise InitError("priority는 1 이상의 정수입니다 (1이 형제 중 먼저)")
    needs = [n.replace("\\", "/").strip("/") for n in (needs or [])]
    for target in needs:
        if target == rel:
            raise InitError("자기 자신을 needs에 넣을 수 없습니다")
        if target not in g.nodes:
            raise InitError(f"needs 대상 카드가 없습니다: {target} — 먼저 그 폴더에 카드를 만드세요")
    meta = {"purpose": purpose, "why": " ".join(why.split()), "serves": serves,
            "priority": priority, "needs": needs, "provides": " ".join(provides.split())}
    path = g.root / rel / "NODE.md"
    _write(path, card_text(meta, body))
    if lock.lock_path(g).is_file() and needs:
        lock.lock_missing(Garden.load(g.root), today=today)
    return path
