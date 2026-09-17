from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from garden.cards import SeedFile, load_card, load_seed
from garden.model import Config, Node, load_config


@dataclass
class Issue:
    code: str
    path: str
    msg: str


def _segment_regex(segment: str) -> str:
    out, i = [], 0
    while i < len(segment):
        ch = segment[i]
        if ch == "*":
            out.append("[^/]*")
        elif ch == "?":
            out.append("[^/]")
        elif ch == "[":
            end = segment.find("]", i + 1)
            if end == -1:
                out.append(re.escape(ch))
            else:
                body = segment[i + 1 : end]
                if body.startswith("!"):
                    body = "^" + body[1:]
                out.append(f"[{body}]")
                i = end
        else:
            out.append(re.escape(ch))
        i += 1
    return "".join(out)


def _glob_regex(pattern: str) -> re.Pattern:
    parts = pattern.split("/")
    rx = ""
    for i, part in enumerate(parts):
        last = i == len(parts) - 1
        if part == "**":
            rx += "(?:[^/]+(?:/[^/]+)*)?" if last else "(?:[^/]+/)*"
        else:
            rx += _segment_regex(part) + ("" if last else "/")
    return re.compile(rx + r"\Z", re.IGNORECASE)


def _full_match(rel: str, pattern: str) -> bool:
    """PurePosixPath.full_match (3.13+) with a regex fallback for older Pythons."""
    path = PurePosixPath(rel or ".")
    if hasattr(path, "full_match"):
        return path.full_match(pattern, case_sensitive=False)
    return bool(_glob_regex(pattern).match(str(path)))


def glob_match(rel: str, pattern: str) -> bool:
    """Match a project-relative path; a plain or `/**` pattern also matches the folder itself."""
    pattern = pattern.strip().replace("\\", "/").rstrip("/")
    if not pattern:
        return False
    candidates = [pattern]
    if not any(ch in pattern for ch in "*?["):
        candidates.append(pattern + "/**")
    elif pattern.endswith("/**"):
        candidates.append(pattern[:-3])
    for c in candidates:
        try:
            if _full_match(rel, c):
                return True
        except (ValueError, re.error):
            continue
    return False


class Garden:
    def __init__(self, root: Path, config: Config, seed: SeedFile | None):
        self.root = Path(root).resolve()
        self.config = config
        self.seed = seed
        self.nodes: dict[str, Node] = {}
        self._by_key: dict[str, Node] = {}
        self.issues: list[Issue] = []
        self._root_key = os.path.normcase(os.path.abspath(self.root))

    @classmethod
    def load(cls, root: Path) -> Garden:
        root = Path(root).resolve()
        seed_path = root / "SEED.md"
        g = cls(root, load_config(root), load_seed(seed_path) if seed_path.is_file() else None)
        g._scan()
        return g

    def ignored(self, rel: str) -> bool:
        return any(glob_match(rel, p) for p in self.config.ignore)

    def _scan(self) -> None:
        folders: list[str] = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            rel_dir = os.path.relpath(dirpath, self.root).replace("\\", "/")
            rel_dir = "" if rel_dir == "." else rel_dir
            dirnames[:] = sorted(d for d in dirnames if not self.ignored(f"{rel_dir}/{d}" if rel_dir else d))
            if "NODE.md" in filenames:
                folders.append(rel_dir)
        folders.sort(key=lambda f: (f.count("/"), f))
        for folder in folders:
            if folder == "":
                self.issues.append(Issue("root-card", "NODE.md", "프로젝트 최상위에는 NODE.md 대신 SEED.md를 둔다"))
                continue
            card = load_card(self.root / folder / "NODE.md")
            if card.error:
                self.issues.append(Issue("card-parse", f"{folder}/NODE.md", card.error))
                continue
            parent = self._nearest(folder)
            node = Node(id=folder, parent=parent.id if parent else "seed", card=card)
            self.nodes[folder] = node
            self._by_key[folder.lower()] = node

    def _nearest(self, folder: str) -> Node | None:
        p = PurePosixPath(folder)
        for parent in p.parents:
            key = "" if str(parent) == "." else str(parent)
            node = self._by_key.get(key.lower())
            if node is not None:
                return node
        return None

    def rel(self, path) -> str | None:
        s = str(path)
        if not os.path.isabs(s):
            s = os.path.join(self.root, s.replace("/", os.sep))
        try:
            r = os.path.relpath(os.path.normcase(os.path.abspath(s)), self._root_key)
        except ValueError:
            return None
        r = r.replace("\\", "/")
        if r == ".":
            return ""
        if r == ".." or r.startswith("../"):
            return None
        return self._restore_case(r)

    def _restore_case(self, lowered: str) -> str:
        parts = lowered.split("/")
        out: list[str] = []
        cur = self.root
        for i, part in enumerate(parts):
            match = part
            try:
                for entry in os.scandir(cur):
                    if entry.name.lower() == part.lower():
                        match = entry.name
                        break
            except OSError:
                out.extend(parts[i:])
                break
            out.append(match)
            cur = cur / match
        return "/".join(out)

    def node_for(self, path) -> Node | None:
        rel = self.rel(path)
        return None if rel is None else self.owner(rel)

    def owner(self, rel: str) -> Node | None:
        """Nearest card at or above an already-normalized project-relative path."""
        if not rel or self.ignored(rel):
            return None
        node = self._by_key.get(rel.lower())
        if node is not None:
            return node
        return self._nearest(rel)

    def get(self, ref: str) -> Node | None:
        ref = ref.replace("\\", "/").strip("/")
        return self.nodes.get(ref) or self.node_for(ref)

    def ancestors(self, node_id: str) -> list[Node]:
        out: list[Node] = []
        node = self.nodes.get(node_id)
        while node is not None and node.parent != "seed":
            node = self.nodes.get(node.parent)
            if node is None:
                break
            out.append(node)
        return out

    def children(self, node_id: str) -> list[Node]:
        return sorted((n for n in self.nodes.values() if n.parent == node_id), key=sibling_key)

    def siblings(self, node: Node) -> list[Node]:
        return self.children(node.parent)

    def dependents(self, node_id: str) -> list[Node]:
        return [n for n in self.nodes.values() if node_id in n.needs]

    def goal_rank(self, node: Node) -> int | None:
        if self.seed is None:
            return None
        ranks = [r for r in (self.seed.rank(g) for g in node.serves) if r is not None]
        return min(ranks) if ranks else None

    def top_goal(self, node: Node) -> str | None:
        rank = self.goal_rank(node)
        return None if rank is None else self.seed.goals[rank].id


def sibling_key(node: Node) -> tuple:
    return (node.priority is None, node.priority or 0, node.id)
