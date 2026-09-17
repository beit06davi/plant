"""Entry point for the plugin wrapper: runs the bundled garden package without installing it."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from garden.cli import main  # noqa: E402

raise SystemExit(main())
