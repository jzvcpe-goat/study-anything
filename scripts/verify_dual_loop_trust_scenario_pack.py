#!/usr/bin/env python3
"""Verify the portable Dual Loop trust scenario pack."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import PurePosixPath
from typing import Any

from generate_dual_loop_trust_scenario_pack import (
    ARCHIVE_PATH,
    ARCHIVE_ROOT,
    MARKDOWN_PATH,
    PACKAGE_NAME,
    ROOT,
    SCHEMA_VERSION,
    SHA256_PATH,
    SIDECAR_PATH,
)


SECRET_PATTERNS = (
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]+\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{36}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]{12,}=*"),
    re.compile(r"/Users/[A-Za-z0-9._-]+/[^\s'\"<>]+"),
    re.compile(r"/private/var/folders/[A-Za-z0-9._-]+/[^\s'\"<>]+"),
)
FORBIDDEN_PATH_PARTS = {".git", ".env", ".venv", "data", "__pycache__"}
REQUIRED_ARCHIVE_FILES = {
    "manifest.json",
    "SCENARIO_PACK_README.md",
    "docs/dual-loop-scenario-harness.md",
    "scripts/run_dual_loop_scenario_harness.py",
    "scripts/verify_dual_loop_scenario_harness.py",
    "scripts/cbb_delivery_harness.py",
    "scripts/verify_cbb_delivery_harness.py",
    "fixtures/dual-loop-scenarios/pass/scenario-result.json",
    "fixtures/dual-loop-scenarios/attention-missing/scenario-result.json",
    "fixtures/dual-loop-scenarios/risk-over-budget/scenario-result.json",
    "fixtures/dual-loop-scenarios/both-fail/scenario-result.json",
    "fixtures/cbb-delivery-harness/pass/tri-loop-run.json",
    "fixtures/cbb-delivery-harness/blocked-ai-review-only/tri-loop-run.json",
}
REQUIRED_PRIVACY_FALSE_FLAGS = (
    "model_calls_performed",
    "daemon_or_hosted_service_started",
    "production_mutation_performed",
    "raw_source_text_included",
    "raw_report_text_included",
    "screenshots_included",
    "keystrokes_included",
    "mouse_coordinates_included",
    "eye_tracking_or_biometrics_included",
    "real_secrets_included",
    "cookies_or_bearer_tokens_included",
    "signed_urls_included",
    "user_owned_agent_credentials_included",
)


class ScenarioPackVerificationError(RuntimeError):
    """Readable scenario-pack verification failure."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(data: bytes, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(data.decode("utf-8"))
    except Exception as exc:
        raise ScenarioPackVerificationError(f"{label} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ScenarioPackVerificationError(f"{label} must be a JSON object")
    return payload


def assert_safe_archive_path(path: str) -> None:
    posix = PurePosixPath(path)
    if posix.is_absolute() or ".." in posix.parts:
        raise ScenarioPackVerificationError(f"Unsafe archive path: {path}")
    if any(part in FORBIDDEN_PATH_PARTS for part in posix.parts):
        raise ScenarioPackVerificationError(f"Forbidden archive path part in: {path}")


def assert_no_private_text(name: str, data: bytes) -> None:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return
    for pattern in SECRET_PATTERNS:
        match = pattern.search(text)
        if match:
            raise ScenarioPackVerificationError(
                f"{name} contains private-looking text: {match.group(0)[:80]}"
            )


def assert_manifest(manifest: dict[str, Any], source: str) -> None:
    expected = {
        "schema_version": SCHEMA_VERSION,
        "name": PACKAGE_NAME,
        "package_type": "dual_loop_trust_scenario_pack",
        "scenario_class": "customer_delivery_readiness",
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise ScenarioPackVerificationError(
                f"{source} {key} drifted: expected {value!r}, got {manifest.get(key)!r}"
            )
    privacy = manifest.get("privacy_boundaries")
    if not isinstance(privacy, dict):
        raise ScenarioPackVerificationError(f"{source} missing privacy boundaries")
    if privacy.get("metadata_only") is not True:
        raise ScenarioPackVerificationError(f"{source} must be metadata-only")
    for flag in REQUIRED_PRIVACY_FALSE_FLAGS:
        if privacy.get(flag) is not False:
            raise ScenarioPackVerificationError(f"{source} privacy flag must be false: {flag}")
    trust_rules = manifest.get("trust_rules")
    if not isinstance(trust_rules, dict):
        raise ScenarioPackVerificationError(f"{source} missing trust rules")
    for key in (
        "controlled_failure_loop_required",
        "human_attention_reconstruction_required",
        "dual_loop_gate_required",
        "delivery_trust_receipt_required",
        "customer_handoff_package_only_for_allowed_case",
        "neither_loop_may_dominate",
        "ai_review_only_rejected",
    ):
        if trust_rules.get(key) is not True:
            raise ScenarioPackVerificationError(f"{source} trust rule must be true: {key}")


def verify_generated_assets() -> dict[str, Any]:
    for path in (SIDECAR_PATH, MARKDOWN_PATH, ARCHIVE_PATH, SHA256_PATH):
        if not path.is_file():
            raise ScenarioPackVerificationError(f"Missing generated asset: {path.relative_to(ROOT)}")
    sidecar = load_json(SIDECAR_PATH.read_bytes(), SIDECAR_PATH.name)
    assert_manifest(sidecar, "sidecar")
    archive_data = ARCHIVE_PATH.read_bytes()
    archive_sha = sha256_bytes(archive_data)
    if sidecar.get("archive", {}).get("sha256") != archive_sha:
        raise ScenarioPackVerificationError("archive sha256 does not match sidecar")
    expected_sha_text = f"{archive_sha}  {PACKAGE_NAME}.zip\n"
    if SHA256_PATH.read_text(encoding="utf-8") != expected_sha_text:
        raise ScenarioPackVerificationError("sha256 sidecar content drifted")
    assert_no_private_text(MARKDOWN_PATH.name, MARKDOWN_PATH.read_bytes())
    return sidecar


def verify_archive(sidecar: dict[str, Any]) -> None:
    with zipfile.ZipFile(ARCHIVE_PATH) as archive:
        names = archive.namelist()
        roots = {name.split("/", 1)[0] for name in names}
        if roots != {ARCHIVE_ROOT}:
            raise ScenarioPackVerificationError(
                f"archive must have one root {ARCHIVE_ROOT!r}; got {sorted(roots)}"
            )
        for name in names:
            assert_safe_archive_path(name)
        relative_names = {name.removeprefix(f"{ARCHIVE_ROOT}/") for name in names}
        missing = sorted(REQUIRED_ARCHIVE_FILES - relative_names)
        if missing:
            raise ScenarioPackVerificationError(f"archive missing required files: {missing}")
        archive_manifest = load_json(
            archive.read(f"{ARCHIVE_ROOT}/manifest.json"),
            "archive manifest",
        )
        assert_manifest(archive_manifest, "archive manifest")
        sidecar_without_archive = dict(sidecar)
        sidecar_without_archive.pop("archive", None)
        sidecar_without_archive_no_files = dict(sidecar_without_archive)
        archive_manifest_no_files = dict(archive_manifest)
        sidecar_files = sidecar_without_archive_no_files.pop("files", None)
        archive_files = archive_manifest_no_files.pop("files", None)
        if archive_manifest_no_files != sidecar_without_archive_no_files:
            raise ScenarioPackVerificationError("archive manifest does not match sidecar content")
        if not isinstance(sidecar_files, list) or not isinstance(archive_files, list):
            raise ScenarioPackVerificationError("manifest file records are malformed")
        archive_without_readme = [
            record
            for record in archive_files
            if isinstance(record, dict) and record.get("path") != "SCENARIO_PACK_README.md"
        ]
        if archive_without_readme != sidecar_files:
            raise ScenarioPackVerificationError("archive manifest file records drifted from sidecar")
        records = archive_manifest.get("files")
        if not isinstance(records, list) or not records:
            raise ScenarioPackVerificationError("archive manifest has no file records")
        for record in records:
            if not isinstance(record, dict):
                raise ScenarioPackVerificationError("archive manifest has malformed file record")
            archive_path = str(record.get("archive_path", ""))
            if archive_path not in names:
                raise ScenarioPackVerificationError(f"archive missing recorded file: {archive_path}")
            data = archive.read(archive_path)
            if sha256_bytes(data) != record.get("sha256"):
                raise ScenarioPackVerificationError(f"hash drifted for {archive_path}")
            assert_no_private_text(archive_path, data)
            if archive_path.endswith(".json"):
                payload = load_json(data, archive_path)
                serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
                assert_no_private_text(archive_path, serialized)
        assert_no_private_text(
            f"{ARCHIVE_PATH.name}:SCENARIO_PACK_README.md",
            archive.read(f"{ARCHIVE_ROOT}/SCENARIO_PACK_README.md"),
        )


def run_existing_gates() -> None:
    commands = (
        [sys.executable, "scripts/verify_dual_loop_scenario_harness.py", "--check"],
        [sys.executable, "scripts/verify_cbb_delivery_harness.py", "--check"],
    )
    for command in commands:
        subprocess.run(command, cwd=ROOT, check=True, text=True, capture_output=True)


def build_report(sidecar: dict[str, Any]) -> dict[str, Any]:
    report = {
        "schema_version": "dual-loop-trust-scenario-pack-verification-v1",
        "status": "pass",
        "version": sidecar.get("version"),
        "package": {
            "name": sidecar.get("name"),
            "schema_version": sidecar.get("schema_version"),
            "archive_sha256": sidecar.get("archive", {}).get("sha256"),
            "file_count": len(sidecar.get("files", [])),
            "scenario_class": sidecar.get("scenario_class"),
        },
        "case_matrix": sidecar.get("case_matrix"),
        "trust_rules": sidecar.get("trust_rules"),
        "privacy": sidecar.get("privacy_boundaries"),
        "acceptance": {
            "generate_command": "python3 scripts/generate_dual_loop_trust_scenario_pack.py --check",
            "minimum_command": "python3 scripts/verify_dual_loop_trust_scenario_pack.py --check",
            "release_gate": "scripts/release_check.sh",
        },
        "claim_boundary": sidecar.get("claim_boundary"),
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.parse_args()
    sidecar = verify_generated_assets()
    verify_archive(sidecar)
    run_existing_gates()
    report = build_report(sidecar)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"verify_dual_loop_trust_scenario_pack failed: {exc}", file=sys.stderr)
        sys.exit(1)
