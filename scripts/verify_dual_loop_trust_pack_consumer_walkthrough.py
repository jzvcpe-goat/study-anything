#!/usr/bin/env python3
"""Verify a Dual Loop Trust Scenario Pack from the ZIP alone."""

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

from generate_dual_loop_trust_scenario_pack import (
    ARCHIVE_PATH,
    ARCHIVE_ROOT,
    PACKAGE_NAME,
    ROOT,
    SCHEMA_VERSION as PACK_SCHEMA_VERSION,
)


REPORT = ROOT / "platform" / "generated" / "study-anything-dual-loop-trust-pack-consumer-walkthrough.json"
SCHEMA_VERSION = "dual-loop-trust-pack-consumer-walkthrough-v1"
REQUIRED_DUAL_LOOP_CASES = ("pass", "attention-missing", "risk-over-budget", "both-fail")
REQUIRED_CBB_CASES = (
    "pass",
    "blocked-missing-developer-reconstruction",
    "blocked-risk-over-budget",
    "blocked-external-scope-expansion",
    "blocked-stale-receipt-chain",
    "blocked-ai-review-only",
)
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
    "automatic_customer_sending_performed",
    "bearer_tokens_included",
    "biometrics_included",
    "client_secrets_included",
    "cookies_included",
    "cookies_or_bearer_tokens_included",
    "customer_payload_included",
    "daemon_or_hosted_service_started",
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


