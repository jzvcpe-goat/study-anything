"""Study Anything API package."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import re

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 and older fallback
    tomllib = None  # type: ignore[assignment]


def _resolve_version() -> str:
    pyproject = Path(__file__).resolve().parents[3] / "pyproject.toml"
    if pyproject.exists():
        text = pyproject.read_text(encoding="utf-8")
        if tomllib is not None:
            return str(tomllib.loads(text)["project"]["version"])
        match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', text)
        if match:
            return match.group(1)
    try:
        return version("study-anything")
    except PackageNotFoundError:
        return "0.3.31-alpha"


__version__ = _resolve_version()
