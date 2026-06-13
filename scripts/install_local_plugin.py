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
    parser.add_argument(
        "--quarantine-destination",
        type=Path,
        default=ROOT / "data" / "plugins-quarantine",
        help="Writable quarantine directory used before explicit approval",
    )
    parser.add_argument("--replace", action="store_true", help="Replace an installed plugin")
    parser.add_argument(
        "--approve-install",
        action="store_true",
        help="Copy into the installed plugin directory instead of the quarantine directory",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    registry = PluginRegistry([])
    if args.approve_install:
        preview = registry.preview_local(args.source)
        if preview.manifest is None:
            raise SystemExit(f"Cannot install invalid plugin: {preview.message}")
        if preview.trust is not None and preview.trust.install_recommendation == "do_not_install":
            raise SystemExit("Plugin trust policy blocks installation.")
        quarantined_source = args.quarantine_destination / preview.manifest.plugin_id
        if not quarantined_source.exists():
            raise SystemExit(
                "Plugin must be quarantined before approved installation. "
                "Run without --approve-install first."
            )
        status = registry.install_local(
            quarantined_source,
            args.destination,
            replace_existing=args.replace,
        )
        lifecycle_status = "installed"
        destination = args.destination
    else:
        status = registry.quarantine_local(
            args.source,
            args.quarantine_destination,
            replace_existing=True,
        )
        lifecycle_status = "quarantined"
        destination = args.quarantine_destination
    print(
        json.dumps(
            {
                **status.public_dict(),
                "schema_version": "plugin-install-result-v1",
                "lifecycle_status": lifecycle_status,
                "installed": lifecycle_status == "installed",
                "quarantined": lifecycle_status == "quarantined",
                "destination_dir": str(destination),
                "install_dir": str(args.destination),
                "quarantine_dir": str(args.quarantine_destination),
                "entrypoints_executed": False,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except (FileExistsError, OSError, ValueError) as exc:
        print(f"install-local-plugin: {exc}", file=sys.stderr)
        sys.exit(1)
