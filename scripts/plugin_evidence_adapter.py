#!/usr/bin/env python3
"""Repository wrapper for the Plugin Evidence Adapter CLI."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from study_anything.cbb.plugin_evidence.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
