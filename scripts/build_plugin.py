"""Render the plugin's skills/ from src/garden/templates in plugin mode.

Usage: python scripts/build_plugin.py [--check]
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from garden.initcmd import SKILLS, render  # noqa: E402


def outputs() -> dict[Path, str]:
    return {ROOT / "skills" / s / "SKILL.md": render(f"skills/{s}/SKILL.md", plugin=True) for s in SKILLS}


def main(check: bool = False) -> int:
    stale = []
    for path, text in outputs().items():
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == text:
            continue
        stale.append(path.relative_to(ROOT).as_posix())
        if not check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
    extra = sorted(p.parent.name for p in (ROOT / "skills").glob("*/SKILL.md") if p.parent.name not in SKILLS)
    if extra:
        stale += [f"skills/{name} (not in SKILLS)" for name in extra]
    if check and stale:
        print("stale plugin files: " + ", ".join(stale))
        return 1
    print("up to date" if not stale else "written: " + ", ".join(stale))
    return 1 if extra else 0


if __name__ == "__main__":
    raise SystemExit(main("--check" in sys.argv))
