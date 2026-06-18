#!/usr/bin/env python3
"""Verify Cognitive Loop schema evidence can be consumed from the adoption pack only."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ADOPTION_PACK = ROOT / "platform" / "generated" / "study-anything-platform-adoption-pack.zip"
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-schema-pack-consumer.json"
ARCHIVE_ROOT = "study-anything-platform-adoption-pack"
MANIFEST_ARCHIVE_PATH = f"{ARCHIVE_ROOT}/manifest.json"
SCHEMA_BUNDLE_PATH = "platform/generated/study-anything-cognitive-loop-recipe-cli-schemas.json"
NEGATIVE_FIXTURE_PATH = (
    "platform/generated/study-anything-cognitive-loop-recipe-cli-schema-negative-fixtures.json"
)
SCHEMA_VERSION = "cognitive-loop-schema-pack-consumer-v1"
PRIVATE_NEEDLES = (
    "sk-proj-",
    "bearer ",
    "api_key",
    "secret_access_key",
    "raw private source text",
    "learner answer:",
    "http://127.0.0.1:8787/",
)


class SchemaPackConsumerError(RuntimeError):
    """Readable schema pack consumer verification failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def reject_private_text(value: str, *, label: str) -> None:
    lowered = value.lower()
    leaked = [needle for needle in PRIVATE_NEEDLES if needle in lowered]
    if leaked:
        raise SchemaPackConsumerError(f"{label} contains private or secret-like text: {leaked}")


def archive_path(relative: str) -> str:
    return f"{ARCHIVE_ROOT}/{relative}"


def read_json_from_zip(archive: zipfile.ZipFile, path: str) -> dict[str, Any]:
    try:
        raw = archive.read(path)
    except KeyError as exc:
        raise SchemaPackConsumerError(f"Adoption pack is missing {path}") from exc
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise SchemaPackConsumerError(f"{path} is not valid JSON: {exc}") from exc


def manifest_record(manifest: dict[str, Any], path: str) -> dict[str, Any]:
    files = manifest.get("files")
    if not isinstance(files, list):
        raise SchemaPackConsumerError("Adoption pack manifest files must be a list.")
    matches = [item for item in files if isinstance(item, dict) and item.get("path") == path]
    if len(matches) != 1:
        raise SchemaPackConsumerError(f"Adoption pack manifest must include exactly one record for {path}.")
    return matches[0]


def assert_zip_record_matches(
    archive: zipfile.ZipFile,
    *,
    record: dict[str, Any],
    expected_path: str,
) -> bytes:
    expected_archive_path = archive_path(expected_path)
    if record.get("archive_path") != expected_archive_path:
        raise SchemaPackConsumerError(f"{expected_path} archive_path drifted.")
    raw = archive.read(expected_archive_path)
    if record.get("bytes") != len(raw):
        raise SchemaPackConsumerError(f"{expected_path} byte count drifted.")
    if record.get("sha256") != sha256_bytes(raw):
        raise SchemaPackConsumerError(f"{expected_path} sha256 drifted.")
    return raw


