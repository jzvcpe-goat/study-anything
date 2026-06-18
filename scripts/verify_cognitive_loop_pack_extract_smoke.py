#!/usr/bin/env python3
"""Verify the extracted adoption pack can run its included schema consumer checks."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import verify_cognitive_loop_schema_pack_consumer as consumer


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-pack-extract-smoke.json"
SCHEMA_VERSION = "cognitive-loop-pack-extract-smoke-v1"
ARCHIVE_ROOT = consumer.ARCHIVE_ROOT
CONSUMER_REPORT = "platform/generated/study-anything-cognitive-loop-schema-pack-consumer.json"
FAILURE_REPORT = "platform/generated/study-anything-cognitive-loop-schema-pack-consumer-failures.json"
CONSUMER_SCRIPT = "scripts/verify_cognitive_loop_schema_pack_consumer.py"
FAILURE_SCRIPT = "scripts/verify_cognitive_loop_schema_pack_consumer_failures.py"
EXTRACTED_REQUIRED_FILES = (
    "manifest.json",
    CONSUMER_REPORT,
    FAILURE_REPORT,
    CONSUMER_SCRIPT,
    FAILURE_SCRIPT,
)


class PackExtractSmokeError(RuntimeError):
    """Readable extracted-pack smoke verification failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def safe_extract(archive: zipfile.ZipFile, destination: Path) -> None:
    destination = destination.resolve()
    for member in archive.infolist():
        target = (destination / member.filename).resolve()
        if not target.is_relative_to(destination):
            raise PackExtractSmokeError(f"Unsafe adoption pack member path: {member.filename}")
    archive.extractall(destination)


def assert_extracted_files(extracted_root: Path) -> list[str]:
    missing = [path for path in EXTRACTED_REQUIRED_FILES if not (extracted_root / path).is_file()]
    if missing:
        raise PackExtractSmokeError(f"Extracted adoption pack is missing required files: {missing}")
    return list(EXTRACTED_REQUIRED_FILES)


def run_included_script(
    *,
    extracted_root: Path,
    pack_path: Path,
    script_path: str,
    report_path: str,
) -> dict[str, Any]:
    base_command = [
        sys.executable,
        str(extracted_root / script_path),
        "--pack",
        str(pack_path),
        "--output",
        str(extracted_root / report_path),
    ]
    write_command = [
        *base_command,
        "--write",
    ]
    check_command = [
        *base_command,
        "--check",
    ]
    for mode, command in (("write", write_command), ("check", check_command)):
        result = subprocess.run(
            command,
            cwd=extracted_root,
            capture_output=True,
            check=False,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip().splitlines()[:1]
            reason = stderr[0] if stderr else "no stderr"
            raise PackExtractSmokeError(f"Extracted pack script {mode} failed: {script_path}: {reason}")
    return {
        "script": script_path,
        "report": report_path,
        "mode": "write_then_check",
        "status": "pass",
        "exit_code": 0,
    }


def build_report(pack_path: Path) -> dict[str, Any]:
    if not pack_path.is_file():
        raise PackExtractSmokeError(f"Adoption pack is missing: {pack_path}")

    baseline = consumer.build_report(pack_path)
    with tempfile.TemporaryDirectory(prefix="study-anything-pack-extract-smoke-") as tmp:
        tmp_dir = Path(tmp)
        with zipfile.ZipFile(pack_path) as archive:
            safe_extract(archive, tmp_dir)
        extracted_root = tmp_dir / ARCHIVE_ROOT
        if not extracted_root.is_dir():
            raise PackExtractSmokeError("Adoption pack did not extract to the expected archive root.")
        extracted_files = assert_extracted_files(extracted_root)
        commands = [
            run_included_script(
                extracted_root=extracted_root,
                pack_path=pack_path.resolve(),
                script_path=CONSUMER_SCRIPT,
                report_path=CONSUMER_REPORT,
            ),
            run_included_script(
                extracted_root=extracted_root,
                pack_path=pack_path.resolve(),
                script_path=FAILURE_SCRIPT,
                report_path=FAILURE_REPORT,
            ),
        ]

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "purpose": (
            "Prove an external platform Agent can extract the adoption pack and run its included "
            "Cognitive Loop schema consumer checks without a repo checkout."
        ),
        "pack": {
            "path": relative_path(pack_path),
            "manifest_schema_version": baseline["pack"]["manifest_schema_version"],
            "file_count": baseline["pack"]["file_count"],
            "no_frontend_required": True,
            "real_model_keys_stored_by_study_anything": False,
        },
        "extraction": {
            "archive_root": ARCHIVE_ROOT,
            "required_files_present": extracted_files,
            "command_count": len(commands),
            "included_scripts_executed": True,
        },
        "commands": commands,
        "zip_only_validation": {
            "repo_checkout_required": False,
            "recipe_cli_invoked": False,
            "runtime_started": False,
            "file_changes_applied": False,
            "used_extracted_pack_scripts": True,
            "original_pack_only": True,
            "temporary_report_outputs_persisted": False,
        },
        "distribution": {
            "report_path": REPORT.relative_to(ROOT).as_posix(),
            "verification_command": "python3 scripts/verify_cognitive_loop_pack_extract_smoke.py --check",
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
            "temporary_paths_included": False,
            "command_stdout_included": False,
            "command_stderr_included": False,
            "temporary_report_outputs_included": False,
        },
    }
    consumer.reject_private_text(dump_json(report), label="extracted pack smoke report")
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
            raise SystemExit(f"Cognitive Loop extracted pack smoke report is missing: {output}")
        current = output.read_text(encoding="utf-8")
        if current != serialized:
            raise SystemExit(
                "Cognitive Loop extracted pack smoke report is stale. "
                "Run: python3 scripts/verify_cognitive_loop_pack_extract_smoke.py --write"
            )
    if not args.write and not args.check:
        print(serialized, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_cognitive_loop_pack_extract_smoke failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
