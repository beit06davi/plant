from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path

from garden.cards import read_text
from garden.model import Node
from garden.tree import Garden

ENTRY = re.compile(r"^\s*-\s+(\d{4}-\d{2}-\d{2})\s*\|\s*(.*?)\s*$")


@dataclass
class Entry:
    date: str
    text: str


def today_str(today: str | None = None) -> str:
    return today or dt.date.today().isoformat()


def history_path(g: Garden, node: Node) -> Path:
    return g.root / node.id / "HISTORY.md"


def read_history(g: Garden, node: Node) -> list[Entry]:
    path = history_path(g, node)
    if not path.is_file():
        return []
    return [Entry(m.group(1), m.group(2)) for line in read_text(path).split("\n") if (m := ENTRY.match(line))]


def history_since(g: Garden, node: Node, date: str | None) -> list[Entry]:
    return [e for e in read_history(g, node) if date is None or e.date >= date]


def _clean(value: str | None) -> str:
    return " ".join((value or "-").split()).replace("|", "/")


def log(
    g: Garden,
    node: Node,
    change: str,
    why: str | None = None,
    evidence: str | None = None,
    serves: list[str] | None = None,
    today: str | None = None,
) -> str:
    goals = ", ".join(serves if serves else node.serves) or "-"
    line = (
        f"- {today_str(today)} | 변경: {_clean(change)} | 이유: {_clean(why)} "
        f"| 목표: {goals} | 근거: {_clean(evidence)}"
    )
    path = history_path(g, node)
    if path.is_file():
        existing = read_text(path)
        prefix = "" if existing.endswith("\n") or not existing else "\n"
        with path.open("a", encoding="utf-8", newline="\n") as f:
            f.write(prefix + line + "\n")
    else:
        path.write_text(f"# HISTORY — {node.id}\n\n{line}\n", encoding="utf-8", newline="\n")
    return line


def resume_text(g: Garden, node_id: str | None = None, last: int = 5, today: str | None = None) -> str:
    from garden import lock
    from garden.validate import check

    nodes = [g.nodes[node_id]] if node_id else list(g.nodes.values())
    pending = lock.safe_pending(g)
    lines = [f"[resume] {g.config.project} — {today_str(today)}"]
    for n in nodes:
        lines.append("")
        lines.append(f"## {n.id} — {n.purpose}")
        meta = [f"목표 {', '.join(n.serves) or '-'}"]
        if n.priority is not None:
            meta.append(f"중요도 {n.priority}")
        if n.needs:
            meta.append(f"needs {', '.join(n.needs)}")
        lines.append("- " + " · ".join(meta))
        if n.why:
            lines.append(f"- 이유: {n.why}")
        entries = read_history(g, n)[-last:]
        if entries:
            lines.append("- 최근 이력:")
            lines += [f"  - {e.date} | {e.text}" for e in entries]
        for p in pending:
            if p.a == n.id:
                lines.append(f"- 확인 필요: {lock.pending_line(p.a, p.b)}")
    notes = [f for f in check(g).findings if f.level != "review" and (node_id is None or f.where == node_id)]
    if notes:
        lines += ["", "## check"] + [f"- [{f.level}] {f.where}: {f.msg}" for f in notes]
    return "\n".join(lines)
