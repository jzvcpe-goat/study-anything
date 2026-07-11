#!/usr/bin/env python3
"""Generate deterministic CBB v1 Agentic evolution fixtures."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.cbb.agentic.fixtures import fixture_outputs  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    outputs = fixture_outputs(ROOT)
    stale: list[str] = []
    for path, expected in sorted(outputs.items()):
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != expected:
                stale.append(path.relative_to(ROOT).as_posix())
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(expected, encoding="utf-8")
    if stale:
        raise SystemExit(
            "stale CBB v1 Agentic evolution fixtures: " + ", ".join(stale)
        )
    action = "checked" if args.check else "wrote"
    print(f"ok    {action} {len(outputs)} CBB v1 Agentic evolution fixtures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
