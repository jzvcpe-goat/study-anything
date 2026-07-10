#!/usr/bin/env python3
"""Verify adopters can install the Review Agent workflow from the adoption pack."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ADOPTION_PACK = ROOT / "platform" / "generated" / "study-anything-platform-adoption-pack.zip"
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-review-agent-workflow-install-smoke.json"
ARCHIVE_ROOT = "study-anything-platform-adoption-pack"
SCHEMA_VERSION = "cognitive-loop-review-agent-workflow-install-smoke-v1"
PACK_SCHEMA_VERSION = "study-anything-platform-adoption-pack-v1"
FIXED_GENERATED_AT = "2026-06-18T00:00:00+00:00"

WORKFLOW_PATH = "platform/workflows/cognitive-loop-review-agent-manual.yml"
BUNDLE_CLI = "scripts/cognitive_loop_review_agent_acceptance_bundle.py"
POLICY_GATE_CLI = "scripts/cognitive_loop_review_agent_policy_gate.py"
REPORT_FIXTURES = ("approved.json", "needs-review.json", "needs-fix.json")
POLICIES = ("advisory", "soft", "strict")
EXPECTED_POLICY_EXITS = {
    "approved": {"advisory": 0, "soft": 0, "strict": 0},
    "needs-review": {"advisory": 0, "soft": 0, "strict": 2},
    "needs-fix": {"advisory": 0, "soft": 2, "strict": 2},
}

REQUIRED_PACK_FILES = (
    "manifest.json",
    WORKFLOW_PATH,
    BUNDLE_CLI,
    POLICY_GATE_CLI,
    "scripts/cognitive_loop_review_agent_receipt.py",
    "scripts/cognitive_loop_review_agent_pr_comment.py",
    "docs/github-review-agent-workflow.md",
    "platform/generated/study-anything-cognitive-loop-review-agent-github-workflow.json",
    "platform/generated/study-anything-cognitive-loop-review-agent-policy-gate.json",
    "fixtures/review-agent/approved.json",
    "fixtures/review-agent/needs-review.json",
    "fixtures/review-agent/needs-fix.json",
)
REQUIRED_WORKFLOW_NEEDLES = (
    "workflow_dispatch:",
    "permissions:",
    "contents: read",
    "actions: read",
    "policy:",
    "upload_metadata_bundle:",
    "scripts/cognitive_loop_review_agent_acceptance_bundle.py build",
    "scripts/cognitive_loop_review_agent_acceptance_bundle.py validate",
    "scripts/cognitive_loop_review_agent_policy_gate.py",
    "REVIEW_AGENT_POLICY_EXIT",
    "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
    "review-agent-policy-gate.json",
    "review-agent-checks-summary.md",
)
FORBIDDEN_WORKFLOW_NEEDLES = (
    "pull_request:",
    "push:",
    "schedule:",
    "secrets.",
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "ANTHROPIC_API_KEY",
    "raw-review-agent-report",
    "path: REVIEW_AGENT_REPORT.json",
    "path: ${{ inputs.review_agent_report }}",
)
UPLOAD_ALLOWLIST = (
    "manifest.json",
    "SUMMARY.md",
    "review-agent-ci-receipt.json",
    "review-agent-pr-comment-pack.json",
    "review-agent-policy-gate.json",
    "review-agent-checks-summary.md",
)
PRIVATE_NEEDLES = (
    "diff --git",
    "@@ ",
    "OPENAI_API_KEY=",
    "MOONSHOT_API_KEY=",
    "sk-proj-",
    "bearer ",
    "http://private-agent.local",
    "hidden chain-of-thought",
)


class WorkflowInstallSmokeError(RuntimeError):
    """Readable workflow install-smoke failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise WorkflowInstallSmokeError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise WorkflowInstallSmokeError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise WorkflowInstallSmokeError(f"JSON object expected: {path}")
    return payload


def reject_private_text(value: Any, *, label: str) -> None:
    serialized = value if isinstance(value, str) else dump_json(value)
    lowered = serialized.lower()
    leaked = [needle for needle in PRIVATE_NEEDLES if needle.lower() in lowered]
    if leaked:
        raise WorkflowInstallSmokeError(f"{label} contains private or raw Review Agent text: {leaked}")


