#!/usr/bin/env python3
"""Verify one assembled 40-case observed benchmark audit set."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.cbb.benchmark.assembly import (  # noqa: E402
    ObservedAssemblyError,
    verify_observed_assembly,
)


DEFAULT_ASSEMBLY = (
    ROOT / ".delivery-clearance" / "benchmarks" / "pilot-v0.1-observed-assembly-v1"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--assembly", default=str(DEFAULT_ASSEMBLY))
    args = parser.parse_args()
    if not args.check:
        raise SystemExit("Use --check.")
    try:
        report = verify_observed_assembly(Path(args.assembly))
    except (ObservedAssemblyError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"observed assembly verification failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
