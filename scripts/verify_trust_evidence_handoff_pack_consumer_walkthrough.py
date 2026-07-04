#!/usr/bin/env python3
"""Verify a Trust Evidence Handoff Pack from the ZIP alone."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Any, Mapping
import zipfile

from generate_trust_evidence_handoff_pack import (
    ARCHIVE_PATH,
    ARCHIVE_ROOT,
    PACKAGE_NAME,
    ROOT,
    SCHEMA_VERSION as PACK_SCHEMA_VERSION,
)


REPORT = ROOT / "platform" / "generated" / "study-anything-trust-evidence-handoff-pack-consumer-walkthrough.json"
SCHEMA_VERSION = "trust-evidence-handoff-pack-consumer-walkthrough-v1"
FORBIDDEN_PATH_PARTS = {".git", ".env", ".venv", "data", "__pycache__"}
SECRET_PATTERNS = (
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]+\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{36}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]{12,}=*"),
    re.compile(r"/Users/[A-Za-z0-9._-]+/[^\s'\"<>]+"),
    re.compile(r"/private/var/folders/[A-Za-z0-9._-]+/[^\s'\"<>]+"),
)
FORBIDDEN_TRUE_FLAGS = {
    "agent_credentials_included",
    "agent_endpoint_secrets_included",
    "attention_streams_included",
    "automatic_customer_delivery_performed",
    "automatic_customer_sending_performed",
    "bearer_tokens_included",
    "biometrics_included",
    "client_secrets_included",
    "cookies_included",
    "cookies_or_bearer_tokens_included",
    "customer_payload_included",
    "daemon_or_hosted_service_started",
    "delivery_artifact_body_included",
    "external_publication_performed",
    "eye_tracking_included",
    "eye_tracking_or_biometrics_included",
    "keystrokes_included",
    "model_calls_performed",
    "model_prompts_included",
    "mouse_coordinates_included",
    "platform_agent_credentials_included",
    "production_mutation_allowed",
    "production_mutation_performed",
    "production_payload_included",
    "raw_customer_payload_included",
    "raw_report_text_included",
    "raw_review_text_included",
    "raw_source_text_included",
    "real_secrets_included",
    "screenshots_included",
    "signed_urls_included",
    "source_mutation_performed",
    "user_owned_agent_credentials_included",
}


class TrustEvidenceHandoffConsumerError(RuntimeError):
    """Readable Trust Evidence Handoff Pack consumer verification failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def assert_no_private_text(text: str, *, label: str) -> None:
    for pattern in SECRET_PATTERNS:
        match = pattern.search(text)
        if match:
            raise TrustEvidenceHandoffConsumerError(
                f"{label} contains private-looking text: {match.group(0)[:80]}"
            )


def walk_mappings(value: Any) -> list[Mapping[str, Any]]:
    found: list[Mapping[str, Any]] = []
    if isinstance(value, Mapping):
        found.append(value)
        for child in value.values():
            found.extend(walk_mappings(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(walk_mappings(child))
    return found


def assert_metadata_only(payload: Mapping[str, Any], *, label: str) -> None:
    regressions: list[str] = []
    for mapping in walk_mappings(payload):
        for key in FORBIDDEN_TRUE_FLAGS:
            if mapping.get(key) is True:
                regressions.append(key)
    if regressions:
        raise TrustEvidenceHandoffConsumerError(f"{label} has privacy regressions: {sorted(set(regressions))}")
    assert_no_private_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), label=label)


def assert_safe_member(name: str) -> None:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise TrustEvidenceHandoffConsumerError(f"Unsafe ZIP member path: {name}")
    if any(part in FORBIDDEN_PATH_PARTS for part in path.parts):
        raise TrustEvidenceHandoffConsumerError(f"Forbidden ZIP member path part in: {name}")
    if not name.startswith(f"{ARCHIVE_ROOT}/"):
        raise TrustEvidenceHandoffConsumerError(f"ZIP member is outside archive root: {name}")


