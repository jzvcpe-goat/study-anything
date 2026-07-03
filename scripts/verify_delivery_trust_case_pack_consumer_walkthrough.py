#!/usr/bin/env python3
"""Verify a Delivery Trust Case Pack from the ZIP alone."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile
from typing import Any, Callable, Mapping
import zipfile

from generate_delivery_trust_case_pack import (
    ARCHIVE_PATH,
    ARCHIVE_ROOT,
    CASE_IDS,
    PACKAGE_NAME,
    ROOT,
    SCHEMA_VERSION as PACK_SCHEMA_VERSION,
)


REPORT = ROOT / "platform" / "generated" / "study-anything-delivery-trust-case-pack-consumer-walkthrough.json"
SCHEMA_VERSION = "delivery-trust-case-pack-consumer-walkthrough-v1"
FORBIDDEN_PATH_PARTS = {".git", ".env", ".venv", "data", "__pycache__"}
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
    "raw_source_text_included",
    "real_secrets_included",
    "screenshots_included",
    "signed_urls_included",
    "source_mutation_performed",
    "user_owned_agent_credentials_included",
}
EXPECTED = {
    "pass": {
        "status": "ready_for_controlled_customer_handoff",
        "decision": "allow_controlled_customer_handoff",
        "reasons": set(),
    },
    "blocked-product-loop": {
        "status": "blocked",
        "decision": "block_customer_handoff",
        "reasons": {"product_loop_not_passed", "developer_vision_missing"},
    },
    "blocked-dual-loop": {
        "status": "blocked",
        "decision": "block_customer_handoff",
        "reasons": {
            "dual_loop_gate_blocked",
            "sandbox_risk_outside_budget",
            "delivery_trust_not_allowed",
            "customer_handoff_not_ready",
        },
    },
    "blocked-customer-handoff": {
        "status": "blocked",
        "decision": "block_customer_handoff",
        "reasons": {"customer_handoff_not_ready", "customer_handoff_scope_expansion"},
    },
    "blocked-ai-review-only": {
        "status": "blocked",
        "decision": "block_customer_handoff",
        "reasons": {"product_loop_not_passed", "ai_review_only_evidence_rejected"},
    },
}


class DeliveryTrustCasePackConsumerError(RuntimeError):
    """Readable delivery-trust-case consumer verification failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def assert_no_private_text(text: str, *, label: str) -> None:
    for pattern in SECRET_PATTERNS:
        match = pattern.search(text)
        if match:
            raise DeliveryTrustCasePackConsumerError(
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
        raise DeliveryTrustCasePackConsumerError(f"{label} has privacy regressions: {sorted(set(regressions))}")
    assert_no_private_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), label=label)


def assert_safe_member(name: str) -> None:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise DeliveryTrustCasePackConsumerError(f"Unsafe ZIP member path: {name}")
    if any(part in FORBIDDEN_PATH_PARTS for part in path.parts):
        raise DeliveryTrustCasePackConsumerError(f"Forbidden ZIP member path part in: {name}")
    if not name.startswith(f"{ARCHIVE_ROOT}/"):
        raise DeliveryTrustCasePackConsumerError(f"ZIP member is outside archive root: {name}")


