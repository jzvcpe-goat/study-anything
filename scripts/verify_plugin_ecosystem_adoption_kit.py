#!/usr/bin/env python3
"""Verify the copy-ready plugin ecosystem adoption kit."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "plugin-ecosystem-adoption-kit-v1"
RELEASE_VERSION = "v0.3.21-alpha"
DEFAULT_REPORT = ROOT / "platform" / "generated" / "study-anything-plugin-ecosystem-adoption-kit.json"
DEFAULT_PACK = ROOT / "platform" / "generated" / "study-anything-platform-adoption-pack.zip"

PLATFORM_IDS = ("codex", "kimi", "workbuddy")
EXPECTED_PLUGINS = {
    "example-note-importer": {
        "path": "plugins/example-note-importer",
        "role": "source_importer",
        "hooks": {"importer"},
        "capabilities": {"import.markdown_note", "import.obsidian_note"},
        "permissions": {"write:context"},
    },
    "example-web-importer": {
        "path": "plugins/example-web-importer",
        "role": "web_importer",
        "hooks": {"importer"},
        "capabilities": {"import.context", "import.web_excerpt"},
        "permissions": {"write:context", "network:http"},
    },
    "example-enrichment-importer": {
        "path": "plugins/example-enrichment-importer",
        "role": "learning_enrichment",
        "hooks": {"importer", "enrichment"},
        "capabilities": {"import.context", "enrich.micro_lesson", "enrich.visual_html"},
        "permissions": {"read:context", "write:context"},
    },
    "example-exporter": {
        "path": "plugins/example-exporter",
        "role": "exporter",
        "hooks": {"exporter"},
        "capabilities": {"export.markdown", "export.obsidian_note", "export.second_brain_handoff"},
        "permissions": {"read:sessions"},
    },
    "example-agent-provider": {
        "path": "plugins/example-agent-provider",
        "role": "agent_provider_template",
        "hooks": {"agent_provider", "agent_panel"},
        "capabilities": {"agent.register_provider", "ui.register_panel"},
        "permissions": {"read:agents", "write:agents", "network:http", "ui:panel"},
    },
}
ALLOWED_HOOKS = {
    "importer",
    "model_provider",
    "agent_provider",
    "agent_tool",
    "agent_panel",
    "enrichment",
    "source_verifier",
    "quiz_generator",
    "grader",
    "exporter",
    "ui_panel",
}
ALLOWED_CAPABILITIES = {
    "agent.invoke_tool",
    "agent.register_provider",
    "enrich.micro_lesson",
    "enrich.visual_html",
    "export.markdown",
    "export.obsidian_note",
    "export.second_brain_handoff",
    "import.context",
    "import.markdown_note",
    "import.obsidian_note",
    "import.web_excerpt",
    "quiz.generate",
    "answer.grade",
    "source.verify_reference",
    "ui.register_panel",
}
ALLOWED_PERMISSIONS = {
    "read:sessions",
    "write:sessions",
    "read:cards",
    "write:cards",
    "read:models",
    "write:models",
    "read:agents",
    "write:agents",
    "read:context",
    "write:context",
    "network:http",
    "ui:panel",
}
PERMISSION_RISK = {
    "read:sessions": "medium",
    "write:sessions": "high",
    "read:cards": "medium",
    "write:cards": "high",
    "read:models": "low",
    "write:models": "medium",
    "read:agents": "medium",
    "write:agents": "high",
    "read:context": "medium",
    "write:context": "high",
    "network:http": "high",
    "ui:panel": "low",
}
RISK_ORDER = {"low": 1, "medium": 2, "high": 3, "unknown": 4}
REQUIRED_OPERATOR_ASSETS = [
    "docs/plugins.md",
    "docs/plugin-sdk.md",
    "docs/plugin-registry.md",
    "docs/platform-agent-integrations.md",
    "docs/adoption.md",
    "docs/use-with-kimi.md",
    "scripts/install_local_plugin.py",
    "scripts/verify_plugin_quarantine.py",
    "scripts/verify_plugin_ecosystem_adoption_kit.py",
    "platform/ecosystem-submission.json",
    "platform/study-anything-platform-tools.json",
]
REQUIRED_PACK_COMMAND = "verify_plugin_ecosystem_adoption_kit.py --check"
REQUIRED_EVIDENCE = (
    "plugin_ecosystem_adoption_kit.schema_version == plugin-ecosystem-adoption-kit-v1"
)
FORBIDDEN_PATTERNS = [
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_./+=-]{8,}"),
]
FORBIDDEN_LITERALS = [
    "OPENAI_API_KEY=",
    "MOONSHOT_API_KEY=",
    "Private answer:",
    "Private platform browser/video context",
    "raw source text returned",
    "learner@example.com",
]
IGNORED_DIGEST_NAMES = {"__pycache__", ".DS_Store", ".git"}
IGNORED_DIGEST_SUFFIXES = {".pyc", ".pyo"}


class PluginEcosystemKitError(RuntimeError):
    """Readable plugin ecosystem adoption-kit failure."""


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise PluginEcosystemKitError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PluginEcosystemKitError(f"JSON object expected: {path}")
    return value


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def resolve_pack_root(args: argparse.Namespace, tmp_root: Path) -> Path:
    if args.pack_root:
        root = Path(args.pack_root).resolve()
        if not root.exists():
            raise PluginEcosystemKitError(f"Pack root does not exist: {root}")
        return root
    if args.pack:
        pack = Path(args.pack).resolve()
        if not pack.exists():
            raise PluginEcosystemKitError(f"Adoption pack archive is missing: {pack}")
        with zipfile.ZipFile(pack) as archive:
            roots = {name.split("/", 1)[0] for name in archive.namelist() if "/" in name}
            if len(roots) != 1:
                raise PluginEcosystemKitError(
                    f"Adoption pack archive should have one root, got {sorted(roots)}"
                )
            archive.extractall(tmp_root)
        return tmp_root / next(iter(roots))
    return ROOT


def safe_relative(root: Path, relative_path: str) -> Path:
    target = (root / relative_path).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise PluginEcosystemKitError(f"Unsafe path escapes pack root: {relative_path}") from exc
    return target


def require_file(root: Path, relative_path: str) -> Path:
    target = safe_relative(root, relative_path)
    if not target.is_file():
        raise PluginEcosystemKitError(f"Required plugin ecosystem asset is missing: {relative_path}")
    return target


def assert_contains(root: Path, relative_path: str, *needles: str) -> str:
    target = require_file(root, relative_path)
    text = target.read_text(encoding="utf-8")
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise PluginEcosystemKitError(f"{relative_path} is missing required text: {missing}")
    return text


def compute_source_digest(root: Path, plugin_path: str) -> str:
    plugin_root = safe_relative(root, plugin_path)
    if not plugin_root.is_dir():
        raise PluginEcosystemKitError(f"Plugin directory is missing: {plugin_path}")
    files = sorted(path for path in plugin_root.rglob("*") if _should_include_in_digest(plugin_root, path))
    digest = hashlib.sha256()
    for path in files:
        relative = path.relative_to(plugin_root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _should_include_in_digest(root: Path, path: Path) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    relative = path.relative_to(root)
    if any(part in IGNORED_DIGEST_NAMES for part in relative.parts):
        return False
    return path.suffix not in IGNORED_DIGEST_SUFFIXES


def highest_risk(permissions: list[str]) -> str:
    highest = "low"
    for permission in permissions:
        risk = PERMISSION_RISK.get(permission, "unknown")
        if RISK_ORDER.get(risk, RISK_ORDER["unknown"]) > RISK_ORDER[highest]:
            highest = risk
    return highest


def validate_manifest(root: Path, plugin_id: str, expected: dict[str, Any]) -> dict[str, Any]:
    manifest_path = require_file(root, f"{expected['path']}/plugin.json")
    plugin_py = require_file(root, f"{expected['path']}/plugin.py")
    manifest = read_json(manifest_path)
    if manifest.get("schemaVersion") != "plugin-manifest-v1":
        raise PluginEcosystemKitError(f"{plugin_id} manifest schema drifted.")
    if manifest.get("id") != plugin_id:
        raise PluginEcosystemKitError(f"{plugin_id} manifest id drifted.")
    if manifest.get("entrypoint") != "plugin.py":
        raise PluginEcosystemKitError(f"{plugin_id} entrypoint must remain plugin.py.")
    for key, allowed in (
        ("hooks", ALLOWED_HOOKS),
        ("capabilities", ALLOWED_CAPABILITIES),
        ("permissions", ALLOWED_PERMISSIONS),
    ):
        values = manifest.get(key)
        if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
            raise PluginEcosystemKitError(f"{plugin_id} manifest requires string list {key}.")
        unsupported = sorted(set(values) - allowed)
        if unsupported:
            raise PluginEcosystemKitError(f"{plugin_id} manifest has unsupported {key}: {unsupported}")
        expected_values = set(expected[key])
        missing = sorted(expected_values - set(values))
        if missing:
            raise PluginEcosystemKitError(f"{plugin_id} manifest missing {key}: {missing}")
    review = manifest.get("review") or {}
    if review.get("status") != "maintainer_reviewed":
        raise PluginEcosystemKitError(f"{plugin_id} must be maintainer_reviewed.")
    if any(part in {".env", ".git", "__pycache__"} for part in plugin_py.parts):
        raise PluginEcosystemKitError(f"{plugin_id} plugin source path is unsafe.")
    permissions = list(manifest.get("permissions", []))
    return {
        "plugin_id": plugin_id,
        "role": expected["role"],
        "path": expected["path"],
        "name": manifest.get("name"),
        "version": manifest.get("version"),
        "hooks": sorted(manifest.get("hooks", [])),
        "capabilities": sorted(manifest.get("capabilities", [])),
        "permissions": sorted(permissions),
        "risk_level": highest_risk(permissions),
        "review_status": review.get("status"),
        "entrypoint": manifest.get("entrypoint"),
        "entrypoint_executed_by_validation": False,
    }


def validate_registry(root: Path, plugin_records: dict[str, dict[str, Any]]) -> dict[str, Any]:
    registry = read_json(require_file(root, "plugins/registry.json"))
    if registry.get("schemaVersion") != "plugin-registry-v1":
        raise PluginEcosystemKitError("Plugin registry schema drifted.")
    entries = registry.get("plugins")
    if not isinstance(entries, list):
        raise PluginEcosystemKitError("Plugin registry requires plugins list.")
    by_id = {str(entry.get("id")): entry for entry in entries if isinstance(entry, dict)}
    missing = sorted(set(EXPECTED_PLUGINS) - set(by_id))
    if missing:
        raise PluginEcosystemKitError(f"Plugin registry missing bundled plugins: {missing}")
    digest_verified: list[str] = []
    for plugin_id, record in plugin_records.items():
        entry = by_id[plugin_id]
        expected_path = record["path"]
        if entry.get("path") != expected_path:
            raise PluginEcosystemKitError(f"{plugin_id} registry path drifted.")
        digest = compute_source_digest(root, expected_path)
        if entry.get("sourceDigest") != digest:
            raise PluginEcosystemKitError(
                f"{plugin_id} registry sourceDigest mismatch: {entry.get('sourceDigest')} != {digest}"
            )
        review = entry.get("review") or {}
        if review.get("status") != "maintainer_reviewed":
            raise PluginEcosystemKitError(f"{plugin_id} registry review must be maintainer_reviewed.")
        digest_verified.append(plugin_id)
        record["source_digest"] = digest
        record["registry_status"] = "digest_verified"
        record["registry_review_status"] = review.get("status")
    trusted_keys = registry.get("trustedKeys", [])
    return {
        "schema_version": registry.get("schemaVersion"),
        "plugin_count": len(entries),
        "bundled_plugin_count": len(EXPECTED_PLUGINS),
        "digest_verified_count": len(digest_verified),
        "trusted_key_count": len(trusted_keys) if isinstance(trusted_keys, list) else 0,
        "remote_code_downloads_allowed": False,
        "automatic_updates_allowed": False,
        "digest_verified_plugins": sorted(digest_verified),
    }


def validate_submission(root: Path) -> dict[str, Any]:
    submission = read_json(safe_relative(root, "platform/ecosystem-submission.json"))
    if submission.get("schema_version") != "ecosystem-submission-v1":
        raise PluginEcosystemKitError("Ecosystem submission schema drifted.")
    if submission.get("version") != RELEASE_VERSION:
        raise PluginEcosystemKitError(f"Ecosystem submission version must be {RELEASE_VERSION}.")
    shared_assets = set(str(item) for item in submission.get("shared_assets", []))
    required_assets = {
        "docs/plugins.md",
        "docs/plugin-sdk.md",
        "docs/plugin-registry.md",
        "scripts/verify_plugin_ecosystem_adoption_kit.py",
        "scripts/install_local_plugin.py",
        "platform/generated/study-anything-plugin-ecosystem-adoption-kit.json",
        "plugins/registry.json",
    }
    required_assets.update(f"{info['path']}/plugin.json" for info in EXPECTED_PLUGINS.values())
    required_assets.update(f"{info['path']}/plugin.py" for info in EXPECTED_PLUGINS.values())
    missing_assets = required_assets - shared_assets
    if missing_assets:
        raise PluginEcosystemKitError(f"Ecosystem submission missing plugin assets: {sorted(missing_assets)}")
    command_text = "\n".join(str(item) for item in (submission.get("acceptance") or {}).get("minimum_commands", []))
    if REQUIRED_PACK_COMMAND not in command_text:
        raise PluginEcosystemKitError("Ecosystem submission missing plugin ecosystem kit check.")
    prove_text = "\n".join(str(item) for item in (submission.get("acceptance") or {}).get("must_prove", []))
    if SCHEMA_VERSION not in prove_text:
        raise PluginEcosystemKitError("Ecosystem submission must prove plugin ecosystem adoption kit schema.")
    return {
        "schema_version": submission.get("schema_version"),
        "version": submission.get("version"),
        "platform_count": len(submission.get("submissions", [])),
        "plugin_assets_declared": len(required_assets),
    }


def validate_platform_pack(root: Path, platform_id: str) -> dict[str, Any]:
    pack = read_json(safe_relative(root, f"platform/packs/{platform_id}/pack.json"))
    if pack.get("schema_version") != "study-anything-platform-pack-v1":
        raise PluginEcosystemKitError(f"{platform_id} pack schema drifted.")
    commands = [str(command) for command in pack.get("local_verification_commands", [])]
    if REQUIRED_PACK_COMMAND not in "\n".join(commands):
        raise PluginEcosystemKitError(f"{platform_id} pack must include {REQUIRED_PACK_COMMAND}.")
    evidence = set(str(item) for item in pack.get("acceptance_evidence", []))
    if REQUIRED_EVIDENCE not in evidence:
        raise PluginEcosystemKitError(f"{platform_id} pack missing plugin ecosystem kit evidence.")
    return {
        "platform_id": platform_id,
        "integration_mode": pack.get("integration_mode"),
        "plugin_verifier_command_present": True,
        "acceptance_evidence_count": len(evidence),
    }


def validate_docs(root: Path) -> dict[str, Any]:
    assert_contains(
        root,
        "docs/plugins.md",
        "plugin-manifest-v1",
        "quarantine",
        "sourceDigest",
        "example-note-importer",
        "example-exporter",
    )
    assert_contains(
        root,
        "docs/plugin-registry.md",
        "plugin-registry-v1",
        "sourceDigest",
        "do_not_install",
        "does not download code",
    )
    assert_contains(
        root,
        "docs/platform-agent-integrations.md",
        "Plugin SDK",
        "validate-package",
        "raw source",
    )
    return {
        "operator_docs": [
            "docs/plugins.md",
            "docs/plugin-sdk.md",
            "docs/plugin-registry.md",
            "docs/platform-agent-integrations.md",
        ],
        "docs_are_metadata_first": True,
    }


def sample_flows() -> list[dict[str, Any]]:
    return [
        {
            "flow_id": "validate_sample_plugin_without_execution",
            "command": "python3 scripts/study_anything_cli.py plugin-validate plugins/example-note-importer",
            "expected_schema": "plugin-package-validation-v1",
            "entrypoints_executed": False,
        },
        {
            "flow_id": "quarantine_unknown_plugin_by_default",
            "command": "python3 scripts/verify_plugin_quarantine.py",
            "expected_schema": "plugin-quarantine-verification-v1",
            "default_action": "quarantine",
        },
        {
            "flow_id": "review_trust_registry_before_install",
            "command": "GET /v1/plugins/registry-review",
            "expected_schema": "plugin-registry-review-v1",
            "downloads_remote_code": False,
        },
        {
            "flow_id": "copy_enrichment_template_for_platform_agent",
            "sample_plugin": "plugins/example-enrichment-importer",
            "expected_output_contract": "learning-enrichment-artifact-v1",
            "platform_agent_owns_external_context": True,
        },
        {
            "flow_id": "export_second_brain_handoff",
            "sample_plugin": "plugins/example-exporter",
            "expected_output_contract": "second-brain-handoff-v1",
            "raw_answers_in_adoption_evidence": False,
        },
    ]


def assert_no_leaks(payload: dict[str, Any]) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in serialized]
    leaks.extend(pattern.pattern for pattern in FORBIDDEN_PATTERNS if pattern.search(serialized))
    if leaks:
        raise PluginEcosystemKitError(f"Plugin ecosystem adoption kit leaked private data: {leaks}")


def build_report(root: Path) -> dict[str, Any]:
    running_from_adoption_pack = safe_relative(root, "manifest.json").is_file()
    for path in REQUIRED_OPERATOR_ASSETS:
        require_file(root, path)
    for expected in EXPECTED_PLUGINS.values():
        require_file(root, f"{expected['path']}/plugin.json")
        require_file(root, f"{expected['path']}/plugin.py")
    if not running_from_adoption_pack:
        require_file(root, "platform/generated/study-anything-platform-adoption-pack.json")

    plugin_records = {
        plugin_id: validate_manifest(root, plugin_id, expected)
        for plugin_id, expected in EXPECTED_PLUGINS.items()
    }
    registry = validate_registry(root, plugin_records)
    report = {
        "schema_version": SCHEMA_VERSION,
        "version": RELEASE_VERSION,
        "status": "pass",
        "ecosystem_goal": (
            "Give external platform Agents copyable plugin examples, trust metadata, and "
            "metadata-only validation gates before any hosted marketplace exists."
        ),
        "submission": validate_submission(root),
        "platforms": {
            platform_id: validate_platform_pack(root, platform_id)
            for platform_id in PLATFORM_IDS
        },
        "plugin_registry": registry,
        "bundled_plugins": [plugin_records[plugin_id] for plugin_id in sorted(plugin_records)],
        "sample_flows": sample_flows(),
        "trust_policy": {
            "schema_version": "plugin-trust-v1",
            "default_install_action": "quarantine",
            "explicit_approval_required_for_install": True,
            "digest_mismatch_action": "do_not_install",
            "registry_review_reads_metadata_only": True,
            "remote_marketplace_payments_enabled": False,
            "automatic_remote_plugin_downloads_enabled": False,
            "entrypoints_executed_during_preview": False,
            "entrypoints_executed_during_quarantine": False,
        },
        "artifact_import_export": {
            "source_report": "platform/generated/study-anything-plugin-ecosystem-adoption-kit.json",
            "adoption_pack": "platform/generated/study-anything-platform-adoption-pack.zip",
            "sample_plugins": [EXPECTED_PLUGINS[plugin_id]["path"] for plugin_id in sorted(EXPECTED_PLUGINS)],
            "copyable_commands": [
                "python3 scripts/verify_plugin_ecosystem_adoption_kit.py --check",
                "python3 scripts/verify_plugin_quarantine.py",
                "python3 scripts/study_anything_cli.py plugin-sdk",
                "python3 scripts/study_anything_cli.py plugin-capabilities",
                "python3 scripts/study_anything_cli.py plugin-validate plugins/example-note-importer",
            ],
        },
        "operator_docs": validate_docs(root),
        "privacy_assertions": {
            "real_model_keys_stored_by_study_anything": False,
            "agent_endpoint_secrets_in_plugin_registry": False,
            "raw_source_text_in_adoption_kit": False,
            "learner_answers_in_adoption_kit": False,
            "plugin_entrypoints_executed_by_verifier": False,
            "remote_code_downloads_allowed": False,
            "browser_video_private_context_in_adoption_kit": False,
            "report_is_redacted": True,
        },
        "failure_remediation": {
            "manifest_invalid": [
                "Run plugin-validate against the explicit local plugin directory.",
                "Keep hooks, capabilities, and permissions inside the documented allowlists.",
            ],
            "digest_mismatch": [
                "Recompute sourceDigest only after reviewing the local plugin source.",
                "Do not install or quarantine plugins whose registry digest mismatches.",
            ],
            "pack_missing_plugin_assets": [
                "Regenerate the adoption pack after editing PACK_FILES.",
                "Verify plugins/registry.json and every bundled plugin manifest/source are in the archive.",
            ],
            "privacy_leak": [
                "Remove raw source, learner answer, endpoint, or key material from generated evidence.",
                "Share only manifest metadata, digests, schema names, and redacted status.",
            ],
        },
    }
    assert_no_leaks(report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", help="Optional adoption-pack zip to validate.")
    parser.add_argument("--pack-root", help="Optional unpacked adoption-pack or repo root.")
    parser.add_argument("--output", default=str(DEFAULT_REPORT))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    tmp_root = Path(tempfile.mkdtemp(prefix="study-anything-plugin-ecosystem-kit-"))
    try:
        root = resolve_pack_root(args, tmp_root)
        payload = build_report(root)
        text = dump_json(payload)
        output = Path(args.output)
        if args.check:
            if not output.exists():
                raise PluginEcosystemKitError(f"Plugin ecosystem adoption kit report missing: {output}")
            if output.read_text(encoding="utf-8") != text:
                raise PluginEcosystemKitError(
                    "Plugin ecosystem adoption kit is stale. Run "
                    "`python3 scripts/verify_plugin_ecosystem_adoption_kit.py --write`."
                )
            print("ok    plugin ecosystem adoption kit is up to date")
            return
        if args.write:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(text, encoding="utf-8")
            print(f"wrote {output.relative_to(ROOT)}")
            return
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_plugin_ecosystem_adoption_kit failed: {exc}", file=sys.stderr)
        sys.exit(1)