def read_json_member(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
    try:
        raw = archive.read(name)
    except KeyError as exc:
        raise TrustEvidenceHandoffConsumerError(f"Missing ZIP member: {name}") from exc
    text = raw.decode("utf-8", errors="replace")
    assert_no_private_text(text, label=name)
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise TrustEvidenceHandoffConsumerError(f"ZIP member JSON must be an object: {name}")
    assert_metadata_only(payload, label=name)
    return payload


def validate_manifest_shape(manifest: Mapping[str, Any]) -> None:
    expected = {
        "schema_version": PACK_SCHEMA_VERSION,
        "name": PACKAGE_NAME,
        "package_type": "trust_evidence_handoff_pack",
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise TrustEvidenceHandoffConsumerError(f"manifest {key} drifted: expected {value!r}")
    rules = manifest.get("trust_rules")
    if not isinstance(rules, Mapping):
        raise TrustEvidenceHandoffConsumerError("manifest is missing trust_rules")
    for key in (
        "both_dual_loop_sides_required",
        "active_reconstruction_required",
        "delivery_class_must_be_registered",
        "scenario_decision_must_allow",
        "delivery_trust_case_pack_must_be_current",
        "ai_review_only_rejected",
        "automatic_customer_sending_blocked",
        "production_mutation_blocked",
        "truth_certification_blocked",
    ):
        if rules.get(key) is not True:
            raise TrustEvidenceHandoffConsumerError(f"manifest trust rule must be true: {key}")
    boundary = manifest.get("claim_boundary")
    if not isinstance(boundary, Mapping):
        raise TrustEvidenceHandoffConsumerError("manifest is missing claim_boundary")
    for item in ("production approval", "automatic customer sending", "truth certification"):
        if item not in set(boundary.get("not_claimed") or []):
            raise TrustEvidenceHandoffConsumerError(f"manifest claim boundary must reject {item}")


def validate_file_records(archive: zipfile.ZipFile, manifest: Mapping[str, Any]) -> list[str]:
    names = archive.namelist()
    for name in names:
        assert_safe_member(name)
        assert_no_private_text(archive.read(name).decode("utf-8", errors="replace"), label=name)
    roots = {name.split("/", 1)[0] for name in names}
    if roots != {ARCHIVE_ROOT}:
        raise TrustEvidenceHandoffConsumerError(f"ZIP must have a single archive root: {sorted(roots)}")
    records = manifest.get("files")
    if not isinstance(records, list) or not records:
        raise TrustEvidenceHandoffConsumerError("manifest files must be a non-empty list")
    name_set = set(names)
    for record in records:
        if not isinstance(record, Mapping):
            raise TrustEvidenceHandoffConsumerError("manifest file records must be objects")
        archive_path = str(record.get("archive_path") or "")
        if archive_path not in name_set:
            raise TrustEvidenceHandoffConsumerError(f"recorded file is missing from ZIP: {archive_path}")
        if sha256_bytes(archive.read(archive_path)) != record.get("sha256"):
            raise TrustEvidenceHandoffConsumerError(f"recorded file hash mismatch: {archive_path}")
    for required in ("manifest.json", "HANDOFF_PACK_README.md"):
        if f"{ARCHIVE_ROOT}/{required}" not in name_set:
            raise TrustEvidenceHandoffConsumerError(f"ZIP is missing {required}")
    return names


def validate_core_reports(manifest: Mapping[str, Any]) -> dict[str, Any]:
    core = manifest.get("core_reports")
    if not isinstance(core, Mapping):
        raise TrustEvidenceHandoffConsumerError("manifest is missing core_reports")
    if core.get("delivery_class_ids") != ["client_report_handoff", "code_review_handoff"]:
        raise TrustEvidenceHandoffConsumerError("delivery class IDs drifted")
    if core.get("trust_scenario_count") != 4 or core.get("blocked_scenario_count") != 2:
        raise TrustEvidenceHandoffConsumerError("trust scenario counts drifted")
    if core.get("decision_case_count") != 7:
        raise TrustEvidenceHandoffConsumerError("decision case count drifted")
    allowed = set(core.get("allowed_decision_cases") or [])
    if allowed != {"controlled_client_report_handoff", "controlled_code_review_handoff"}:
        raise TrustEvidenceHandoffConsumerError("allowed decision cases drifted")
    return {
        "delivery_class_count": int(core["delivery_class_count"]),
        "trust_scenario_count": int(core["trust_scenario_count"]),
        "decision_case_count": int(core["decision_case_count"]),
        "allowed_decision_cases": sorted(allowed),
        "blocked_decision_scenario_count": len(core.get("blocked_decision_scenarios") or []),
    }


def consume_pack(pack_path: Path) -> dict[str, Any]:
    if not pack_path.is_file():
        raise TrustEvidenceHandoffConsumerError(f"Pack ZIP is missing: {pack_path.name}")
    try:
        archive = zipfile.ZipFile(pack_path)
    except zipfile.BadZipFile as exc:
        raise TrustEvidenceHandoffConsumerError("Pack is not a valid ZIP archive") from exc
    with archive:
        manifest_name = f"{ARCHIVE_ROOT}/manifest.json"
        manifest = read_json_member(archive, manifest_name)
        manifest_raw = archive.read(manifest_name)
        validate_manifest_shape(manifest)
        names = validate_file_records(archive, manifest)
        core_summary = validate_core_reports(manifest)
        decision_report = read_json_member(
            archive,
            f"{ARCHIVE_ROOT}/platform/generated/study-anything-trust-scenario-decision-gate.json",
        )
        if decision_report.get("allowed_case_count") != 2 or decision_report.get("blocked_case_count") != 5:
            raise TrustEvidenceHandoffConsumerError("embedded decision gate report drifted")

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "purpose": "Verify external zip-only consumption of the Trust Evidence Handoff Pack.",
        "pack": {
            "archive_name": pack_path.name,
            "archive_root": ARCHIVE_ROOT,
            "manifest_schema_version": manifest["schema_version"],
            "manifest_sha256": sha256_bytes(manifest_raw),
            "zip_sha256": sha256_bytes(pack_path.read_bytes()),
            "entry_count": len(names),
            "file_record_count": len(manifest["files"]),
        },
        "walkthrough": [
            {"step_id": "download_pack", "status": "pass", "evidence": "ZIP is valid and has one archive root."},
            {"step_id": "verify_manifest_and_hashes", "status": "pass", "evidence": "Manifest records match archive members and SHA-256 hashes."},
            {"step_id": "inspect_delivery_classes", "status": "pass", "evidence": "Registered delivery classes are present."},
            {"step_id": "inspect_decision_gate", "status": "pass", "evidence": "Only supported scenarios are allowed; blocked scenarios remain blocked."},
            {"step_id": "inspect_claim_boundary", "status": "pass", "evidence": "Claim boundary rejects production/customer/truth overclaims."},
        ],
        "core_summary": core_summary,
        "decision": {
            "external_adopter_can_verify_zip_only": True,
            "controlled_handoff_scenarios_allowed": core_summary["allowed_decision_cases"],
            "blocked_scenarios_remain_blocked": True,
            "ai_review_only_rejected": True,
            "production_mutation_blocked": True,
            "truth_certification_blocked": True,
        },
        "privacy": {
            "metadata_only": True,
            "model_calls_performed": False,
            "daemon_or_hosted_service_started": False,
            "production_mutation_performed": False,
            "automatic_customer_sending_performed": False,
            "external_publication_performed": False,
            "raw_source_text_included": False,
            "raw_report_text_included": False,
            "raw_customer_payload_included": False,
            "delivery_artifact_body_included": False,
            "screenshots_included": False,
            "attention_streams_included": False,
            "real_secrets_included": False,
            "user_owned_agent_credentials_included": False,
        },
        "claim_boundary": {
            "current_claim": "An external consumer can verify the handoff evidence pack from ZIP metadata alone.",
            "not_claimed": [
                "production approval",
                "automatic customer sending",
                "truth certification",
                "customer outcome guarantee",
                "general model correctness",
            ],
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, default=ARCHIVE_PATH)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = consume_pack(args.pack)
    text = dump_json(report)
    if args.write:
        REPORT.write_text(text, encoding="utf-8")
        print(f"wrote {REPORT.relative_to(ROOT)}")
        return
    if args.check:
        if not REPORT.exists():
            raise TrustEvidenceHandoffConsumerError(f"consumer walkthrough report missing: {REPORT.relative_to(ROOT)}")
        if REPORT.read_text(encoding="utf-8") != text:
            raise TrustEvidenceHandoffConsumerError(
                "Trust Evidence Handoff Pack consumer walkthrough is stale. Run: "
                "python3 scripts/verify_trust_evidence_handoff_pack_consumer_walkthrough.py --write"
            )
        print("ok    Trust Evidence Handoff Pack consumer walkthrough is up to date")
        return
    print(text, end="")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_trust_evidence_handoff_pack_consumer_walkthrough failed: {exc}", file=sys.stderr)
        sys.exit(1)