def build_report(pack_path: Path) -> dict[str, Any]:
    if not pack_path.is_file():
        raise SchemaPackConsumerError(f"Adoption pack is missing: {pack_path}")
    with zipfile.ZipFile(pack_path) as archive:
        names = set(archive.namelist())
        required_archive_paths = {
            MANIFEST_ARCHIVE_PATH,
            archive_path(SCHEMA_BUNDLE_PATH),
            archive_path(NEGATIVE_FIXTURE_PATH),
        }
        missing = sorted(required_archive_paths - names)
        if missing:
            raise SchemaPackConsumerError(f"Adoption pack is missing schema consumer files: {missing}")

        manifest = read_json_from_zip(archive, MANIFEST_ARCHIVE_PATH)
        if manifest.get("schema_version") != "study-anything-platform-adoption-pack-v1":
            raise SchemaPackConsumerError("Adoption pack manifest schema drifted.")
        if manifest.get("no_frontend_required") is not True:
            raise SchemaPackConsumerError("Adoption pack must remain no-frontend required.")
        if manifest.get("real_model_keys_stored_by_study_anything") is not False:
            raise SchemaPackConsumerError("Study Anything must not store real model keys.")

        schema_record = manifest_record(manifest, SCHEMA_BUNDLE_PATH)
        negative_record = manifest_record(manifest, NEGATIVE_FIXTURE_PATH)
        schema_raw = assert_zip_record_matches(archive, record=schema_record, expected_path=SCHEMA_BUNDLE_PATH)
        negative_raw = assert_zip_record_matches(
            archive,
            record=negative_record,
            expected_path=NEGATIVE_FIXTURE_PATH,
        )
        schema_bundle = json.loads(schema_raw.decode("utf-8"))
        negative_fixtures = json.loads(negative_raw.decode("utf-8"))

    reject_private_text(dump_json(schema_bundle), label="schema bundle from adoption pack")
    reject_private_text(dump_json(negative_fixtures), label="schema negative fixtures from adoption pack")

    json_schema = schema_bundle.get("json_schema") or {}
    if schema_bundle.get("schema_version") != "cognitive-loop-recipe-cli-schemas-v1":
        raise SchemaPackConsumerError("Schema bundle schema_version drifted.")
    if schema_bundle.get("status") != "pass":
        raise SchemaPackConsumerError("Schema bundle must pass.")
    if json_schema.get("schema_count") != 3:
        raise SchemaPackConsumerError("Schema bundle must expose three schemas.")
    validation = schema_bundle.get("validation") or {}
    for key in ("validated_without_running_recipe_cli",):
        if validation.get(key) is not True:
            raise SchemaPackConsumerError(f"Schema bundle validation.{key} must be true.")
    for key in ("recipe_cli_invoked", "runtime_started", "file_changes_applied"):
        if validation.get(key) is not False:
            raise SchemaPackConsumerError(f"Schema bundle validation.{key} must be false.")

    if negative_fixtures.get("schema_version") != "cognitive-loop-recipe-cli-schema-negative-fixtures-v1":
        raise SchemaPackConsumerError("Schema negative fixture schema_version drifted.")
    if negative_fixtures.get("status") != "pass":
        raise SchemaPackConsumerError("Schema negative fixture report must pass.")
    coverage = negative_fixtures.get("coverage") or {}
    expected_cases = {
        "success_wrong_schema_version",
        "success_auto_execute_true",
        "receipts_missing_privacy",
        "failures_exit_code_string",
        "private_text_probe_rejected",
    }
    if coverage.get("case_count") != len(expected_cases):
        raise SchemaPackConsumerError("Schema negative fixture case count drifted.")
    if set(coverage.get("case_ids", [])) != expected_cases:
        raise SchemaPackConsumerError("Schema negative fixture case IDs drifted.")
    for key in (
        "all_cases_rejected",
        "all_expected_errors_matched",
        "all_errors_redacted",
        "validated_without_running_recipe_cli",
    ):
        if coverage.get(key) is not True:
            raise SchemaPackConsumerError(f"Schema negative fixture coverage.{key} must be true.")
    for key in ("mutated_payloads_persisted", "recipe_cli_invoked", "runtime_started", "file_changes_applied"):
        if coverage.get(key) is not False:
            raise SchemaPackConsumerError(f"Schema negative fixture coverage.{key} must be false.")

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "purpose": "Prove external platform Agents can validate Cognitive Loop recipe CLI schemas from the adoption pack zip without a repo checkout.",
        "pack": {
            "path": relative_path(pack_path),
            "manifest_schema_version": manifest["schema_version"],
            "file_count": len(manifest.get("files", [])),
            "no_frontend_required": True,
            "real_model_keys_stored_by_study_anything": False,
        },
        "zip_only_validation": {
            "repo_checkout_required": False,
            "recipe_cli_invoked": False,
            "runtime_started": False,
            "file_changes_applied": False,
            "manifest_records_checked": True,
            "archive_asset_hashes_match": True,
            "files_read_from_zip": [
                MANIFEST_ARCHIVE_PATH,
                archive_path(SCHEMA_BUNDLE_PATH),
                archive_path(NEGATIVE_FIXTURE_PATH),
            ],
        },
        "schema_bundle": {
            "path": SCHEMA_BUNDLE_PATH,
            "archive_path": archive_path(SCHEMA_BUNDLE_PATH),
            "schema_version": schema_bundle["schema_version"],
            "schema_count": json_schema["schema_count"],
            "schema_keys": json_schema.get("schema_keys", []),
            "validated_without_running_recipe_cli": True,
        },
        "negative_fixtures": {
            "path": NEGATIVE_FIXTURE_PATH,
            "archive_path": archive_path(NEGATIVE_FIXTURE_PATH),
            "schema_version": negative_fixtures["schema_version"],
            "case_count": coverage["case_count"],
            "case_ids": coverage["case_ids"],
            "all_cases_rejected": True,
        },
        "distribution": {
            "report_path": REPORT.relative_to(ROOT).as_posix(),
            "verification_command": "python3 scripts/verify_cognitive_loop_schema_pack_consumer.py --check",
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
        },
    }
    reject_private_text(dump_json(report), label="schema pack consumer report")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--pack", default=str(ADOPTION_PACK))
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
            raise SystemExit(f"Cognitive Loop schema pack consumer report is missing: {output}")
        current = output.read_text(encoding="utf-8")
        if current != serialized:
            raise SystemExit(
                "Cognitive Loop schema pack consumer report is stale. "
                "Run: python3 scripts/verify_cognitive_loop_schema_pack_consumer.py --write"
            )
    if not args.write and not args.check:
        print(serialized, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_cognitive_loop_schema_pack_consumer failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