def safe_extract(archive: zipfile.ZipFile, destination: Path) -> None:
    destination = destination.resolve()
    for member in archive.infolist():
        target = (destination / member.filename).resolve()
        if not target.is_relative_to(destination):
            raise WorkflowInstallSmokeError(f"Unsafe adoption pack member path: {member.filename}")
    archive.extractall(destination)


def extract_pack(pack_path: Path, destination: Path) -> Path:
    if not pack_path.is_file():
        raise WorkflowInstallSmokeError(f"Adoption pack is missing: {pack_path}")
    with zipfile.ZipFile(pack_path) as archive:
        safe_extract(archive, destination)
    extracted_root = destination / ARCHIVE_ROOT
    if not extracted_root.is_dir():
        raise WorkflowInstallSmokeError("Adoption pack did not extract to the expected archive root.")
    return extracted_root


def validate_pack_manifest(extracted_root: Path) -> dict[str, Any]:
    manifest = read_json(extracted_root / "manifest.json")
    require(manifest.get("schema_version") == PACK_SCHEMA_VERSION, "Adoption pack schema drifted.")
    require(manifest.get("no_frontend_required") is True, "Adoption pack must remain no-frontend required.")
    require(
        manifest.get("real_model_keys_stored_by_study_anything") is False,
        "Study Anything must not store real model keys.",
    )
    missing = [path for path in REQUIRED_PACK_FILES if not (extracted_root / path).is_file()]
    require(not missing, f"Adoption pack is missing Review Agent workflow install files: {missing}")

    manifest_files = {str(record.get("path")): record for record in manifest.get("files", []) if isinstance(record, dict)}
    recorded_required_files = [path for path in REQUIRED_PACK_FILES if path != "manifest.json"]
    missing_records = [path for path in recorded_required_files if path not in manifest_files]
    require(not missing_records, f"Adoption pack manifest omits required files: {missing_records}")
    sha_mismatches = [
        path
        for path in recorded_required_files
        if sha256_file(extracted_root / path) != manifest_files[path].get("sha256")
    ]
    require(not sha_mismatches, f"Adoption pack Review Agent files failed sha256 validation: {sha_mismatches}")
    return {
        "schema_version": manifest["schema_version"],
        "file_count": len(manifest.get("files", [])),
        "required_review_agent_files_present": list(REQUIRED_PACK_FILES),
        "no_frontend_required": True,
        "real_model_keys_stored_by_study_anything": False,
    }


def validate_installed_workflow(workflow_path: Path) -> dict[str, Any]:
    text = workflow_path.read_text(encoding="utf-8")
    missing = [needle for needle in REQUIRED_WORKFLOW_NEEDLES if needle not in text]
    require(not missing, f"Installed Review Agent workflow missing required text: {missing}")
    forbidden = [needle for needle in FORBIDDEN_WORKFLOW_NEEDLES if needle in text]
    require(not forbidden, f"Installed Review Agent workflow contains unsafe text: {forbidden}")
    for allowed in UPLOAD_ALLOWLIST:
        require(allowed in text, f"Installed workflow upload allowlist missing {allowed}.")
    reject_private_text(
        {
            "workflow_sha256": sha256_file(workflow_path),
            "required_needles_present": list(REQUIRED_WORKFLOW_NEEDLES),
            "upload_allowlist": list(UPLOAD_ALLOWLIST),
        },
        label="installed workflow metadata",
    )
    return {
        "installed_path": ".github/workflows/cognitive-loop-review-agent-manual.yml",
        "content_sha256": sha256_file(workflow_path),
        "manual_only_trigger": True,
        "read_only_permissions": True,
        "automatic_pr_trigger": False,
        "automatic_push_trigger": False,
        "requires_external_agent_secret": False,
        "uploads_raw_report": False,
        "upload_allowlist": list(UPLOAD_ALLOWLIST),
    }


