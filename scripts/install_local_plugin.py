#!/usr/bin/env python3
"""Validate and install one explicitly selected local Study Anything plugin."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
API_PATH = ROOT / "apps" / "api"


LOCAL_ABSOLUTE_PATH_RE = re.compile(
    r"(?<![\w<])(?:/Users|/private/tmp|/tmp|/private/var/folders|/var/folders)"
    r"/[^\s\"'<>]+"
)


class PluginInstallCliError(Exception):
    """Actionable local plugin installation failure."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        next_steps: list[str],
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.next_steps = next_steps
        self.details = details or {}


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


def _path_for_report(path: Path, *, placeholder: str = "<local-path>") -> str:
    expanded = path.expanduser()
    if not expanded.is_absolute():
        return str(expanded)
    try:
        return str(expanded.resolve(strict=False).relative_to(ROOT))
    except ValueError:
        return placeholder


def _redact_report_value(value: Any) -> Any:
    if isinstance(value, str):
        return LOCAL_ABSOLUTE_PATH_RE.sub("<local-path>", value)
    if isinstance(value, list):
        return [_redact_report_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _redact_report_value(item) for key, item in value.items()}
    return value


def _validate_source_shape(source: Path) -> None:
    if not source.exists():
        raise PluginInstallCliError(
            "source_missing",
            "Local plugin source directory does not exist.",
            next_steps=[
                "Pass the path to a local directory that contains plugin.json.",
                "Try the bundled example with: python3 scripts/install_local_plugin.py plugins/example-exporter",
            ],
            details={"source": _path_for_report(source, placeholder="<local-plugin-source>")},
        )
    if not source.is_dir():
        raise PluginInstallCliError(
            "source_not_directory",
            "Local plugin source must be a directory.",
            next_steps=[
                "Pass the plugin directory, not plugin.json itself.",
                "Expected layout: <plugin-dir>/plugin.json and optional plugin files.",
            ],
            details={"source": _path_for_report(source, placeholder="<local-plugin-source>")},
        )
    manifest = source / "plugin.json"
    if not manifest.exists():
        raise PluginInstallCliError(
            "manifest_missing",
            "Local plugin directory is missing plugin.json.",
            next_steps=[
                "Add plugin.json at the root of the plugin directory.",
                "Use plugins/example-exporter/plugin.json as the minimum manifest reference.",
            ],
            details={
                "source": _path_for_report(source, placeholder="<local-plugin-source>"),
                "expected_manifest": _path_for_report(
                    manifest,
                    placeholder="<local-plugin-source>/plugin.json",
                ),
            },
        )


def _classify_value_error(exc: ValueError) -> PluginInstallCliError:
    message = str(exc)
    if "Cannot install invalid plugin:" in message:
        return PluginInstallCliError(
            "invalid_manifest",
            message,
            next_steps=[
                "Open plugin.json and fix the field named in the validation message.",
                "Compare with plugins/example-exporter/plugin.json, then rerun the install command.",
            ],
        )
    if "destination must be outside the source directory" in message:
        return PluginInstallCliError(
            "unsafe_destination",
            message,
            next_steps=[
                "Choose a destination outside the plugin source directory.",
                "For a quick check, omit --destination and use the default local data/plugins directory.",
            ],
        )
    if "trust policy blocks" in message or "do_not_install" in message:
        return PluginInstallCliError(
            "trust_policy_blocked",
            message,
            next_steps=[
                "Do not install this plugin until its registry metadata, signature, or digest is fixed.",
                "Inspect the preview/trust report before approving any local plugin install.",
            ],
        )
    return PluginInstallCliError(
        "plugin_install_invalid",
        message,
        next_steps=[
            "Run without --approve-install first to quarantine and inspect the plugin.",
            "If the message names a manifest field, fix plugin.json and retry.",
        ],
    )


def _classify_file_exists(exc: FileExistsError) -> PluginInstallCliError:
    return PluginInstallCliError(
        "plugin_already_present",
        str(exc),
        next_steps=[
            "Review the existing installed or quarantined plugin directory first.",
            "Rerun with --replace only when you intentionally want to overwrite it.",
        ],
    )


def _classify_os_error(exc: OSError) -> PluginInstallCliError:
    return PluginInstallCliError(
        "filesystem_error",
        str(exc),
        next_steps=[
            "Check that the destination parent exists and is writable.",
            "Retry with --destination and --quarantine-destination pointing to writable local paths.",
        ],
    )


