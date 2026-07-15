#!/usr/bin/env python3
"""Verify metric recomputation and paired statistical primitives."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.cbb.benchmark.verification import (  # noqa: E402
    metrics_report,
    write_or_check_report,
)


REPORT = ROOT / "platform" / "generated" / "delivery-clearance-benchmark-metrics.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.check == args.write:
        raise SystemExit("Choose exactly one of --check or --write.")
    report = write_or_check_report(path=REPORT, build=metrics_report, write=args.write)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
