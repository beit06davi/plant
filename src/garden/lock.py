from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from garden.history import history_since, log, today_str
from garden.model import TOP, Node
from garden.tree import Garden
from garden.validate import Finding

LOCK_REL = ".garden/concept.lock"
UNREADABLE = "`.garden/concept.lock`을 읽을 수 없음 (병합 충돌 등) — `garden lock --force`로 다시 기록"
LEGACY_TOP = "seed"  # parent id of top-level cards in early 0.4 lock files
DIFF_LIMIT = 600
_EMPHASIS = re.compile(r"\*\*|__")


class LockError(Exception):
    pass


def lock_path(g: Garden) -> Path:
    return g.root / LOCK_REL


def normalize(value: str) -> str:
    return " ".join(_EMPHASIS.sub("", value).split())


def concept_text(node: Node) -> str:
    """What dependents rely on: purpose, why, and what the folder provides."""
    lines = []
    for key, value in (("purpose", node.purpose), ("why", node.why), ("provides", node.provides)):
        value = normalize(value)
        if value:
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


def fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def edges(g: Garden) -> list[tuple[str, str]]:
    """(a, b): a needs b, so a should check when b's concept changes."""
    return sorted({(n.id, t) for n in g.nodes.values() for t in n.needs if t in g.nodes and t != n.id})


def edge_key(a: str, b: str) -> str:
    return f"{a} <- {b}"


def pending_line(a: str, b: str) -> str:
    return f"{a} ← {b}: {b}의 개념이 바뀜 — {a}에서 영향 확인 (`garden ack {a} --from {b}`)"


def _empty() -> dict:
    return {"version": 1, "nodes": {}, "edges": {}, "snapshots": {}}


def load_lock(g: Garden) -> dict:
    """Raises LockError when the file exists but is not a lock this version can read."""
    path = lock_path(g)
    if not path.is_file():
        return _empty()
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (ValueError, OSError) as e:
        raise LockError(f"{UNREADABLE} [{e.__class__.__name__}]") from e
    if not isinstance(data, dict):
        raise LockError(UNREADABLE)
    base = _empty()
    base["version"] = data.get("version", 1)
    for key in ("nodes", "edges", "snapshots"):
        value = data.get(key, {})
        if not isinstance(value, dict):
            raise LockError(UNREADABLE)
        base[key] = value
    entries = list(base["nodes"].values()) + list(base["edges"].values())
    if not all(isinstance(e, dict) for e in entries) or not all(isinstance(t, str) for t in base["snapshots"].values()):
        raise LockError(UNREADABLE)
    return base


def save_lock(g: Garden, data: dict) -> None:
    referenced = {e["seen"] for e in data["edges"].values()}
    data["snapshots"] = {h: t for h, t in data["snapshots"].items() if h in referenced}
    path = lock_path(g)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


class _Concepts:
    def __init__(self, g: Garden):
        self.g = g
        self._cache: dict[str, tuple[str, str]] = {}

    def get(self, node_id: str) -> tuple[str, str]:
        if node_id not in self._cache:
            text = concept_text(self.g.nodes[node_id])
            self._cache[node_id] = (fingerprint(text), text)
        return self._cache[node_id]


@dataclass
class Pending:
    a: str
    b: str
    old: str
    new: str
    at: str
    old_text: str
    new_text: str


def pending(g: Garden, data: dict | None = None) -> list[Pending]:
    data = load_lock(g) if data is None else data
    concepts = _Concepts(g)
    out = []
    for a, b in edges(g):
        entry = data["edges"].get(edge_key(a, b))
        if entry is None:
            continue
        new, new_text = concepts.get(b)
        if entry.get("seen") != new:
            old = entry.get("seen", "")
            out.append(Pending(a, b, old, new, entry.get("at", ""), data["snapshots"].get(old, ""), new_text))
    return out


def safe_pending(g: Garden) -> list[Pending]:
    """Pending changes, or [] when there is no lock or it cannot be read (`check` reports that case)."""
    if not lock_path(g).is_file():
        return []
    try:
        return pending(g)
    except LockError:
        return []


def status(g: Garden) -> list[Finding]:
    if not lock_path(g).is_file():
        return [Finding("warning", "lock-missing", LOCK_REL, "concept.lock 없음 — `garden lock`으로 기록")]
    try:
        data = load_lock(g)
    except LockError as e:
        return [Finding("error", "lock-parse", LOCK_REL, str(e))]
    out = [Finding("review", "change-pending", p.a, pending_line(p.a, p.b)) for p in pending(g, data)]
    current = {edge_key(a, b) for a, b in edges(g)}
    for key in sorted(current - set(data["edges"])):
        out.append(Finding("warning", "edge-unlocked", key.split(" <- ")[0], f"기록 안 된 연결 {key} — `garden lock --missing`"))
    for key in sorted(set(data["edges"]) - current):
        out.append(Finding("warning", "edge-stale", key.split(" <- ")[0], f"없어진 연결 {key} — `garden lock --missing`로 정리"))
    for node_id, entry in sorted(data["nodes"].items()):
        node = g.nodes.get(node_id)
        before = entry.get("parent")
        if before == LEGACY_TOP and LEGACY_TOP not in g.nodes:
            before = TOP
        if node is not None and before != node.parent:
            out.append(Finding("warning", "parent-changed", node_id,
                               f"상위 폴더 변경: {before or 'SEED'} → {node.parent or 'SEED'} — 확인 후 `garden lock --missing`"))
    return out


