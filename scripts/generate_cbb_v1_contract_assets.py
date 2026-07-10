#!/usr/bin/env python3
"""Generate or verify canonical CBB Protocol v1 schemas and fixtures."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.cbb.protocol.canonical import schema_outputs  # noqa: E402
from study_anything.cbb.protocol.fixtures import fixture_outputs  # noqa: E402


def outputs() -> dict[Path, str]:
    return {**schema_outputs(ROOT), **fixture_outputs(ROOT)}


def write_outputs() -> None:
    for path, content in outputs().items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")


def check_outputs() -> None:
    missing: list[str] = []
    stale: list[str] = []
    for path, expected in outputs().items():
        if not path.is_file():
            missing.append(path.relative_to(ROOT).as_posix())
            continue
        if path.read_text(encoding="utf-8") != expected:
            stale.append(path.relative_to(ROOT).as_posix())
    if missing or stale:
        raise SystemExit(f"CBB v1 assets are not current; missing={missing}, stale={stale}")
    print(f"ok    {len(outputs())} CBB Protocol v1 schema and fixture assets are current")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.write:
        write_outputs()
    else:
        check_outputs()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

