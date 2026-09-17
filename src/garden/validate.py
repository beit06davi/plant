from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass

from garden.tree import Garden

PURPOSE_MAX = 120


@dataclass
class Finding:
    level: str
    code: str
    where: str
    msg: str


@dataclass
class Report:
    findings: list[Finding]

    def of(self, level: str) -> list[Finding]:
        return [f for f in self.findings if f.level == level]

    @property
    def exit_code(self) -> int:
        if self.of("error"):
            return 2
        if self.of("warning") or self.of("review"):
            return 1
        return 0

    def to_json(self) -> str:
        data = {level + "s": [asdict(f) for f in self.of(level)] for level in ("error", "warning", "review")}
        data["exit_code"] = self.exit_code
        return json.dumps(data, ensure_ascii=False, indent=2)


def check(g: Garden, propagation: bool | None = None) -> Report:
    """propagation=None: also report pending changes whenever .garden/concept.lock exists."""
    if propagation is None:
        propagation = (g.root / ".garden" / "concept.lock").is_file()
    out: list[Finding] = []

    def add(level: str, code: str, where: str, msg: str) -> None:
        out.append(Finding(level, code, where, msg))

    if g.config.error:
        add("error", "config", "garden.yaml", g.config.error)
    if g.seed is None:
        add("error", "seed-missing", "SEED.md", "SEED.md가 없음")
    else:
        if g.seed.error:
            add("error", "seed-parse", "SEED.md", g.seed.error)
        if not g.seed.goals:
            add("error", "seed-no-goals", "SEED.md", "목표(`- G1: …`)가 하나도 없음")
        if g.seed.line_count > g.config.seed_max_lines:
            add("warning", "seed-long", "SEED.md", f"{g.seed.line_count}줄 (기준 {g.config.seed_max_lines}줄)")

    for issue in g.issues:
        add("error", issue.code, issue.path, issue.msg)

    for n in g.nodes.values():
        where = n.id
        if not n.purpose:
            add("error", "purpose-missing", where, "purpose가 없음")
        elif len(n.purpose) > PURPOSE_MAX:
            add("warning", "purpose-long", where, f"purpose는 한 문장으로 ({len(n.purpose)}자)")
        if not n.why:
            add("warning", "why-missing", where, "why(이 폴더를 이렇게 나눈 이유)가 없음")
        if not n.serves:
            add("error", "serves-missing", where, "serves(섬기는 목표)가 없음")
        elif g.seed is not None:
            bad = [s for s in n.serves if g.seed.rank(s) is None]
            if bad:
                add("error", "serves-invalid", where, f"SEED에 없는 목표: {', '.join(bad)}")
        if "priority" in n.meta and n.priority is None:
            add("error", "priority-invalid", where, f"priority는 1 이상의 정수: {n.meta['priority']}")
        elif n.priority is not None and n.priority < 1:
            add("error", "priority-invalid", where, f"priority는 1 이상의 정수: {n.priority}")
        for target in n.needs:
            if target == n.id:
                add("error", "needs-self", where, "자기 자신을 needs에 적음")
            elif target not in g.nodes:
                add("error", "needs-missing", where, f"needs 대상 카드가 없음: {target}")
        if n.card.line_count > g.config.node_max_lines:
            add("warning", "card-long", where, f"{n.card.line_count}줄 (기준 {g.config.node_max_lines}줄)")

    for parent in ["seed", *g.nodes]:
        counts = Counter(c.priority for c in g.children(parent) if c.priority is not None)
        dup = sorted(p for p, k in counts.items() if k > 1)
        if dup:
            add("warning", "priority-duplicate", parent, f"하위 폴더들의 priority가 겹침: {', '.join(map(str, dup))}")

    for cycle in needs_cycles(g):
        add("error", "needs-cycle", cycle[0], "needs 순환: " + " → ".join(cycle))

    if propagation:
        from garden.lock import status

        out.extend(status(g))
    return Report(out)


def needs_cycles(g: Garden) -> list[list[str]]:
    cycles: list[list[str]] = []
    seen: set[frozenset] = set()

    def walk(start: str, cur: str, path: list[str]) -> None:
        for nxt in g.nodes[cur].needs:
            if nxt == start and len(path) > 1:
                key = frozenset(path)
                if key not in seen:
                    seen.add(key)
                    cycles.append(path + [start])
            elif nxt in g.nodes and nxt not in path and nxt != cur:
                walk(start, nxt, path + [nxt])

    for nid in g.nodes:
        walk(nid, nid, [nid])
    return cycles
