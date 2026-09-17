from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
ITEM = re.compile(r"^\s*[-*]\s+(.*\S)\s*$")
GOAL = re.compile(r"^\s*[-*]\s+(G\d+)\s*:\s*(.+?)\s*$")
MEASURE = re.compile(r"\s+(?:—|--?)\s*측정\s*기준\s*:\s*")


def read_text(path: Path) -> str:
    return path.read_bytes().decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")


def split_frontmatter(text: str) -> tuple[dict, str, str | None]:
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, text, "frontmatter 없음"
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            raw = "\n".join(lines[1:i])
            body = "\n".join(lines[i + 1 :])
            try:
                meta = yaml.safe_load(raw)
            except yaml.YAMLError as e:
                return {}, body, f"frontmatter YAML 오류: {str(e).splitlines()[0]}"
            if meta is None:
                meta = {}
            if not isinstance(meta, dict):
                return {}, body, "frontmatter가 key: value 형식이 아님"
            return meta, body, None
    return {}, text, "frontmatter를 닫는 --- 없음"


def parse_sections(body: str) -> dict[str, str]:
    """Level-2 headings only; deeper headings stay inside their section."""
    sections: dict[str, str] = {}
    current: str | None = None
    buf: list[str] = []
    for line in body.split("\n"):
        m = HEADING.match(line)
        if m and len(m.group(1)) <= 2:
            if current is not None:
                sections[current] = "\n".join(buf).strip()
            current = m.group(2) if len(m.group(1)) == 2 else None
            buf = []
        elif current is not None:
            buf.append(line)
    if current is not None:
        sections[current] = "\n".join(buf).strip()
    return sections


def find_section(sections: dict[str, str], name: str) -> str:
    if name in sections:
        return sections[name]
    for key, value in sections.items():
        if key.startswith(name + " ") or key.startswith(name + "("):
            return value
    return ""


def items(text: str) -> list[str]:
    return [m.group(1) for line in text.split("\n") if (m := ITEM.match(line))]


@dataclass
class CardFile:
    path: Path
    meta: dict
    body: str
    sections: dict[str, str]
    line_count: int
    error: str | None


def load_card(path: Path) -> CardFile:
    text = read_text(path)
    meta, body, error = split_frontmatter(text)
    return CardFile(path, meta, body, parse_sections(body), len(text.rstrip("\n").split("\n")), error)


@dataclass
class Goal:
    id: str
    text: str
    measure: str = ""


@dataclass
class SeedFile:
    path: Path
    meta: dict
    goals: list[Goal]
    sections: dict[str, str]
    line_count: int
    error: str | None

    def rank(self, goal_id: str) -> int | None:
        for i, g in enumerate(self.goals):
            if g.id == goal_id:
                return i
        return None

    def goal(self, goal_id: str) -> Goal | None:
        i = self.rank(goal_id)
        return None if i is None else self.goals[i]


def load_seed(path: Path) -> SeedFile:
    text = read_text(path)
    meta, body, error = split_frontmatter(text)
    if error == "frontmatter 없음":
        error = None
    goals = []
    for line in body.split("\n"):
        m = GOAL.match(line)
        if m:
            parts = MEASURE.split(m.group(2), maxsplit=1)
            goals.append(Goal(m.group(1), parts[0].strip(), parts[1].strip() if len(parts) > 1 else ""))
    return SeedFile(path, meta, goals, parse_sections(body), len(text.rstrip("\n").split("\n")), error)
