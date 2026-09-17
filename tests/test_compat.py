import io
import tokenize
from pathlib import Path, PurePosixPath

import pytest

from garden.tree import _glob_regex

SRC = Path(__file__).resolve().parents[1] / "src" / "garden"

CASES = [
    ("backend/booking/service.py", "backend/**"),
    ("backend", "backend/**"),
    ("backend/tests/booking/x.py", "backend/tests/booking/**"),
    ("a/b/c.md", "**/c.md"),
    ("c.md", "**/c.md"),
    ("x/__pycache__/y.pyc", "**/__pycache__/**"),
    ("contracts/ep01.md", "contracts/ep*.md"),
    ("contracts/sub/ep01.md", "contracts/ep*.md"),
    ("a/b", "a/?"),
    ("a/bc", "a/?"),
    ("A/B.md", "a/b.md"),
    ("data/x1.csv", "data/x[0-9].csv"),
    ("data/xa.csv", "data/x[!0-9].csv"),
    (".git/config", ".git/**"),
    ("design/style_refs/calm/README.md", "design/style_refs/calm/**"),
]


@pytest.mark.parametrize("rel,pattern", CASES)
def test_fallback_glob_matches_native(rel, pattern):
    native = PurePosixPath(rel).full_match(pattern, case_sensitive=False)
    assert bool(_glob_regex(pattern).match(rel)) == native


def _nested_same_quote(source: str) -> list[int]:
    """Lines where an f-string contains a string using its own quote char (a syntax error before Python 3.12)."""
    bad, stack = [], []
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        name = tokenize.tok_name[tok.type]
        if name in ("FSTRING_START", "STRING"):
            text = tok.string.lstrip("rRbBfFuU")
            quote = text[:3] if text[:3] in ('"""', "'''") else text[:1]
            if any(q == quote for q in stack):
                bad.append(tok.start[0])
            if name == "FSTRING_START":
                stack.append(quote)
        elif name == "FSTRING_END" and stack:
            stack.pop()
    return bad


def test_checker_detects_nested_quotes():
    assert _nested_same_quote('x = f"{a or "-"}"\n') == [1]
    assert _nested_same_quote("x = f\"{a or '-'}\"\n") == []


@pytest.mark.parametrize("path", sorted(SRC.rglob("*.py")), ids=lambda p: p.name)
def test_sources_parse_on_python_311(path):
    assert _nested_same_quote(path.read_text(encoding="utf-8")) == []