def _node_entries(g: Garden) -> dict:
    return {nid: {"parent": n.parent} for nid, n in g.nodes.items()}


def lock_all(g: Garden, force: bool = False, today: str | None = None) -> tuple[bool, str]:
    try:
        old = load_lock(g)
    except LockError as e:
        if not force:
            return False, str(e)
        old = _empty()
    waiting = pending(g, old)
    if waiting and not force:
        return False, f"확인 대기 {len(waiting)}건이 있어 중단 — `garden ack` 후 다시 실행하거나 --force"
    concepts = _Concepts(g)
    data = _empty()
    data["nodes"] = _node_entries(g)
    for a, b in edges(g):
        h, text = concepts.get(b)
        prev = old["edges"].get(edge_key(a, b))
        at = prev["at"] if prev and prev.get("seen") == h else today_str(today)
        data["edges"][edge_key(a, b)] = {"seen": h, "at": at}
        data["snapshots"][h] = text
    save_lock(g, data)
    return True, f"연결 {len(data['edges'])}개, 카드 {len(data['nodes'])}장 기록"


def lock_missing(g: Garden, today: str | None = None) -> list[tuple[str, str]]:
    data = load_lock(g)
    concepts = _Concepts(g)
    data["nodes"] = _node_entries(g)
    current = edges(g)
    keys = {edge_key(a, b) for a, b in current}
    data["edges"] = {k: v for k, v in data["edges"].items() if k in keys}
    added = []
    for a, b in current:
        key = edge_key(a, b)
        if key not in data["edges"]:
            h, text = concepts.get(b)
            data["edges"][key] = {"seen": h, "at": today_str(today)}
            data["snapshots"][h] = text
            added.append((a, b))
    save_lock(g, data)
    return added


def ack(
    g: Garden,
    a: str,
    source: str | None = None,
    all_pending: bool = False,
    note: str | None = None,
    today: str | None = None,
) -> list[str]:
    node = g.nodes.get(a)
    if node is None:
        raise LockError(f"카드 없음: {a}")
    linked = [b for x, b in edges(g) if x == a]
    if source:
        if source not in linked:
            raise LockError(f"{a}의 needs에 {source}가 없음 (needs: {', '.join(linked) or '없음'})")
        targets = [source]
    elif all_pending:
        targets = linked
    else:
        raise LockError("--from <카드> 또는 --all 이 필요")
    data = load_lock(g)
    concepts = _Concepts(g)
    done = []
    for b in targets:
        key = edge_key(a, b)
        new, text = concepts.get(b)
        entry = data["edges"].get(key)
        old = entry.get("seen", "") if entry else ""
        if old == new:
            continue
        data["edges"][key] = {"seen": new, "at": today_str(today)}
        data["snapshots"][new] = text
        log(g, node, f"{b} 변경 확인", why=note or "영향 확인", evidence=f"concept {old[:4] or 'new'}→{new[:4]}", today=today)
        done.append(b)
    if done:
        save_lock(g, data)
    return done


def _diff(old: str, new: str, limit: int) -> list[str]:
    if not old:
        return ["(이전 기록 없음)"]
    old_lines, new_lines = old.splitlines(), new.splitlines()
    out = [f"- {x}" for x in old_lines if x not in new_lines] + [f"+ {x}" for x in new_lines if x not in old_lines]
    kept, used = [], 0
    for line in out:
        if used + len(line) > limit:
            kept.append("…")
            break
        kept.append(line)
        used += len(line)
    return kept


def alert_text(g: Garden, pendings: list[Pending], limit: int = DIFF_LIMIT) -> str:
    lines = [f"[garden] 확인 필요 {len(pendings)}건 — 'A ← B'는 A가 필요로 하는 B의 개념이 바뀌었다는 뜻"]
    for p in pendings:
        since = f"{p.at} 확인 이후" if p.at else "확인 기록 없음"
        lines.append(f"- {p.a} ← {p.b}  ({since})")
        lines += [f"    {d}" for d in _diff(p.old_text, p.new_text, limit)]
        b = g.nodes.get(p.b)
        if b is not None:
            lines += [f"    이력 {p.b}: {e.date} | {e.text}" for e in history_since(g, b, p.at or None)]
        lines.append(f"    처리: {p.a}에 영향이 있는지 확인한 뒤 `garden ack {p.a} --from {p.b}`")
    return "\n".join(lines)

