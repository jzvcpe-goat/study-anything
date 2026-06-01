#!/usr/bin/env python3
"""Validate and install one explicitly selected local Study Anything plugin."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.core.plugin_registry import PluginRegistry  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Local plugin directory containing plugin.json")
    parser.add_argument(
        "--destination",
        type=Path,
        default=ROOT / "data" / "plugins",
        help="Writable local plugin directory scanned by the API",
    )
    parser.add_argument("--replace", action="store_true", help="Replace an installed plugin")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    status = PluginRegistry([]).install_local(
        args.source,
        args.destination,
        replace_existing=args.replace,
    )
    print(json.dumps(status.public_dict(), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (FileExistsError, OSError, ValueError) as exc:
        print(f"install-local-plugin: {exc}", file=sys.stderr)
        sys.exit(1)