def read_json_member(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
    try:
        raw = archive.read(name)
    except KeyError as exc:
        raise DeliveryTrustCasePackConsumerError(f"Missing ZIP member: {name}") from exc
    text = raw.decode("utf-8", errors="replace")
    assert_no_private_text(text, label=name)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DeliveryTrustCasePackConsumerError(f"ZIP member is not valid JSON: {name}") from exc
    if not isinstance(payload, dict):
        raise DeliveryTrustCasePackConsumerError(f"ZIP member JSON must be an object: {name}")
    return payload


def validate_manifest_shape(manifest: dict[str, Any]) -> None:
    assert_metadata_only(manifest, label="manifest")
    expected = {
        "schema_version": PACK_SCHEMA_VERSION,
        "name": PACKAGE_NAME,
        "package_type": "delivery_trust_case_pack",
        "scenario_class": "controlled_customer_handoff",
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise DeliveryTrustCasePackConsumerError(f"manifest {key} drifted: expected {value!r}")
    if tuple(manifest.get("case_matrix", ())) != CASE_IDS:
        raise DeliveryTrustCasePackConsumerError("manifest case matrix drifted")
    trust_rules = manifest.get("trust_rules")
    if not isinstance(trust_rules, Mapping):
        raise DeliveryTrustCasePackConsumerError("manifest is missing trust_rules")
    for key in (
        "product_loop_required",
        "dual_loop_gate_required",
        "delivery_trust_receipt_required",
        "customer_handoff_package_required",
        "external_eval_receipts_supporting_only",
        "ai_review_only_rejected",
        "automatic_customer_sending_blocked",
        "production_mutation_blocked",
    ):
        if trust_rules.get(key) is not True:
            raise DeliveryTrustCasePackConsumerError(f"manifest trust rule must be true: {key}")
    boundary = manifest.get("claim_boundary")
    if not isinstance(boundary, Mapping):
        raise DeliveryTrustCasePackConsumerError("manifest is missing claim_boundary")
    not_claimed = set(boundary.get("not_claimed") or [])
    for item in ("production deployment approval", "real customer delivery", "customer outcome guarantee"):
        if item not in not_claimed:
            raise DeliveryTrustCasePackConsumerError(f"manifest claim boundary must reject {item}")


def validate_file_records(archive: zipfile.ZipFile, manifest: Mapping[str, Any]) -> list[str]:
    names = archive.namelist()
    for name in names:
        assert_safe_member(name)
        if not name.endswith(".zip"):
            assert_no_private_text(archive.read(name).decode("utf-8", errors="replace"), label=name)
    roots = {name.split("/", 1)[0] for name in names}
    if roots != {ARCHIVE_ROOT}:
        raise DeliveryTrustCasePackConsumerError(f"ZIP must have a single archive root: {sorted(roots)}")
    records = manifest.get("files")
    if not isinstance(records, list) or not records:
        raise DeliveryTrustCasePackConsumerError("manifest files must be a non-empty list")
    name_set = set(names)
    for record in records:
        if not isinstance(record, Mapping):
            raise DeliveryTrustCasePackConsumerError("manifest file records must be objects")
        archive_path = str(record.get("archive_path") or "")
        if archive_path not in name_set:
            raise DeliveryTrustCasePackConsumerError(f"recorded file is missing from ZIP: {archive_path}")
        if sha256_bytes(archive.read(archive_path)) != record.get("sha256"):
            raise DeliveryTrustCasePackConsumerError(f"recorded file hash mismatch: {archive_path}")
    for required in ("manifest.json", "CASE_PACK_README.md"):
        if f"{ARCHIVE_ROOT}/{required}" not in name_set:
            raise DeliveryTrustCasePackConsumerError(f"ZIP is missing {required}")
    return names


def load_case(archive: zipfile.ZipFile, case_id: str) -> dict[str, Any]:
    return read_json_member(
        archive,
        f"{ARCHIVE_ROOT}/fixtures/delivery-trust-case/{case_id}/delivery-trust-case.json",
    )


def validate_case(case_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    assert_metadata_only(payload, label=f"delivery_trust_case:{case_id}")
    if payload.get("schema_version") != "delivery-trust-case-v1":
        raise DeliveryTrustCasePackConsumerError(f"{case_id} schema_version drifted")
    expected = EXPECTED[case_id]
    if payload.get("status") != expected["status"]:
        raise DeliveryTrustCasePackConsumerError(f"{case_id} status drifted")
    decision = payload.get("decision")
    if decision != expected["decision"]:
        raise DeliveryTrustCasePackConsumerError(f"{case_id} decision drifted")
    reasons = set(payload.get("reasons") or [])
    if not expected["reasons"].issubset(reasons):
        raise DeliveryTrustCasePackConsumerError(f"{case_id} missing required reasons: {sorted(expected['reasons'] - reasons)}")
    if case_id == "pass" and reasons:
        raise DeliveryTrustCasePackConsumerError("pass case must not include block reasons")
    return {
        "case_id": case_id,
        "status": payload.get("status"),
        "decision": decision,
        "reasons": sorted(reasons),
        "artifact_count": len(payload.get("artifact_refs") or []),
    }


def consume_pack(pack_path: Path) -> dict[str, Any]:
    if not pack_path.is_file():
        raise DeliveryTrustCasePackConsumerError(f"Pack ZIP is missing: {pack_path.name}")
    try:
        archive = zipfile.ZipFile(pack_path)
    except zipfile.BadZipFile as exc:
        raise DeliveryTrustCasePackConsumerError("Pack is not a valid ZIP archive") from exc
    with archive:
        manifest_name = f"{ARCHIVE_ROOT}/manifest.json"
        manifest = read_json_member(archive, manifest_name)
        manifest_raw = archive.read(manifest_name)
        validate_manifest_shape(manifest)
        names = validate_file_records(archive, manifest)
        cases = [validate_case(case_id, load_case(archive, case_id)) for case_id in CASE_IDS]
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "purpose": "Verify external zip-only consumption of the Delivery Trust Case Pack.",
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
            {"step_id": "inspect_claim_boundary", "status": "pass", "evidence": "Claim boundary rejects production/customer overclaims."},
            {"step_id": "review_case_matrix", "status": "pass", "evidence": "Only the pass case allows controlled customer handoff."},
        ],
        "case_summary": {
            "delivery_trust_cases": cases,
            "allowed_case_count": sum(1 for case in cases if case["decision"] == "allow_controlled_customer_handoff"),
            "blocked_case_count": sum(1 for case in cases if case["decision"] == "block_customer_handoff"),
        },
        "decision": {
            "external_adopter_can_verify_zip_only": True,
            "allowed_customer_handoff_cases": ["pass"],
            "blocked_cases_remain_blocked": True,
            "ai_review_only_rejected": True,
            "production_mutation_blocked": True,
        },
        "privacy": {
            "metadata_only": True,
            "model_calls_performed": False,
            "daemon_or_hosted_service_started": False,
            "production_mutation_performed": False,
            "automatic_customer_sending_performed": False,
            "raw_source_text_included": False,
            "raw_report_text_included": False,
            "raw_customer_payload_included": False,
            "delivery_artifact_body_included": False,
            "screenshots_included": False,
            "keystrokes_included": False,
            "mouse_coordinates_included": False,
            "eye_tracking_or_biometrics_included": False,
            "real_secrets_included": False,
            "cookies_or_bearer_tokens_included": False,
            "signed_urls_included": False,
            "user_owned_agent_credentials_included": False,
        },
        "runtime_boundaries": {
            "repo_checkout_required_for_pack_mode": False,
            "api_required": False,
            "docker_required": False,
            "model_called": False,
            "daemon_started": False,
            "real_worktree_apply_executed": False,
            "source_files_modified": False,
        },
        "claim_boundary": manifest["claim_boundary"],
    }
    assert_metadata_only(report, label="delivery-trust-case-pack-consumer-walkthrough")
    return report


def write_zip(path: Path, entries: Mapping[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            info = zipfile.ZipInfo(name)
            info.date_time = (2026, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)


def rewrite_zip(zip_bytes: bytes, mutator: Callable[[dict[str, bytes]], None]) -> bytes:
    with tempfile.TemporaryDirectory(prefix="study-anything-delivery-trust-case-pack-") as tmp:
        root = Path(tmp)
        source = root / "source.zip"
        source.write_bytes(zip_bytes)
        entries: dict[str, bytes] = {}
        with zipfile.ZipFile(source) as archive:
            for name in archive.namelist():
                entries[name] = archive.read(name)
        mutator(entries)
        target = root / "target.zip"
        write_zip(target, entries)
        return target.read_bytes()


def mutate_manifest(zip_bytes: bytes, mutator: Callable[[dict[str, Any]], None]) -> bytes:
    def edit(entries: dict[str, bytes]) -> None:
        path = f"{ARCHIVE_ROOT}/manifest.json"
        manifest = json.loads(entries[path].decode("utf-8"))
        mutator(manifest)
        entries[path] = dump_json(manifest).encode("utf-8")

    return rewrite_zip(zip_bytes, edit)


def mutate_json_entry(
    zip_bytes: bytes,
    archive_path: str,
    mutator: Callable[[dict[str, Any]], None],
    *,
    update_manifest_hash: bool = False,
) -> bytes:
    def edit(entries: dict[str, bytes]) -> None:
        payload = json.loads(entries[archive_path].decode("utf-8"))
        mutator(payload)
        rendered = dump_json(payload).encode("utf-8")
        entries[archive_path] = rendered
        if update_manifest_hash:
            manifest_path = f"{ARCHIVE_ROOT}/manifest.json"
            manifest = json.loads(entries[manifest_path].decode("utf-8"))
            for record in manifest["files"]:
                if record.get("archive_path") == archive_path:
                    record["bytes"] = len(rendered)
                    record["sha256"] = sha256_bytes(rendered)
                    break
            entries[manifest_path] = dump_json(manifest).encode("utf-8")

    return rewrite_zip(zip_bytes, edit)


def expect_failure(name: str, zip_bytes: bytes) -> bool:
    with tempfile.TemporaryDirectory(prefix=f"study-anything-delivery-case-fail-{name}-") as tmp:
        pack = Path(tmp) / "pack.zip"
        pack.write_bytes(zip_bytes)
        try:
            consume_pack(pack)
        except DeliveryTrustCasePackConsumerError:
            return True
    raise RuntimeError(f"Unsafe or invalid Delivery Trust Case pack was not rejected: {name}")


def verify_failure_modes(ready_zip: bytes) -> dict[str, bool]:
    secret_value = "OPENAI_API_KEY=" + "sk-" + "proj-" + "abcdefghijklmnop"

    def disable_trust_rule(payload: dict[str, Any]) -> None:
        payload["trust_rules"]["product_loop_required"] = False

    def privacy_regression(payload: dict[str, Any]) -> None:
        payload["privacy_boundaries"]["production_mutation_performed"] = True

    def secret_like(payload: dict[str, Any]) -> None:
        payload["summary"] = secret_value

    def unsafe_path(entries: dict[str, bytes]) -> None:
        entries["../outside.json"] = b"{}\n"

    def missing_manifest(entries: dict[str, bytes]) -> None:
        entries.pop(f"{ARCHIVE_ROOT}/manifest.json")

    def missing_case(entries: dict[str, bytes]) -> None:
        entries.pop(f"{ARCHIVE_ROOT}/fixtures/delivery-trust-case/blocked-dual-loop/delivery-trust-case.json")

    def blocked_case_allowed(payload: dict[str, Any]) -> None:
        payload["status"] = "ready_for_controlled_customer_handoff"
        payload["decision"] = "allow_controlled_customer_handoff"
        payload["reasons"] = []

    blocked_case = f"{ARCHIVE_ROOT}/fixtures/delivery-trust-case/blocked-dual-loop/delivery-trust-case.json"
    return {
        "tampered_zip_rejected": expect_failure("tampered_zip", b"not-a-zip"),
        "unsafe_zip_path_rejected": expect_failure("unsafe_zip_path", rewrite_zip(ready_zip, unsafe_path)),
        "missing_manifest_rejected": expect_failure("missing_manifest", rewrite_zip(ready_zip, missing_manifest)),
        "missing_case_rejected": expect_failure("missing_case", rewrite_zip(ready_zip, missing_case)),
        "hash_mismatch_rejected": expect_failure(
            "hash_mismatch",
            mutate_json_entry(ready_zip, blocked_case, blocked_case_allowed),
        ),
        "trust_rule_disabled_rejected": expect_failure(
            "trust_rule_disabled",
            mutate_manifest(ready_zip, disable_trust_rule),
        ),
        "privacy_regression_rejected": expect_failure(
            "privacy_regression",
            mutate_manifest(ready_zip, privacy_regression),
        ),
        "secret_like_text_rejected": expect_failure(
            "secret_like_text",
            mutate_manifest(ready_zip, secret_like),
        ),
        "blocked_case_semantics_rejected": expect_failure(
            "blocked_case_semantics",
            mutate_json_entry(ready_zip, blocked_case, blocked_case_allowed, update_manifest_hash=True),
        ),
    }


def build_report(pack_path: Path) -> dict[str, Any]:
    consumed = consume_pack(pack_path)
    failures = verify_failure_modes(pack_path.read_bytes())
    report = {
        **consumed,
        "consumer": {
            "script": "scripts/verify_delivery_trust_case_pack_consumer_walkthrough.py",
            "command": (
                "python3 scripts/verify_delivery_trust_case_pack_consumer_walkthrough.py "
                "--pack platform/generated/study-anything-delivery-trust-case-pack.zip"
            ),
            "zip_only": True,
            "repo_checkout_required_for_pack_mode": False,
        },
        "failure_modes": failures,
    }
    assert_metadata_only(report, label="delivery-trust-case-pack-consumer-report")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", help="Path to the Delivery Trust Case pack ZIP.")
    parser.add_argument("--write", action="store_true", help="Write generated consumer walkthrough report.")
    parser.add_argument("--check", action="store_true", help="Require generated report to be up to date.")
    parser.add_argument("--output", default=str(REPORT), help="Report path for --write/--check.")
    args = parser.parse_args()
    try:
        pack = Path(args.pack) if args.pack else ARCHIVE_PATH
        if not pack.is_absolute():
            pack = ROOT / pack
        if args.pack and not args.write and not args.check:
            print(dump_json(consume_pack(pack)), end="")
            return 0
        report = build_report(pack)
        rendered = dump_json(report)
        output = Path(args.output)
        if not output.is_absolute():
            output = ROOT / output
        if args.write:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(rendered, encoding="utf-8")
            print(f"wrote {output.relative_to(ROOT)}")
            return 0
        if args.check:
            current = output.read_text(encoding="utf-8") if output.is_file() else ""
            if current != rendered:
                raise SystemExit(
                    "generated Delivery Trust Case pack consumer walkthrough is stale; run with --write"
                )
            print("ok    Delivery Trust Case pack consumer walkthrough report is up to date")
            return 0
        print(rendered, end="")
        return 0
    except DeliveryTrustCasePackConsumerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
