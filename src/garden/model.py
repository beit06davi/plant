from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from garden.cards import CardFile, read_text

DETAILS = ("none", "concept", "full")
TOP = ""  # parent id of top-level cards (their parent is SEED); never a folder id
ALWAYS_IGNORE = [".git/**", ".garden/**"]
# keys written by garden 0.3; 0.4 ignores them
LEGACY_CONFIG_KEYS = ("garden_version", "read_scope", "zones", "roles", "unmapped_role", "shared_read")
DEFAULT_IGNORE = [".git/**", ".garden/**", ".claude/**", "node_modules/**", ".venv/**", "**/__pycache__/**"]


@dataclass
class Config:
    project: str = ""
    context: str = "concept"
    context_budget: int = 1500
    node_max_lines: int = 60
    seed_max_lines: int = 80
    ignore: list[str] = field(default_factory=lambda: list(DEFAULT_IGNORE))
    legacy: list[str] = field(default_factory=list)
    error: str | None = None


def load_config(root: Path) -> Config:
    cfg = Config(project=root.name)
    path = root / "garden.yaml"
    if not path.exists():
        return cfg
    try:
        data = yaml.safe_load(read_text(path)) or {}
    except yaml.YAMLError as e:
        cfg.error = f"garden.yaml YAML 오류: {str(e).splitlines()[0]}"
        return cfg
    if not isinstance(data, dict):
        cfg.error = "garden.yaml이 key: value 형식이 아님"
        return cfg
    cfg.project = str(data.get("project") or cfg.project)
    cfg.legacy = [k for k in LEGACY_CONFIG_KEYS if k in data]
    if data.get("context") in DETAILS:
        cfg.context = str(data["context"])
    elif "context" in data:
        cfg.error = f"garden.yaml `context`는 {' | '.join(DETAILS)} 중 하나: {data['context']}"
    cfg.context_budget = int(data.get("context_budget", cfg.context_budget))
    lines = data.get("card_max_lines") or {}
    cfg.node_max_lines = int(lines.get("node", cfg.node_max_lines))
    cfg.seed_max_lines = int(lines.get("seed", cfg.seed_max_lines))
    if isinstance(data.get("ignore"), list):
        cfg.ignore = [str(x) for x in data["ignore"]]
    cfg.ignore = list(dict.fromkeys(ALWAYS_IGNORE + cfg.ignore))
    return cfg


def find_root(start: Path) -> Path | None:
    start = Path(start).resolve()
    candidates = [start, *start.parents]
    for marker in ("garden.yaml", "SEED.md"):
        for d in candidates:
            if (d / marker).is_file():
                return d
    return None


def as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value if v is not None]
    return [str(value)]


@dataclass
class Node:
    """A folder card. Its id is the folder path relative to the project root."""

    id: str
    parent: str
    card: CardFile

    @property
    def meta(self) -> dict:
        return self.card.meta

    def text(self, key: str) -> str:
        value = self.meta.get(key)
        return "" if value is None else " ".join(str(value).split())

    @property
    def folder(self) -> str:
        return self.id

    @property
    def card_rel(self) -> str:
        return f"{self.id}/NODE.md"

    @property
    def depth(self) -> int:
        return self.id.count("/") + 1

    @property
    def purpose(self) -> str:
        return self.text("purpose")

    @property
    def why(self) -> str:
        return self.text("why")

    @property
    def provides(self) -> str:
        return self.text("provides")

    @property
    def serves(self) -> list[str]:
        return as_list(self.meta.get("serves"))

    @property
    def needs(self) -> list[str]:
        return [n.strip("/") for n in as_list(self.meta.get("needs"))]

    @property
    def priority(self) -> int | None:
        value = self.meta.get("priority")
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
        return None

    @property
    def body(self) -> str:
        return self.card.body.strip()
