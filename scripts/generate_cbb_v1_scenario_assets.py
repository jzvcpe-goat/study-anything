#!/usr/bin/env python3
"""Generate or verify deterministic CBB Protocol v1 scenario fixtures."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from study_anything.cbb.scenarios.fixtures import fixture_outputs  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.check == args.write:
        raise SystemExit("Choose exactly one of --check or --write.")

    outputs = fixture_outputs(ROOT)
    stale: list[str] = []
    for path, expected in outputs.items():
        if args.write:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(expected, encoding="utf-8")
        elif not path.is_file() or path.read_text(encoding="utf-8") != expected:
            stale.append(path.relative_to(ROOT).as_posix())
    if stale:
        raise SystemExit(f"CBB v1 scenario fixtures are stale: {stale}")
    print(f"ok    {len(outputs)} CBB Protocol v1 scenario fixtures are current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
