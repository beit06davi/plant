import io
import sys
import tokenize
from pathlib import Path, PurePosixPath

import pytest

from garden.tree import _glob_regex

SRC = Path(__file__).resolve().parents[1] / "src" / "garden"

# (path, pattern, expected) — expected is what PurePosixPath.full_match (Python 3.13+) returns
CASES = [
    ("backend/booking/service.py", "backend/**", True),
    ("backend", "backend/**", False),
    ("backend/tests/booking/x.py", "backend/tests/booking/**", True),
    ("a/b/c.md", "**/c.md", True),
    ("c.md", "**/c.md", True),
    ("x/__pycache__/y.pyc", "**/__pycache__/**", True),
    ("docs/ch01.md", "docs/ch*.md", True),
    ("docs/sub/ch01.md", "docs/ch*.md", False),
    ("a/b", "a/?", True),
    ("a/bc", "a/?", False),
    ("A/B.md", "a/b.md", True),
    ("data/x1.csv", "data/x[0-9].csv", True),
    ("data/xa.csv", "data/x[!0-9].csv", True),
    (".git/config", ".git/**", True),
    ("assets/icons/app/README.md", "assets/icons/app/**", True),
]
HAS_FULL_MATCH = hasattr(PurePosixPath, "full_match")


@pytest.mark.parametrize("rel,pattern,expected", CASES)
def test_fallback_glob(rel, pattern, expected):
    assert bool(_glob_regex(pattern).match(rel)) == expected


@pytest.mark.skipif(not HAS_FULL_MATCH, reason="PurePosixPath.full_match needs Python 3.13+")
@pytest.mark.parametrize("rel,pattern,expected", CASES)
def test_expected_values_match_native(rel, pattern, expected):
    assert PurePosixPath(rel).full_match(pattern, case_sensitive=False) == expected


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


# f-strings are tokenized piece by piece only on Python 3.12+; on older versions importing the sources is the check
NEEDS_312 = pytest.mark.skipif(sys.version_info < (3, 12), reason="f-string tokens need Python 3.12+")


@NEEDS_312
def test_checker_detects_nested_quotes():
    assert _nested_same_quote('x = f"{a or "-"}"\n') == [1]
    assert _nested_same_quote("x = f\"{a or '-'}\"\n") == []


@NEEDS_312
@pytest.mark.parametrize("path", sorted(SRC.rglob("*.py")), ids=lambda p: p.name)
def test_sources_parse_on_python_311(path):
    assert _nested_same_quote(path.read_text(encoding="utf-8")) == []
