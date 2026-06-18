#!/usr/bin/env python3
"""Verify Cognitive Loop schema pack consumer failure cases are safe and deterministic."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Callable

import verify_cognitive_loop_schema_pack_consumer as consumer


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-schema-pack-consumer-failures.json"
SCHEMA_VERSION = "cognitive-loop-schema-pack-consumer-failures-v1"
PRIVATE_REDACTION = "<redacted-private-needle>"


class SchemaPackConsumerFailureError(RuntimeError):
    """Readable schema pack consumer failure verification error."""


PackFiles = dict[str, bytes]
Mutator = Callable[[PackFiles], None]


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def archive_path(relative: str) -> str:
    return consumer.archive_path(relative)


def load_pack_files(pack_path: Path) -> PackFiles:
    with zipfile.ZipFile(pack_path) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def read_json(files: PackFiles, path: str) -> dict[str, Any]:
    try:
        return json.loads(files[path].decode("utf-8"))
    except KeyError as exc:
        raise SchemaPackConsumerFailureError(f"Missing fixture source file: {path}") from exc


def write_json(files: PackFiles, path: str, payload: dict[str, Any]) -> bytes:
    raw = dump_json(payload).encode("utf-8")
    files[path] = raw
    return raw


def update_manifest_record(manifest: dict[str, Any], path: str, raw: bytes) -> None:
    files = manifest.get("files")
    if not isinstance(files, list):
        raise SchemaPackConsumerFailureError("Manifest files must be a list.")
    matches = [item for item in files if isinstance(item, dict) and item.get("path") == path]
    if len(matches) != 1:
        raise SchemaPackConsumerFailureError(f"Manifest must include one record for {path}.")
    matches[0]["bytes"] = len(raw)
    matches[0]["sha256"] = sha256_bytes(raw)


def write_mutated_pack(path: Path, files: PackFiles) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, files[name])


def mutate_manifest_schema_drift(files: PackFiles) -> None:
    manifest = read_json(files, consumer.MANIFEST_ARCHIVE_PATH)
    manifest["schema_version"] = "study-anything-platform-adoption-pack-v0"
    write_json(files, consumer.MANIFEST_ARCHIVE_PATH, manifest)


def mutate_schema_bundle_missing(files: PackFiles) -> None:
    files.pop(archive_path(consumer.SCHEMA_BUNDLE_PATH), None)


def mutate_schema_bundle_hash_drift(files: PackFiles) -> None:
    schema_path = archive_path(consumer.SCHEMA_BUNDLE_PATH)
    schema_bundle = read_json(files, schema_path)
    schema_bundle["safe_tamper_probe"] = "hash drift should be rejected"
    write_json(files, schema_path, schema_bundle)


def mutate_no_frontend_false(files: PackFiles) -> None:
    manifest = read_json(files, consumer.MANIFEST_ARCHIVE_PATH)
    manifest["no_frontend_required"] = False
    write_json(files, consumer.MANIFEST_ARCHIVE_PATH, manifest)


def mutate_real_model_keys_true(files: PackFiles) -> None:
    manifest = read_json(files, consumer.MANIFEST_ARCHIVE_PATH)
    manifest["real_model_keys_stored_by_study_anything"] = True
    write_json(files, consumer.MANIFEST_ARCHIVE_PATH, manifest)


def mutate_negative_fixture_case_drop(files: PackFiles) -> None:
    manifest = read_json(files, consumer.MANIFEST_ARCHIVE_PATH)
    fixture_path = archive_path(consumer.NEGATIVE_FIXTURE_PATH)
    negative = read_json(files, fixture_path)
    coverage = negative.setdefault("coverage", {})
    case_ids = list(coverage.get("case_ids", []))
    if case_ids:
        case_ids.pop()
    coverage["case_ids"] = case_ids
    coverage["case_count"] = len(case_ids)
    raw = write_json(files, fixture_path, negative)
    update_manifest_record(manifest, consumer.NEGATIVE_FIXTURE_PATH, raw)
    write_json(files, consumer.MANIFEST_ARCHIVE_PATH, manifest)


def mutate_private_text_probe(files: PackFiles) -> None:
    manifest = read_json(files, consumer.MANIFEST_ARCHIVE_PATH)
    schema_path = archive_path(consumer.SCHEMA_BUNDLE_PATH)
    schema_bundle = read_json(files, schema_path)
    schema_bundle["safe_private_probe"] = "sk-proj-test-value"
    raw = write_json(files, schema_path, schema_bundle)
    update_manifest_record(manifest, consumer.SCHEMA_BUNDLE_PATH, raw)
    write_json(files, consumer.MANIFEST_ARCHIVE_PATH, manifest)


def mutate_runtime_started_true(files: PackFiles) -> None:
    manifest = read_json(files, consumer.MANIFEST_ARCHIVE_PATH)
    schema_path = archive_path(consumer.SCHEMA_BUNDLE_PATH)
    schema_bundle = read_json(files, schema_path)
    validation = schema_bundle.setdefault("validation", {})
    validation["runtime_started"] = True
    raw = write_json(files, schema_path, schema_bundle)
    update_manifest_record(manifest, consumer.SCHEMA_BUNDLE_PATH, raw)
    write_json(files, consumer.MANIFEST_ARCHIVE_PATH, manifest)


FAILURE_CASES: tuple[dict[str, Any], ...] = (
    {
        "case_id": "manifest_schema_version_drift",
        "mutation": "Change the adoption pack manifest schema version.",
        "expected_error": "manifest schema drifted",
        "mutator": mutate_manifest_schema_drift,
    },
    {
        "case_id": "schema_bundle_missing",
        "mutation": "Remove the recipe CLI schema bundle from the zip.",
        "expected_error": "missing schema consumer files",
        "mutator": mutate_schema_bundle_missing,
    },
    {
        "case_id": "schema_bundle_manifest_record_drift",
        "mutation": "Change the schema bundle without updating the manifest record.",
        "expected_error": "byte count drifted",
        "mutator": mutate_schema_bundle_hash_drift,
    },
    {
        "case_id": "no_frontend_required_false",
        "mutation": "Change no_frontend_required to false.",
        "expected_error": "no-frontend required",
        "mutator": mutate_no_frontend_false,
    },
    {
        "case_id": "real_model_keys_true",
        "mutation": "Change real_model_keys_stored_by_study_anything to true.",
        "expected_error": "must not store real model keys",
        "mutator": mutate_real_model_keys_true,
    },
    {
        "case_id": "negative_fixture_case_drop",
        "mutation": "Drop one negative fixture case while keeping manifest hashes coherent.",
        "expected_error": "case count drifted",
        "mutator": mutate_negative_fixture_case_drop,
    },
    {
        "case_id": "private_text_probe_rejected",
        "mutation": "Inject a private secret-like probe while keeping manifest hashes coherent.",
        "expected_error": "contains private or secret-like text",
        "mutator": mutate_private_text_probe,
    },
    {
        "case_id": "runtime_started_true",
        "mutation": "Change schema bundle validation.runtime_started to true.",
        "expected_error": "validation.runtime_started must be false",
        "mutator": mutate_runtime_started_true,
    },
)


def redact_error(text: str) -> str:
    redacted = text.replace(str(ROOT), "<repo>")
    for needle in consumer.PRIVATE_NEEDLES:
        redacted = redacted.replace(needle, PRIVATE_REDACTION)
        redacted = redacted.replace(needle.upper(), PRIVATE_REDACTION)
    return redacted


def run_failure_case(
    *,
    case: dict[str, Any],
    original_files: PackFiles,
    tmp_dir: Path,
) -> dict[str, Any]:
    files = copy.deepcopy(original_files)
    case_id = str(case["case_id"])
    mutator: Mutator = case["mutator"]
    mutator(files)
    mutated_pack = tmp_dir / f"{case_id}.zip"
    write_mutated_pack(mutated_pack, files)
    try:
        consumer.build_report(mutated_pack)
    except Exception as exc:  # noqa: BLE001 - every consumer failure path should be classified.
        raw_error = str(exc)
        expected_error = str(case["expected_error"])
        if expected_error not in raw_error:
            raise SchemaPackConsumerFailureError(
                f"{case_id} failed with unexpected error: {redact_error(raw_error)}"
            ) from exc
        redacted_error = redact_error(raw_error)
        consumer.reject_private_text(redacted_error, label=f"{case_id} redacted error")
        return {
            "case_id": case_id,
            "status": "pass",
            "mutation": case["mutation"],
            "expected_error": expected_error,
            "actual_error_redacted": redacted_error,
            "error_redacted": True,
            "mutated_payload_persisted": False,
        }
    raise SchemaPackConsumerFailureError(f"{case_id} unexpectedly passed.")


def build_report(pack_path: Path) -> dict[str, Any]:
    if not pack_path.is_file():
        raise SchemaPackConsumerFailureError(f"Adoption pack is missing: {pack_path}")
    baseline = consumer.build_report(pack_path)
    original_files = load_pack_files(pack_path)
    with tempfile.TemporaryDirectory(prefix="study-anything-schema-pack-failures-") as tmp:
        tmp_dir = Path(tmp)
        results = [
            run_failure_case(case=case, original_files=original_files, tmp_dir=tmp_dir)
            for case in FAILURE_CASES
        ]

    case_ids = [result["case_id"] for result in results]
    if len(set(case_ids)) != len(case_ids):
        raise SchemaPackConsumerFailureError("Failure case IDs must be unique.")
    if any(result.get("status") != "pass" for result in results):
        raise SchemaPackConsumerFailureError("All failure cases must pass.")
    if any(result.get("mutated_payload_persisted") is not False for result in results):
        raise SchemaPackConsumerFailureError("Failure cases must not persist mutated payloads.")

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "purpose": "Prove the adoption-pack schema consumer rejects tampered or policy-violating zip variants safely.",
        "pack": {
            "path": relative_path(pack_path),
            "manifest_schema_version": baseline["pack"]["manifest_schema_version"],
            "file_count": baseline["pack"]["file_count"],
            "no_frontend_required": True,
            "real_model_keys_stored_by_study_anything": False,
        },
        "baseline": {
            "consumer_schema_version": baseline["schema_version"],
            "schema_bundle_schema_version": baseline["schema_bundle"]["schema_version"],
            "negative_fixture_schema_version": baseline["negative_fixtures"]["schema_version"],
            "zip_only_validation_passed": True,
        },
        "coverage": {
            "case_count": len(results),
            "case_ids": case_ids,
            "all_cases_rejected": True,
            "all_expected_errors_matched": True,
            "all_errors_redacted": True,
            "mutated_payloads_persisted": False,
            "mutated_archives_persisted": False,
            "repo_checkout_required": False,
            "recipe_cli_invoked": False,
            "runtime_started": False,
            "file_changes_applied": False,
        },
        "cases": results,
        "distribution": {
            "report_path": REPORT.relative_to(ROOT).as_posix(),
            "verification_command": "python3 scripts/verify_cognitive_loop_schema_pack_consumer_failures.py --check",
            "safe_for_platform_agent_static_import": True,
        },
        "privacy": {
            "raw_source_text_included": False,
            "diff_bodies_included": False,
            "learner_answers_included": False,
            "grading_feedback_included": False,
            "generated_private_insights_included": False,
            "agent_endpoints_included": False,
            "agent_metadata_included": False,
            "real_model_keys_stored": False,
            "browser_video_app_private_context_included": False,
            "mutated_payloads_included": False,
        },
    }
    consumer.reject_private_text(dump_json(report), label="schema pack consumer failure report")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--pack", default=str(consumer.ADOPTION_PACK))
    parser.add_argument("--output", default=str(REPORT))
    args = parser.parse_args()

    output = Path(args.output)
    pack_path = Path(args.pack)
    if not pack_path.is_absolute():
        pack_path = ROOT / pack_path
    serialized = dump_json(build_report(pack_path))
    if args.write:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
    if args.check:
        if not output.is_file():
            raise SystemExit(f"Cognitive Loop schema pack consumer failure report is missing: {output}")
        current = output.read_text(encoding="utf-8")
        if current != serialized:
            raise SystemExit(
                "Cognitive Loop schema pack consumer failure report is stale. "
                "Run: python3 scripts/verify_cognitive_loop_schema_pack_consumer_failures.py --write"
            )
    if not args.write and not args.check:
        print(serialized, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_cognitive_loop_schema_pack_consumer_failures failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
