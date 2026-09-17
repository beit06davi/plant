from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path, PurePosixPath

from garden import lock
from garden.lineage import context
from garden.tree import Garden

SEED_NOTE = "[garden] SEED.md가 바뀜 — 목표 id나 순서가 바뀌었으면 카드의 serves를 확인 (`garden check`)"
CARD_LEVELS = ("error", "warning")


def read_input(stream) -> dict:
    raw = stream.read()
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8-sig", errors="replace")
    data = json.loads(raw.lstrip("﻿"))
    if not isinstance(data, dict):
        raise ValueError("hook input is not an object")
    return data


def find_project(cwd: str | None) -> Path | None:
    start = Path(cwd or os.getcwd())
    for d in [start, *start.parents]:
        if (d / "garden.yaml").is_file():
            return d
    return None


def target_path(tool_input: dict) -> str | None:
    for key in ("file_path", "notebook_path", "path"):
        value = tool_input.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _session_file(root: Path, session_id: str | None) -> Path:
    name = re.sub(r"[^A-Za-z0-9_.-]", "_", session_id or "") or "nosession"
    return root / ".garden" / "cache" / f"{name}.json"


class Cache:
    """Per session: which agent already saw which block, so unchanged blocks are not repeated."""

    def __init__(self, root: Path, session_id: str | None):
        self.path = _session_file(root, session_id)
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.data = {}
        if not isinstance(self.data, dict) or not isinstance(self.data.get("seen"), dict):
            self.data = {"seen": {}}
        self.dirty = False

    def fresh(self, agent: str, node_id: str, fingerprint: str) -> bool:
        key = f"{agent}|{node_id}"
        if self.data["seen"].get(key) == fingerprint:
            return False
        self.data["seen"][key] = fingerprint
        self.dirty = True
        return True

    def save(self) -> None:
        if not self.dirty:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.path)


def _out(event: str, text: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}


def pre(data: dict) -> dict | None:
    root = find_project(data.get("cwd"))
    path = target_path(data.get("tool_input") or {})
    if root is None or path is None:
        return None
    g = Garden.load(root)
    node = g.node_for(path)
    if node is None:
        return None
    pending = []
    if lock.lock_path(g).is_file():
        pending = [lock.pending_line(p.a, p.b) for p in lock.pending(g) if p.a == node.id]
    text = context(g, node, pending=pending)
    cache = Cache(root, data.get("session_id"))
    if not cache.fresh(str(data.get("agent_id") or "main"), node.id, lock.fingerprint(text)):
        return None
    cache.save()
    return _out("PreToolUse", text)


def post(data: dict) -> dict | None:
    root = find_project(data.get("cwd"))
    path = target_path(data.get("tool_input") or {})
    if root is None or path is None:
        return None
    g = Garden.load(root)
    rel = g.rel(path)
    if not rel:
        return None
    from garden.validate import check

    parts: list[str] = []
    if rel.lower() == "seed.md":
        parts.append(SEED_NOTE)
        parts += [f"[garden] {f.where}: {f.msg}" for f in check(g, propagation=False).of("error")]
    elif PurePosixPath(rel).name.lower() == "node.md":
        folder = str(PurePosixPath(rel).parent)
        node = g.nodes.get(folder)
        where = {folder, rel}
        parts += [
            f"[garden] 카드 {f.level} {folder}: {f.msg}"
            for f in check(g).findings if f.level in CARD_LEVELS and f.where in where
        ]
        if node is not None and lock.lock_path(g).is_file():
            waiting = [p for p in lock.pending(g) if p.b == node.id]
            if waiting:
                parts.append(lock.alert_text(g, waiting))
    if not parts:
        return None
    return _out("PostToolUse", "\n".join(parts))


def compact(data: dict) -> dict | None:
    root = find_project(data.get("cwd"))
    if root is not None:
        try:
            _session_file(root, data.get("session_id")).unlink()
        except OSError:
            pass
    return None


HANDLERS = {"pre": pre, "post": post, "compact": compact}


def run(kind: str, stdin=None, stdout=None) -> int:
    """Fail open: a broken hook must never block the tool call, so this always returns 0."""
    stdin = stdin if stdin is not None else getattr(sys.stdin, "buffer", sys.stdin)
    stdout = stdout if stdout is not None else sys.stdout
    try:
        data = read_input(stdin)
    except (ValueError, OSError, UnicodeError):
        return 0
    try:
        result = HANDLERS[kind](data)
    except Exception as e:
        print(f"garden hook {kind}: {e!r}", file=sys.stderr)
        return 0
    if result:
        stdout.write(json.dumps(result, ensure_ascii=True))
        stdout.flush()
    return 0
