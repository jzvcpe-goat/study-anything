"""Study Anything API package."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import tomllib


def _resolve_version() -> str:
    try:
        return version("study-anything")
    except PackageNotFoundError:
        pyproject = Path(__file__).resolve().parents[3] / "pyproject.toml"
        if pyproject.exists():
            return tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]
        return "0.2.10-alpha"


__version__ = _resolve_version()