def _ensure_supported_python() -> None:
    if sys.version_info >= (3, 11):
        return
    raise PluginInstallCliError(
        "python_version_unsupported",
        "Local plugin install requires Python 3.11 or newer.",
        next_steps=[
            "Run with the project virtual environment: .venv/bin/python scripts/install_local_plugin.py <plugin-dir>",
            "Or set up the environment first: python3 scripts/setup_env.py",
            "If you only want the zero-config learning path, start with: ./scripts/run_skill_mode_demo.sh",
        ],
        details={"python_version": sys.version.split()[0]},
    )


def _error_payload(exc: PluginInstallCliError) -> dict[str, Any]:
    return {
        "schema_version": "plugin-install-error-v1",
        "status": "error",
        "error_code": exc.code,
        "classification": exc.code,
        "message": _redact_report_value(exc.message),
        "next_steps": _redact_report_value(exc.next_steps),
        "details": _redact_report_value(exc.details),
        "entrypoints_executed": False,
        "privacy": {
            "local_only": True,
            "local_absolute_paths_included": False,
            "secrets_recorded": False,
        },
    }


def _print_error(exc: PluginInstallCliError) -> None:
    print(json.dumps(_error_payload(exc), ensure_ascii=False, indent=2, sort_keys=True), file=sys.stderr)


def main() -> None:
    args = build_parser().parse_args()
    source = args.source.expanduser()
    _validate_source_shape(source)
    _ensure_supported_python()
    if str(API_PATH) not in sys.path:
        sys.path.insert(0, str(API_PATH))
    from study_anything.core.plugin_registry import PluginRegistry

    registry = PluginRegistry([])
    if args.approve_install:
        preview = registry.preview_local(source)
        if preview.manifest is None:
            raise PluginInstallCliError(
                "invalid_manifest",
                f"Cannot install invalid plugin: {preview.message}",
                next_steps=[
                    "Open plugin.json and fix the validation error.",
                    "Run the command without --approve-install after the manifest is valid.",
                ],
                details={"source": _path_for_report(source, placeholder="<local-plugin-source>")},
            )
        if preview.trust is not None and preview.trust.install_recommendation == "do_not_install":
            raise PluginInstallCliError(
                "trust_policy_blocked",
                "Plugin trust policy blocks installation.",
                next_steps=[
                    "Do not approve-install this plugin until the trust report is fixed.",
                    "Use a reviewed local plugin or keep it quarantined for manual inspection.",
                ],
                details={"plugin_id": preview.manifest.plugin_id},
            )
        quarantined_source = args.quarantine_destination / preview.manifest.plugin_id
        if not quarantined_source.exists():
            raise PluginInstallCliError(
                "quarantine_required",
                "Plugin must be quarantined before approved installation.",
                next_steps=[
                    "Run without --approve-install first to copy the plugin into quarantine.",
                    "Inspect the quarantined copy, then rerun with --approve-install.",
                ],
                details={
                    "plugin_id": preview.manifest.plugin_id,
                    "quarantine_source": _path_for_report(
                        quarantined_source,
                        placeholder=f"<plugin-quarantine-dir>/{preview.manifest.plugin_id}",
                    ),
                },
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
            source,
            args.quarantine_destination,
            replace_existing=True,
        )
        lifecycle_status = "quarantined"
        destination = args.quarantine_destination
    payload = {
        **status.public_dict(),
        "schema_version": "plugin-install-result-v1",
        "lifecycle_status": lifecycle_status,
        "classification": f"plugin_{lifecycle_status}",
        "installed": lifecycle_status == "installed",
        "quarantined": lifecycle_status == "quarantined",
        "destination_dir": _path_for_report(destination, placeholder="<plugin-output-dir>"),
        "install_dir": _path_for_report(
            args.destination,
            placeholder="<plugin-install-dir>",
        ),
        "quarantine_dir": _path_for_report(
            args.quarantine_destination,
            placeholder="<plugin-quarantine-dir>",
        ),
        "entrypoints_executed": False,
        "privacy": {
            "local_only": True,
            "local_absolute_paths_included": False,
            "secrets_recorded": False,
        },
    }
    print(
        json.dumps(
            _redact_report_value(payload),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except PluginInstallCliError as exc:
        _print_error(exc)
        sys.exit(1)
    except FileExistsError as exc:
        _print_error(_classify_file_exists(exc))
        sys.exit(1)
    except ValueError as exc:
        _print_error(_classify_value_error(exc))
        sys.exit(1)
    except OSError as exc:
        _print_error(_classify_os_error(exc))
        sys.exit(1)