def run_command(command: list[str], *, cwd: Path, expected_exit: int = 0, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, capture_output=True, check=False, text=True, timeout=timeout)
    if result.returncode != expected_exit:
        stderr = result.stderr.strip().splitlines()[:1]
        reason = stderr[0] if stderr else result.stdout.strip().splitlines()[:1]
        raise WorkflowInstallSmokeError(
            f"Command exited {result.returncode}, expected {expected_exit}: {command[0]} {command[1]}: {reason}"
        )
    reject_private_text(result.stdout, label=f"{Path(command[1]).name} stdout")
    reject_private_text(result.stderr, label=f"{Path(command[1]).name} stderr")
    return result


def build_acceptance_bundle(extracted_root: Path, consumer_repo: Path, fixture_name: str) -> dict[str, Any]:
    fixture_id = fixture_name.removesuffix(".json")
    bundle_dir = consumer_repo / "review-agent-acceptance" / fixture_id
    command = [
        sys.executable,
        str(extracted_root / BUNDLE_CLI),
        "build",
        "--report",
        str(extracted_root / "fixtures" / "review-agent" / fixture_name),
        "--output-dir",
        str(bundle_dir),
        "--provider-id",
        f"zip-install-smoke-{fixture_id}",
        "--provider-label",
        "Zip install smoke external Review Agent",
        "--execution-surface",
        "ci",
        "--pr-ref",
        f"PR-zip-install-smoke-{fixture_id}",
        "--commit-sha",
        f"sha-zip-install-smoke-{fixture_id}",
        "--base-ref",
        "main",
        "--head-ref",
        f"codex/zip-install-smoke-{fixture_id}",
        "--generated-at",
        FIXED_GENERATED_AT,
    ]
    run_command(command, cwd=extracted_root)
    validate_command = [
        sys.executable,
        str(extracted_root / BUNDLE_CLI),
        "validate",
        "--bundle-dir",
        str(bundle_dir),
    ]
    run_command(validate_command, cwd=extracted_root)
    manifest = read_json(bundle_dir / "manifest.json")
    decision = manifest["decision_summary"]["decision"]
    require(decision == fixture_id, f"Fixture {fixture_name} produced unexpected decision {decision}.")
    reject_private_text(manifest, label=f"{fixture_id} acceptance bundle manifest")
    return {
        "fixture": fixture_name,
        "decision": decision,
        "bundle_dir_name": f"review-agent-acceptance/{fixture_id}",
        "metadata_files": ["manifest.json", "SUMMARY.md", "review-agent-ci-receipt.json", "review-agent-pr-comment-pack.json"],
        "manifest_sha256": sha256_file(bundle_dir / "manifest.json"),
    }


def run_policy_matrix(extracted_root: Path, consumer_repo: Path) -> dict[str, dict[str, Any]]:
    matrix: dict[str, dict[str, Any]] = {}
    for fixture_name in REPORT_FIXTURES:
        fixture_id = fixture_name.removesuffix(".json")
        bundle_dir = consumer_repo / "review-agent-acceptance" / fixture_id
        matrix[fixture_id] = {}
        for policy in POLICIES:
            output = consumer_repo / "policy-gates" / fixture_id / f"{policy}.json"
            command = [
                sys.executable,
                str(extracted_root / POLICY_GATE_CLI),
                "--bundle-dir",
                str(bundle_dir),
                "--policy",
                policy,
                "--output",
                str(output),
                "--generated-at",
                FIXED_GENERATED_AT,
            ]
            expected_exit = EXPECTED_POLICY_EXITS[fixture_id][policy]
            run_command(command, cwd=extracted_root, expected_exit=expected_exit)
            payload = read_json(output)
            reject_private_text(payload, label=f"{fixture_id} {policy} policy gate")
            require(payload.get("schema_version") == "cognitive-loop-review-agent-policy-gate-v1", "Policy schema drifted.")
            require(payload.get("exit_code") == expected_exit, f"{fixture_id} {policy} exit code drifted.")
            require(payload.get("policy") == policy, f"{fixture_id} policy label drifted.")
            matrix[fixture_id][policy] = {
                "status": payload["status"],
                "exit_code": payload["exit_code"],
                "decision": payload["decision_summary"]["decision"],
                "metadata_only": payload["privacy"]["metadata_only"],
            }
    return matrix


