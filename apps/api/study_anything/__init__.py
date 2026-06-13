"""Study Anything API package."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import tomllib


def _resolve_version() -> str:
    pyproject = Path(__file__).resolve().parents[3] / "pyproject.toml"
    if pyproject.exists():
        return tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]
    try:
        return version("study-anything")
    except PackageNotFoundError:
        return "0.3.7-alpha"


__version__ = _resolve_version()
