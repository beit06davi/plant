from __future__ import annotations

from dataclasses import dataclass

from garden.model import DETAILS, Node
from garden.tree import Garden

KEEP = 0  # trim levels: higher numbers are dropped first when over budget
BODY_LIMIT = 600
RELATED_BODY_LIMIT = 300


@dataclass
class Line:
    key: str
    text: str
    trim: int = KEEP


def _goal_text(g: Garden, gid: str) -> str:
    goal = g.seed.goal(gid) if g.seed else None
    return f"{gid} {goal.text}" if goal else gid


def _clip(text: str, limit: int) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _parent_label(node: Node) -> str:
    return "SEED" if node.parent == "seed" else node.parent


def trace_text(g: Garden, node: Node) -> str:
    chain = list(reversed(g.ancestors(node.id))) + [node]
    lines = [f"{node.id} — {node.purpose}"]
    lines.append("목표: " + (" | ".join(_goal_text(g, s) for s in node.serves) or "-"))
    lines.append("SEED")
    for depth, n in enumerate(chain):
        pad = "   " * depth
        rank = f" (순위 {n.priority})" if n.priority is not None else ""
        lines.append(f"{pad}└─ {n.id} — {n.purpose}{rank}")
        if n.why:
            lines.append(f"{pad}   이유: {n.why}")
    lines.append("needs: " + (", ".join(node.needs) or "-"))
    lines.append("needed by: " + (", ".join(d.id for d in g.dependents(node.id)) or "-"))
    return "\n".join(lines)


def _related(g: Garden, other: Node, detail: str, provides: bool) -> list[str]:
    if detail == "none":
        return [other.id]
    head = f"{other.id} — {other.purpose}"
    if provides and other.provides:
        head += f" · 주는 것: {other.provides}"
    out = [head]
    if detail == "full":
        if other.why:
            out.append(f"    이유: {other.why}")
        if other.body:
            out.append("    " + _clip(other.body, RELATED_BODY_LIMIT).replace("\n", "\n    "))
    return out


def _lines(g: Garden, node: Node, detail: str, pending: list[str]) -> tuple[list[Line], list[Node]]:
    lines = [Line("header", f"[garden] {node.id} — {node.purpose or '(purpose 없음)'}")]
    lines.append(Line("goal", "goal: " + (" | ".join(_goal_text(g, s) for s in node.serves) or "-")))
    rank = g.goal_rank(node)
    if g.seed and rank:
        lines.append(Line("higher", "higher: " + " | ".join(f"{x.id} {x.text}" for x in g.seed.goals[:rank]), trim=3))
    ancestors = g.ancestors(node.id)
    lines.append(Line("lineage", ""))
    if node.why:
        lines.append(Line("why", f"why: {node.why}"))
    siblings = g.siblings(node)
    if len(siblings) > 1:
        order = " > ".join(f"{s.id}({s.priority})" if s.priority is not None else s.id for s in siblings)
        position = siblings.index(node) + 1
        lines.append(Line("order", f"order: {_parent_label(node)} 아래 {position}번째 — {order}", trim=2))
    for target in node.needs:
        other = g.nodes.get(target)
        if other is None:
            continue
        first, *rest = _related(g, other, detail, provides=True)
        lines.append(Line("needs", "needs: " + first))
        lines += [Line("needs", r) for r in rest]
    if node.provides:
        lines.append(Line("provides", f"provides: {node.provides}"))
    dependents = g.dependents(node.id)
    if dependents:
        if detail == "none":
            lines.append(Line("needed", "needed by: " + ", ".join(d.id for d in dependents), trim=4))
        else:
            for d in dependents:
                first, *rest = _related(g, d, detail, provides=False)
                lines.append(Line("needed", "needed by: " + first, trim=4))
                lines += [Line("needed", r, trim=4) for r in rest]
    if node.body:
        lines.append(Line("notes", "notes:\n  " + _clip(node.body, BODY_LIMIT).replace("\n", "\n  "), trim=1))
    lines += [Line("check", f"check: {p}") for p in pending]
    lines.append(Line("more", f"more: `garden context {node.id} --detail full` · 전체 구조 `garden map --why`", trim=5))
    return lines, ancestors


def _lineage_text(node: Node, ancestors: list[Node], keep: int) -> str:
    parts = ["SEED"]
    far_first = list(reversed(ancestors))
    cutoff = len(far_first) - keep
    for i, a in enumerate(far_first):
        parts.append(f"{a.id}({a.purpose})" if i >= cutoff else a.id)
    parts.append(node.id)
    return "lineage: " + " > ".join(parts)


def _render(lines: list[Line], lineage: str) -> str:
    return "\n".join(lineage if ln.key == "lineage" else ln.text for ln in lines)


def build(
    g: Garden,
    node: Node,
    detail: str | None = None,
    budget: int | None = None,
    pending: list[str] | None = None,
) -> tuple[str, bool]:
    detail = detail if detail in DETAILS else g.config.context
    if budget is None:
        budget = g.config.context_budget * (2 if detail == "full" else 1)
    lines, ancestors = _lines(g, node, detail, pending or [])
    keep = len(ancestors)
    text = _render(lines, _lineage_text(node, ancestors, keep))
    trimmed = False
    while len(text) > budget:
        trimmed = True
        if keep > 0:
            keep -= 1
        else:
            removable = [i for i, ln in enumerate(lines) if ln.trim]
            if not removable:
                break
            level = max(lines[i].trim for i in removable)
            idx = max(i for i in removable if lines[i].trim == level)
            del lines[idx]
        text = _render(lines, _lineage_text(node, ancestors, keep))
    if len(text) > budget:
        suffix = f"\n…(생략 — `garden context {node.id}`)"
        text = text[: max(0, budget - len(suffix))] + suffix
    return text, trimmed


def context(g: Garden, node: Node, detail: str | None = None, budget: int | None = None, pending: list[str] | None = None) -> str:
    return build(g, node, detail, budget, pending)[0]


def context_data(g: Garden, node: Node, detail: str | None = None, budget: int | None = None, pending: list[str] | None = None) -> dict:
    text, trimmed = build(g, node, detail, budget, pending)
    return {
        "node": node.id,
        "goal": g.top_goal(node),
        "detail": detail if detail in DETAILS else g.config.context,
        "text": text,
        "chars": len(text),
        "trimmed": trimmed,
    }