def build_report(pack_path: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-anything-review-agent-workflow-install-") as tmp:
        tmp_root = Path(tmp)
        extracted_root = extract_pack(pack_path, tmp_root)
        pack = validate_pack_manifest(extracted_root)

        consumer_repo = tmp_root / "adopter-repo"
        workflow_target = consumer_repo / ".github" / "workflows" / "cognitive-loop-review-agent-manual.yml"
        workflow_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(extracted_root / WORKFLOW_PATH, workflow_target)
        installed = validate_installed_workflow(workflow_target)
        require(
            installed["content_sha256"] == sha256_file(extracted_root / WORKFLOW_PATH),
            "Installed workflow sha256 differs from adoption pack template.",
        )

        bundles = [build_acceptance_bundle(extracted_root, consumer_repo, fixture) for fixture in REPORT_FIXTURES]
        policy_matrix = run_policy_matrix(extracted_root, consumer_repo)

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "purpose": (
            "Prove an external adopter can extract the platform adoption pack, install the manual "
            "Review Agent GitHub workflow into .github/workflows, and reproduce metadata-only policy "
            "gate behavior without a repo checkout or raw report artifact upload."
        ),
        "pack": {
            "path": relative_path(pack_path),
            **pack,
        },
        "install": {
            "source_template": WORKFLOW_PATH,
            "target_workflow": installed,
            "copied_from_adoption_pack": True,
            "repo_checkout_required": False,
            "runtime_started": False,
            "file_changes_persisted": False,
        },
        "dry_run": {
            "fixture_count": len(bundles),
            "acceptance_bundles": bundles,
            "policy_matrix": policy_matrix,
            "policy_path_coverage": list(POLICIES),
            "decision_path_coverage": [fixture.removesuffix(".json") for fixture in REPORT_FIXTURES],
        },
        "quality_gates": {
            "zip_only_install": "pass",
            "installed_workflow_matches_pack": "pass",
            "manual_only_trigger": "pass",
            "read_only_permissions": "pass",
            "metadata_only_upload_allowlist": "pass",
            "raw_report_not_uploaded": "pass",
            "policy_gate_runnable_from_pack": "pass",
            "decision_path_coverage": "pass",
        },
        "privacy": {
            "raw_diff_included": False,
            "file_bodies_included": False,
            "finding_evidence_included": False,
            "raw_report_uploaded": False,
            "agent_endpoint_secrets_included": False,
            "real_model_keys_included": False,
            "hidden_chain_of_thought_included": False,
            "temporary_paths_included": False,
            "command_stdout_included": False,
            "command_stderr_included": False,
            "safe_for_public_evidence": True,
        },
        "acceptance": {
            "minimum_command": "python3 scripts/verify_cognitive_loop_review_agent_workflow_install_smoke.py --check",
            "generated_report": "platform/generated/study-anything-cognitive-loop-review-agent-workflow-install-smoke.json",
            "workflow_template": WORKFLOW_PATH,
        },
    }
    reject_private_text(report, label="Review Agent workflow install smoke report")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--pack", default=str(ADOPTION_PACK))
    parser.add_argument("--output", default=str(REPORT))
    args = parser.parse_args()

    pack_path = Path(args.pack)
    if not pack_path.is_absolute():
        pack_path = ROOT / pack_path
    output = Path(args.output)
    serialized = dump_json(build_report(pack_path))
    if args.write:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
    if args.check:
        if not output.is_file():
            raise SystemExit(f"Cognitive Loop Review Agent workflow install smoke report is missing: {output}")
        current = output.read_text(encoding="utf-8")
        if current != serialized:
            raise SystemExit(
                "Cognitive Loop Review Agent workflow install smoke report is stale. "
                "Run: python3 scripts/verify_cognitive_loop_review_agent_workflow_install_smoke.py --write"
            )
    if not args.write and not args.check:
        print(serialized, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_cognitive_loop_review_agent_workflow_install_smoke failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
