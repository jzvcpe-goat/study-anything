#!/usr/bin/env python3
"""Compatibility wrapper for the installed ``delivery-clearance`` command."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from study_anything.cbb.personal.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