class TrustPackConsumerError(RuntimeError):
    """Readable trust-pack consumer verification failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def assert_no_private_text(text: str, *, label: str) -> None:
    for pattern in SECRET_PATTERNS:
        match = pattern.search(text)
        if match:
            raise TrustPackConsumerError(
                f"{label} contains private-looking text: {match.group(0)[:80]}"
            )


def assert_public_payload(payload: Any, *, label: str) -> None:
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, sort_keys=True)
    assert_no_private_text(text, label=label)


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
        raise TrustPackConsumerError(f"{label} has privacy regressions: {sorted(set(regressions))}")
    assert_public_payload(payload, label=label)


def assert_safe_member(name: str) -> None:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise TrustPackConsumerError(f"Unsafe ZIP member path: {name}")
    if any(part in FORBIDDEN_PATH_PARTS for part in path.parts):
        raise TrustPackConsumerError(f"Forbidden ZIP member path part in: {name}")
    if not name.startswith(f"{ARCHIVE_ROOT}/"):
        raise TrustPackConsumerError(f"ZIP member is outside archive root: {name}")


def read_json_member(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
    try:
        raw = archive.read(name)
    except KeyError as exc:
        raise TrustPackConsumerError(f"Missing ZIP member: {name}") from exc
    text = raw.decode("utf-8", errors="replace")
    assert_no_private_text(text, label=name)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise TrustPackConsumerError(f"ZIP member is not valid JSON: {name}") from exc
    if not isinstance(payload, dict):
        raise TrustPackConsumerError(f"ZIP member JSON must be an object: {name}")
    return payload


def validate_manifest_shape(manifest: dict[str, Any]) -> None:
    assert_metadata_only(manifest, label="manifest")
    expected = {
        "schema_version": PACK_SCHEMA_VERSION,
        "name": PACKAGE_NAME,
        "package_type": "dual_loop_trust_scenario_pack",
        "scenario_class": "customer_delivery_readiness",
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise TrustPackConsumerError(f"manifest {key} drifted: expected {value!r}")

    privacy = manifest.get("privacy_boundaries")
    if not isinstance(privacy, Mapping) or privacy.get("metadata_only") is not True:
        raise TrustPackConsumerError("manifest must assert metadata-only privacy")
    for key in FORBIDDEN_TRUE_FLAGS:
        if privacy.get(key) is True:
            raise TrustPackConsumerError(f"manifest privacy flag must not be true: {key}")

    trust_rules = manifest.get("trust_rules")
    if not isinstance(trust_rules, Mapping):
        raise TrustPackConsumerError("manifest is missing trust_rules")
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
            raise TrustPackConsumerError(f"manifest trust rule must be true: {key}")

    matrix = manifest.get("case_matrix")
    if not isinstance(matrix, Mapping):
        raise TrustPackConsumerError("manifest is missing case_matrix")
    if tuple(matrix.get("dual_loop", ())) != REQUIRED_DUAL_LOOP_CASES:
        raise TrustPackConsumerError("manifest dual_loop case matrix drifted")
    if tuple(matrix.get("cbb_delivery", ())) != REQUIRED_CBB_CASES:
        raise TrustPackConsumerError("manifest cbb_delivery case matrix drifted")

    boundary = manifest.get("claim_boundary")
    if not isinstance(boundary, Mapping):
        raise TrustPackConsumerError("manifest is missing claim_boundary")
    not_claimed = set(boundary.get("not_claimed") or [])
    if "production deployment approval" not in not_claimed or "real customer acceptance" not in not_claimed:
        raise TrustPackConsumerError("manifest claim boundary must reject production and customer-acceptance overclaims")


def validate_file_records(archive: zipfile.ZipFile, manifest: Mapping[str, Any]) -> list[str]:
    names = archive.namelist()
    for name in names:
        assert_safe_member(name)
        data = archive.read(name)
        if not name.endswith(".zip"):
            assert_no_private_text(data.decode("utf-8", errors="replace"), label=name)
    roots = {name.split("/", 1)[0] for name in names}
    if roots != {ARCHIVE_ROOT}:
        raise TrustPackConsumerError(f"ZIP must have a single archive root: {sorted(roots)}")

    records = manifest.get("files")
    if not isinstance(records, list) or not records:
        raise TrustPackConsumerError("manifest files must be a non-empty list")
    name_set = set(names)
    for record in records:
        if not isinstance(record, Mapping):
            raise TrustPackConsumerError("manifest file records must be objects")
        archive_path = str(record.get("archive_path") or "")
        if archive_path not in name_set:
            raise TrustPackConsumerError(f"recorded file is missing from ZIP: {archive_path}")
        if sha256_bytes(archive.read(archive_path)) != record.get("sha256"):
            raise TrustPackConsumerError(f"recorded file hash mismatch: {archive_path}")
    if f"{ARCHIVE_ROOT}/manifest.json" not in name_set:
        raise TrustPackConsumerError("ZIP is missing manifest.json")
    if f"{ARCHIVE_ROOT}/SCENARIO_PACK_README.md" not in name_set:
        raise TrustPackConsumerError("ZIP is missing SCENARIO_PACK_README.md")
    return names


def has_member(archive: zipfile.ZipFile, relative: str) -> bool:
    return f"{ARCHIVE_ROOT}/{relative}" in archive.namelist()


def load_case_result(archive: zipfile.ZipFile, case_id: str) -> dict[str, Any]:
    return read_json_member(
        archive,
        f"{ARCHIVE_ROOT}/fixtures/dual-loop-scenarios/{case_id}/scenario-result.json",
    )


def load_cbb_run(archive: zipfile.ZipFile, case_id: str) -> dict[str, Any]:
    return read_json_member(
        archive,
        f"{ARCHIVE_ROOT}/fixtures/cbb-delivery-harness/{case_id}/tri-loop-run.json",
    )


def validate_dual_loop_cases(archive: zipfile.ZipFile) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for case_id in REQUIRED_DUAL_LOOP_CASES:
        result = load_case_result(archive, case_id)
        assert_metadata_only(result, label=f"dual_loop_case:{case_id}")
        observed = result.get("observed")
        expected = result.get("expected")
        isolation = result.get("isolation")
        if not isinstance(observed, Mapping) or not isinstance(expected, Mapping):
            raise TrustPackConsumerError(f"{case_id} scenario result missing observed/expected")
        if not isinstance(isolation, Mapping) or isolation.get("structured_artifact_bridge_only") is not True:
            raise TrustPackConsumerError(f"{case_id} must preserve the structured artifact bridge")

        package_member = f"fixtures/dual-loop-scenarios/{case_id}/customer-handoff-package.json"
        package_exists = has_member(archive, package_member)
        if case_id == "pass":
            if observed.get("dual_loop_gate_status") != "allowed":
                raise TrustPackConsumerError("pass case must allow the Dual Loop gate")
            if observed.get("delivery_trust_status") != "allowed":
                raise TrustPackConsumerError("pass case must allow delivery trust")
            if observed.get("customer_handoff_package_emitted") is not True or not package_exists:
                raise TrustPackConsumerError("pass case must emit a customer handoff package")
        else:
            if observed.get("dual_loop_gate_status") != "blocked":
                raise TrustPackConsumerError(f"{case_id} must block the Dual Loop gate")
            if observed.get("delivery_trust_status") != "blocked":
                raise TrustPackConsumerError(f"{case_id} must block delivery trust")
            if observed.get("customer_handoff_package_emitted") is not False or package_exists:
                raise TrustPackConsumerError(f"{case_id} must not emit a customer handoff package")
            reasons = set(observed.get("gate_reasons") or []) | set(observed.get("delivery_reasons") or [])
            for reason in expected.get("required_reasons") or []:
                if reason not in reasons:
                    raise TrustPackConsumerError(f"{case_id} missing required block reason: {reason}")

        summaries.append(
            {
                "case_id": case_id,
                "dual_loop_gate_status": observed.get("dual_loop_gate_status"),
                "delivery_trust_status": observed.get("delivery_trust_status"),
                "customer_handoff_package_emitted": observed.get("customer_handoff_package_emitted"),
                "artifact_count": len(result.get("artifact_refs") or []),
            }
        )
    return summaries


def validate_cbb_cases(archive: zipfile.ZipFile) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for case_id in REQUIRED_CBB_CASES:
        run = load_cbb_run(archive, case_id)
        assert_metadata_only(run, label=f"cbb_case:{case_id}")
        parity = run.get("loop_parity")
        statuses = run.get("loop_statuses")
        if not isinstance(parity, Mapping) or parity.get("neither_loop_may_dominate") is not True:
            raise TrustPackConsumerError(f"{case_id} must keep loop parity")
        if not isinstance(statuses, Mapping):
            raise TrustPackConsumerError(f"{case_id} is missing loop_statuses")
        decision = run.get("decision")
        if case_id == "pass":
            if decision != "promote_next_sandbox_level":
                raise TrustPackConsumerError("CBB pass case must promote to the next sandbox level")
            if set(statuses.values()) != {"passed"}:
                raise TrustPackConsumerError("CBB pass case must have every loop passed")
        elif decision != "block_delivery_scenario":
            raise TrustPackConsumerError(f"CBB {case_id} must block delivery")
        summaries.append(
            {
                "case_id": case_id,
                "decision": decision,
                "agentic_loop": statuses.get("agentic_coding_loop"),
                "developer_loop": statuses.get("developer_feedback_loop"),
                "external_loop": statuses.get("external_feedback_loop"),
            }
        )
    return summaries


def consume_pack(pack_path: Path) -> dict[str, Any]:
    if not pack_path.is_file():
        raise TrustPackConsumerError(f"Pack ZIP is missing: {pack_path.name}")
    try:
        archive = zipfile.ZipFile(pack_path)
    except zipfile.BadZipFile as exc:
        raise TrustPackConsumerError("Pack is not a valid ZIP archive") from exc
    with archive:
        manifest_name = f"{ARCHIVE_ROOT}/manifest.json"
        manifest = read_json_member(archive, manifest_name)
        manifest_raw = archive.read(manifest_name)
        validate_manifest_shape(manifest)
        names = validate_file_records(archive, manifest)
        dual_loop_cases = validate_dual_loop_cases(archive)
        cbb_cases = validate_cbb_cases(archive)

    blocked_dual_loop = [case for case in dual_loop_cases if case["dual_loop_gate_status"] == "blocked"]
    blocked_cbb = [case for case in cbb_cases if case["decision"] == "block_delivery_scenario"]
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "purpose": "Verify external zip-only consumption of the Dual Loop Trust Scenario Pack.",
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
            {
                "step_id": "download_pack",
                "status": "pass",
                "evidence": "ZIP is valid and has one archive root.",
            },
            {
                "step_id": "verify_manifest_and_hashes",
                "status": "pass",
                "evidence": "Manifest file records match archive members and SHA-256 hashes.",
            },
            {
                "step_id": "inspect_claim_boundary",
                "status": "pass",
                "evidence": "Claim boundary rejects production deployment approval and real customer acceptance.",
            },
            {
                "step_id": "review_dual_loop_cases",
                "status": "pass",
                "evidence": "Only the pass case emits a customer handoff package.",
            },
            {
                "step_id": "review_cbb_delivery_cases",
                "status": "pass",
                "evidence": "Only the CBB pass case promotes to the next sandbox level.",
            },
        ],
        "case_summary": {
            "dual_loop": dual_loop_cases,
            "cbb_delivery": cbb_cases,
            "customer_handoff_allowed_case_count": 1,
            "blocked_case_count": len(blocked_dual_loop) + len(blocked_cbb),
        },
        "decision": {
            "external_adopter_can_rehearse": True,
            "allowed_customer_handoff_cases": ["pass"],
            "blocked_cases_remain_blocked": True,
            "neither_loop_may_dominate": True,
        },
        "privacy": {
            "metadata_only": True,
            "model_calls_performed": False,
            "daemon_or_hosted_service_started": False,
            "production_mutation_performed": False,
            "raw_source_text_included": False,
            "raw_report_text_included": False,
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
    assert_metadata_only(report, label="dual-loop-trust-pack-consumer-walkthrough")
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
    with tempfile.TemporaryDirectory(prefix="study-anything-dual-loop-pack-tamper-") as tmp:
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
    with tempfile.TemporaryDirectory(prefix=f"study-anything-dual-loop-consumer-fail-{name}-") as tmp:
        pack = Path(tmp) / "pack.zip"
        pack.write_bytes(zip_bytes)
        try:
            consume_pack(pack)
        except TrustPackConsumerError:
            return True
    raise RuntimeError(f"Unsafe or invalid Dual Loop trust pack was not rejected: {name}")


def verify_failure_modes(ready_zip: bytes) -> dict[str, bool]:
    secret_value = "OPENAI_API_KEY=" + "sk-" + "proj-" + "abcdefghijklmnop"

    def disable_trust_rule(payload: dict[str, Any]) -> None:
        payload["trust_rules"]["human_attention_reconstruction_required"] = False

    def privacy_regression(payload: dict[str, Any]) -> None:
        payload["privacy_boundaries"]["model_calls_performed"] = True

    def secret_like(payload: dict[str, Any]) -> None:
        payload["summary"] = secret_value

    def unsafe_path(entries: dict[str, bytes]) -> None:
        entries["../outside.json"] = b"{}\n"

    def missing_manifest(entries: dict[str, bytes]) -> None:
        entries.pop(f"{ARCHIVE_ROOT}/manifest.json")

    def missing_case(entries: dict[str, bytes]) -> None:
        entries.pop(f"{ARCHIVE_ROOT}/fixtures/dual-loop-scenarios/attention-missing/scenario-result.json")

    def blocked_handoff(payload: dict[str, Any]) -> None:
        payload["observed"]["customer_handoff_package_emitted"] = True

    attention_result = (
        f"{ARCHIVE_ROOT}/fixtures/dual-loop-scenarios/attention-missing/scenario-result.json"
    )
    return {
        "tampered_zip_rejected": expect_failure("tampered_zip", b"not-a-zip"),
        "unsafe_zip_path_rejected": expect_failure("unsafe_zip_path", rewrite_zip(ready_zip, unsafe_path)),
        "missing_manifest_rejected": expect_failure("missing_manifest", rewrite_zip(ready_zip, missing_manifest)),
        "missing_case_rejected": expect_failure("missing_case", rewrite_zip(ready_zip, missing_case)),
        "hash_mismatch_rejected": expect_failure(
            "hash_mismatch",
            mutate_json_entry(ready_zip, attention_result, blocked_handoff),
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
        "blocked_handoff_semantics_rejected": expect_failure(
            "blocked_handoff_semantics",
            mutate_json_entry(ready_zip, attention_result, blocked_handoff, update_manifest_hash=True),
        ),
    }


def build_report(pack_path: Path) -> dict[str, Any]:
    consumed = consume_pack(pack_path)
    failures = verify_failure_modes(pack_path.read_bytes())
    report = {
        **consumed,
        "consumer": {
            "script": "scripts/verify_dual_loop_trust_pack_consumer_walkthrough.py",
            "command": (
                "python3 scripts/verify_dual_loop_trust_pack_consumer_walkthrough.py "
                "--pack platform/generated/study-anything-dual-loop-trust-scenario-pack.zip"
            ),
            "zip_only": True,
            "repo_checkout_required_for_pack_mode": False,
        },
        "failure_modes": failures,
    }
    assert_metadata_only(report, label="dual-loop-trust-pack-consumer-report")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", help="Path to the Dual Loop trust scenario pack ZIP.")
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
                    "generated Dual Loop trust pack consumer walkthrough is stale; run with --write"
                )
            print("ok    Dual Loop trust pack consumer walkthrough report is up to date")
            return 0
        print(rendered, end="")
        return 0
    except TrustPackConsumerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
