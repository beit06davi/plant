from __future__ import annotations

import os

from garden import lock
from garden.cards import find_section, items
from garden.model import TOP, Node
from garden.tree import Garden, sibling_key


def _pending_by_node(g: Garden) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for p in lock.safe_pending(g):
        out.setdefault(p.a, []).append(p.b)
    return out


def _goal_header(g: Garden) -> str:
    if g.seed is None or not g.seed.goals:
        return f"{g.config.project}   (SEED 목표 없음)"
    return f"{g.config.project}   " + " > ".join(f"{x.id} {x.text}" for x in g.seed.goals)


def _unlinked(g: Garden, node: Node) -> bool:
    return not node.serves or (g.seed is not None and g.goal_rank(node) is None)


def _uncarded_top_folders(g: Garden) -> list[str]:
    carded_tops = {n.id.split("/", 1)[0] for n in g.nodes.values()}
    out = []
    for entry in sorted(os.scandir(g.root), key=lambda e: e.name):
        if entry.is_dir() and not entry.name.startswith(".") and not g.ignored(entry.name):
            if entry.name not in carded_tops:
                out.append(entry.name)
    return out


def map_tree(g: Garden, show_why: bool = False) -> str:
    pending = _pending_by_node(g)
    rows: list[tuple[str, Node, str]] = []

    def walk(parent: str, prefix: str) -> None:
        children = g.children(parent)
        for i, n in enumerate(children):
            last = i == len(children) - 1
            label = n.id if parent == TOP else n.id[len(parent) + 1 :]
            child_prefix = prefix + ("   " if last else "│  ")
            rows.append((prefix + ("└─ " if last else "├─ ") + label + "/", n, child_prefix))
            walk(n.id, child_prefix)

    walk(TOP, "")
    width = max((len(r[0]) for r in rows), default=0) + 2
    lines = [_goal_header(g)]
    for label, n, child_prefix in rows:
        goal = g.top_goal(n) or "-"
        rank = f"#{n.priority}" if n.priority is not None else ""
        line = label.ljust(width) + f"{goal:<4}{rank:<4}{n.purpose}"
        extras = []
        if n.needs:
            extras.append("← " + ", ".join(n.needs))
        if n.id in pending:
            extras.append(f"⚠ 확인 필요(← {', '.join(pending[n.id])})")
        if _unlinked(g, n):
            extras.append("⚠ 목표 연결 없음")
        if extras:
            line += "   " + "   ".join(extras)
        lines.append(line)
        if show_why and n.why:
            lines.append(f"{child_prefix}  ↳ 이유: {n.why}")
    loose = _uncarded_top_folders(g)
    if loose:
        lines += ["", "카드 없는 최상위 폴더: " + ", ".join(f"{f}/" for f in loose)]
    if show_why and g.seed is not None:
        principles = items(find_section(g.seed.sections, "구조 원칙"))
        if principles:
            lines += ["", "구조 원칙 (SEED)"] + [f"- {p}" for p in principles]
    return "\n".join(lines)


def _order_key(g: Garden, node: Node) -> tuple:
    rank = g.goal_rank(node)
    return (99 if rank is None else rank, node.depth, *sibling_key(node))


def order_levels(g: Garden) -> tuple[list[list[str]], list[str], list[str]]:
    """Kahn levels over needs edges. Returns (levels, nodes without needs links, nodes stuck in cycles)."""
    linked = {x for a, b in lock.edges(g) for x in (a, b)}
    remaining = {nid for nid in g.nodes if nid in linked}
    done: set[str] = set()
    levels: list[list[str]] = []
    while remaining:
        ready = [nid for nid in remaining if all(t in done or t not in remaining for t in g.nodes[nid].needs if t in g.nodes)]
        if not ready:
            break
        ready.sort(key=lambda nid: _order_key(g, g.nodes[nid]))
        levels.append(ready)
        done.update(ready)
        remaining -= set(ready)
    unlinked = sorted(nid for nid in g.nodes if nid not in linked)
    return levels, unlinked, sorted(remaining)


def map_order(g: Garden) -> str:
    levels, unlinked, stuck = order_levels(g)
    lines = ["작업 순서 (needs 기준 — 같은 단계는 서로 기다리지 않음)"]
    for i, level in enumerate(levels, 1):
        lines.append(f"{i}. " + ", ".join(f"{nid}({g.top_goal(g.nodes[nid]) or '-'})" for nid in level))
    if not levels:
        lines.append("(needs로 연결된 폴더 없음)")
    if stuck:
        lines.append("⚠ 순환 때문에 순서를 정할 수 없음: " + ", ".join(stuck))
    if unlinked:
        lines += ["", "순서 연결 없음: " + ", ".join(unlinked)]
    return "\n".join(lines)


def _label(text: str) -> str:
    return text.replace('"', "#quot;")


def map_mermaid(g: Garden) -> str:
    """Graph ids are sequence numbers so non-ASCII folder names never collide."""
    ids = {nid: f"n{i}" for i, nid in enumerate(sorted(g.nodes), 1)}
    ids[TOP] = "seed"
    lines = ["flowchart TD", f'  seed(["SEED · {_label(g.config.project)}"])']
    for nid in sorted(g.nodes):
        n = g.nodes[nid]
        goal = g.top_goal(n) or "-"
        label = _label(f"{nid}<br/>{goal} · {n.purpose}")
        lines.append(f'  {ids[nid]}["{label}"]')
    for nid in sorted(g.nodes):
        lines.append(f"  {ids[g.nodes[nid].parent]} --> {ids[nid]}")
    for a, b in lock.edges(g):
        lines.append(f"  {ids[b]} -. 먼저 .-> {ids[a]}")
    return "\n".join(lines)
