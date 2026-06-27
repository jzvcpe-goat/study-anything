#!/usr/bin/env python3
"""Verify the end-to-end Review Agent adoption drill from the adoption pack."""

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
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-review-agent-adoption-drill.json"
ARCHIVE_ROOT = "study-anything-platform-adoption-pack"

SCHEMA_VERSION = "cognitive-loop-review-agent-adoption-drill-v1"
PACK_SCHEMA_VERSION = "study-anything-platform-adoption-pack-v1"
COMMENT_PACK_SCHEMA_VERSION = "cognitive-loop-review-agent-pr-comment-pack-v1"
POLICY_GATE_SCHEMA_VERSION = "cognitive-loop-review-agent-policy-gate-v1"
FIXED_GENERATED_AT = "2026-06-18T00:00:00+00:00"

REPORT_FIXTURES = ("approved.json", "needs-review.json", "needs-fix.json")
POLICIES = ("advisory", "soft", "strict")
EXPECTED_POLICY_EXITS = {
    "approved": {"advisory": 0, "soft": 0, "strict": 0},
    "needs-review": {"advisory": 0, "soft": 0, "strict": 2},
    "needs-fix": {"advisory": 0, "soft": 2, "strict": 2},
}

REQUIRED_PACK_FILES = (
    "manifest.json",
    "platform/prompts/cognitive-loop-review-agent.json",
    "platform/schemas/cognitive-loop-review-agent-report.schema.json",
    "platform/workflows/cognitive-loop-review-agent-manual.yml",
    "scripts/cognitive_loop_review_agent_acceptance_bundle.py",
    "scripts/cognitive_loop_review_agent_policy_gate.py",
    "scripts/cognitive_loop_review_agent_pr_comment.py",
    "scripts/cognitive_loop_review_agent_receipt.py",
    "scripts/cognitive_loop_review_agent_handoff.py",
    "scripts/verify_cognitive_loop_review_agent_workflow_install_smoke.py",
    "platform/generated/study-anything-cognitive-loop-review-agent-acceptance-bundle.json",
    "platform/generated/study-anything-cognitive-loop-review-agent-pr-comment-pack.json",
    "platform/generated/study-anything-cognitive-loop-review-agent-policy-gate.json",
    "platform/generated/study-anything-cognitive-loop-review-agent-workflow-install-smoke.json",
    "docs/cognitive-loop-code-review.md",
    "docs/github-review-agent-workflow.md",
    "evals/README.md",
    "fixtures/review-agent/approved.json",
    "fixtures/review-agent/needs-review.json",
    "fixtures/review-agent/needs-fix.json",
)
WORKFLOW_REQUIRED_NEEDLES = (
    "workflow_dispatch:",
    "permissions:",
    "contents: read",
    "actions: read",
    "scripts/cognitive_loop_review_agent_acceptance_bundle.py build",
    "scripts/cognitive_loop_review_agent_policy_gate.py",
    "review-agent-policy-gate.json",
    "review-agent-checks-summary.md",
)
WORKFLOW_FORBIDDEN_NEEDLES = (
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
PRIVATE_NEEDLES = (
    "diff --git",
    "@@ ",
    "OPENAI_API_KEY=",
    "MOONSHOT_API_KEY=",
    "ANTHROPIC_API_KEY=",
    "sk-proj-",
    "bearer ",
    "http://private-agent.local",
    "hidden chain-of-thought",
    "subprocess.run(user_command",
)


class ReviewAgentAdoptionDrillError(RuntimeError):
    """Readable Review Agent adoption drill failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReviewAgentAdoptionDrillError(message)


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ReviewAgentAdoptionDrillError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ReviewAgentAdoptionDrillError(f"JSON object expected: {path}")
    return payload


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reject_private_text(value: Any, *, label: str) -> None:
    serialized = value if isinstance(value, str) else dump_json(value)
    lowered = serialized.lower()
    leaked = [needle for needle in PRIVATE_NEEDLES if needle.lower() in lowered]
    require(not leaked, f"{label} leaked private Review Agent material: {leaked}")


def safe_extract(archive: zipfile.ZipFile, destination: Path) -> None:
    destination = destination.resolve()
    for member in archive.infolist():
        target = (destination / member.filename).resolve()
        if not target.is_relative_to(destination):
            raise ReviewAgentAdoptionDrillError(f"Unsafe adoption pack member path: {member.filename}")
    archive.extractall(destination)


def extract_pack(pack_path: Path, destination: Path) -> Path:
    require(pack_path.is_file(), f"Adoption pack is missing: {pack_path}")
    with zipfile.ZipFile(pack_path) as archive:
        safe_extract(archive, destination)
    extracted_root = destination / ARCHIVE_ROOT
    require(extracted_root.is_dir(), "Adoption pack did not extract to the expected archive root.")
    return extracted_root


def run_command(command: list[str], *, cwd: Path, expected_code: int = 0) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != expected_code:
        raise ReviewAgentAdoptionDrillError(
            "Command exited unexpectedly: "
            f"expected={expected_code} actual={completed.returncode} command={' '.join(command)} "
            f"stdout={completed.stdout[-500:]} stderr={completed.stderr[-500:]}"
        )
    reject_private_text(completed.stdout + completed.stderr, label=f"command output {' '.join(command[:2])}")
    return completed


def validate_pack_manifest(extracted_root: Path) -> dict[str, Any]:
    manifest = read_json(extracted_root / "manifest.json")
    require(manifest.get("schema_version") == PACK_SCHEMA_VERSION, "Adoption pack schema drifted.")
    require(manifest.get("no_frontend_required") is True, "Adoption pack must remain no-frontend required.")
    require(
        manifest.get("real_model_keys_stored_by_study_anything") is False,
        "Study Anything must not store real model keys.",
    )
    missing = [path for path in REQUIRED_PACK_FILES if not (extracted_root / path).is_file()]
    require(not missing, f"Adoption pack is missing Review Agent adoption drill files: {missing}")

    manifest_files = {str(record.get("path")): record for record in manifest.get("files", []) if isinstance(record, dict)}
    missing_records = [path for path in REQUIRED_PACK_FILES if path != "manifest.json" and path not in manifest_files]
    require(not missing_records, f"Adoption pack manifest omits required files: {missing_records}")
    sha_mismatches = []
    for path in REQUIRED_PACK_FILES:
        if path == "manifest.json":
            continue
        record = manifest_files[path]
        actual = sha256_file(extracted_root / path)
        if record.get("sha256") != actual:
            sha_mismatches.append(path)
    require(not sha_mismatches, f"Adoption pack manifest hashes drifted: {sha_mismatches}")

    return {
        "schema_version": manifest["schema_version"],
        "file_count": len(manifest.get("files", [])),
        "tool_count": manifest.get("tool_count"),
        "archive_sha256": manifest.get("archive_sha256"),
        "no_frontend_required": manifest.get("no_frontend_required"),
        "real_model_keys_stored_by_study_anything": manifest.get("real_model_keys_stored_by_study_anything"),
    }


def validate_generated_report_schemas(extracted_root: Path) -> dict[str, str]:
    expected = {
        "acceptance_bundle": (
            "platform/generated/study-anything-cognitive-loop-review-agent-acceptance-bundle.json",
            "cognitive-loop-review-agent-acceptance-bundle-verification-v1",
        ),
        "pr_comment_pack": (
            "platform/generated/study-anything-cognitive-loop-review-agent-pr-comment-pack.json",
            "cognitive-loop-review-agent-pr-comment-pack-verification-v1",
        ),
        "policy_gate": (
            "platform/generated/study-anything-cognitive-loop-review-agent-policy-gate.json",
            "cognitive-loop-review-agent-policy-gate-verification-v1",
        ),
        "workflow_install_smoke": (
            "platform/generated/study-anything-cognitive-loop-review-agent-workflow-install-smoke.json",
            "cognitive-loop-review-agent-workflow-install-smoke-v1",
        ),
    }
    schemas: dict[str, str] = {}
    for key, (relative, schema_version) in expected.items():
        payload = read_json(extracted_root / relative)
        require(payload.get("schema_version") == schema_version, f"{relative} schema drifted.")
        schemas[key] = str(payload.get("schema_version"))
    return schemas


def validate_workflow_install(extracted_root: Path, scratch: Path) -> dict[str, Any]:
    source = extracted_root / "platform" / "workflows" / "cognitive-loop-review-agent-manual.yml"
    installed_dir = scratch / "adopter-repo" / ".github" / "workflows"
    installed_dir.mkdir(parents=True)
    installed = installed_dir / "cognitive-loop-review-agent-manual.yml"
    shutil.copy2(source, installed)
    text = installed.read_text(encoding="utf-8")
    missing = [needle for needle in WORKFLOW_REQUIRED_NEEDLES if needle not in text]
    forbidden = [needle for needle in WORKFLOW_FORBIDDEN_NEEDLES if needle in text]
    require(not missing, f"Installed workflow is missing required Review Agent fields: {missing}")
    require(not forbidden, f"Installed workflow contains unsafe trigger/secret/raw-report fields: {forbidden}")
    return {
        "installed_path": ".github/workflows/cognitive-loop-review-agent-manual.yml",
        "manual_only": True,
        "read_only_permissions": True,
        "raw_report_upload": False,
        "secret_dependency": False,
        "sha256": sha256_file(installed),
    }


def build_acceptance_bundle(extracted_root: Path, fixture_name: str, output_root: Path) -> Path:
    fixture_id = fixture_name.removesuffix(".json")
    output_dir = output_root / fixture_id / "review-agent-acceptance"
    run_command(
        [
            sys.executable,
            "scripts/cognitive_loop_review_agent_acceptance_bundle.py",
            "build",
            "--report",
            f"fixtures/review-agent/{fixture_name}",
            "--output-dir",
            str(output_dir),
            "--provider-id",
            f"adoption-drill-{fixture_id}-review-agent",
            "--provider-label",
            f"Adoption drill {fixture_id} Review Agent",
            "--execution-surface",
            "ci",
            "--pr-ref",
            f"PR-adoption-drill-{fixture_id}",
            "--commit-sha",
            f"sha-adoption-drill-{fixture_id}",
            "--base-ref",
            "main",
            "--head-ref",
            f"codex/adoption-drill-{fixture_id}",
            "--generated-at",
            FIXED_GENERATED_AT,
            "--validation-command",
            "python3 scripts/cognitive_loop_review_agent_handoff.py validate --report REVIEW_AGENT_REPORT.json",
        ],
        cwd=extracted_root,
    )
    run_command(
        [
            sys.executable,
            "scripts/cognitive_loop_review_agent_acceptance_bundle.py",
            "validate",
            "--bundle-dir",
            str(output_dir),
        ],
        cwd=extracted_root,
    )
    return output_dir


def validate_comment_pack(extracted_root: Path, bundle_dir: Path) -> dict[str, Any]:
    comment_pack_path = bundle_dir / "review-agent-pr-comment-pack.json"
    run_command(
        [
            sys.executable,
            "scripts/cognitive_loop_review_agent_pr_comment.py",
            "validate",
            "--comment-pack",
            str(comment_pack_path),
        ],
        cwd=extracted_root,
    )
    payload = read_json(comment_pack_path)
    reject_private_text(payload, label=f"{bundle_dir.name} PR comment pack")
    require(payload.get("schema_version") == COMMENT_PACK_SCHEMA_VERSION, "PR comment pack schema drifted.")
    summary = payload.get("decision_summary", {})
    comments = payload.get("comments", {})
    require("Decision:" in str(comments.get("markdown_en", "")), "English PR comment missing decision.")
    require("决策：" in str(comments.get("markdown_zh", "")), "Chinese PR comment missing decision.")
    return {
        "schema_version": payload["schema_version"],
        "conclusion": summary.get("conclusion"),
        "human_action": summary.get("human_action"),
        "labels_to_add": summary.get("labels_to_add", []),
        "markdown_en_sha256": hashlib.sha256(str(comments.get("markdown_en", "")).encode("utf-8")).hexdigest(),
        "markdown_zh_sha256": hashlib.sha256(str(comments.get("markdown_zh", "")).encode("utf-8")).hexdigest(),
    }


def run_policy_matrix(extracted_root: Path, bundle_dir: Path, fixture_id: str) -> dict[str, Any]:
    matrix: dict[str, Any] = {}
    for policy in POLICIES:
        output_path = bundle_dir / f"review-agent-policy-gate-{policy}.json"
        expected_code = EXPECTED_POLICY_EXITS[fixture_id][policy]
        completed = run_command(
            [
                sys.executable,
                "scripts/cognitive_loop_review_agent_policy_gate.py",
                "--bundle-dir",
                str(bundle_dir),
                "--policy",
                policy,
                "--output",
                str(output_path),
                "--generated-at",
                FIXED_GENERATED_AT,
            ],
            cwd=extracted_root,
            expected_code=expected_code,
        )
        payload = read_json(output_path)
        reject_private_text(payload, label=f"{fixture_id} {policy} policy gate")
        require(payload.get("schema_version") == POLICY_GATE_SCHEMA_VERSION, f"{policy} policy gate schema drifted.")
        require(payload.get("policy") == policy, f"{fixture_id} policy gate policy drifted.")
        require(payload.get("exit_code") == expected_code, f"{fixture_id} {policy} exit code drifted.")
        matrix[policy] = {
            "exit_code": completed.returncode,
            "status": payload.get("status"),
            "decision": payload.get("decision_summary", {}).get("decision"),
            "conclusion": payload.get("github_checks", {}).get("conclusion"),
        }
    return matrix


def run_fixture_drill(extracted_root: Path, fixture_name: str, output_root: Path) -> dict[str, Any]:
    fixture_id = fixture_name.removesuffix(".json")
    bundle_dir = build_acceptance_bundle(extracted_root, fixture_name, output_root)
    manifest = read_json(bundle_dir / "manifest.json")
    reject_private_text(manifest, label=f"{fixture_id} acceptance bundle manifest")
    comment_pack = validate_comment_pack(extracted_root, bundle_dir)
    policy_matrix = run_policy_matrix(extracted_root, bundle_dir, fixture_id)
    expected_matrix = EXPECTED_POLICY_EXITS[fixture_id]
    actual_matrix = {policy: policy_matrix[policy]["exit_code"] for policy in POLICIES}
    require(actual_matrix == expected_matrix, f"{fixture_id} policy matrix drifted: {actual_matrix}")
    return {
        "fixture": fixture_name,
        "decision": manifest.get("decision_summary", {}).get("decision"),
        "bundle_schema_version": manifest.get("schema_version"),
        "bundle_file_count": len(list(bundle_dir.iterdir())),
        "comment_pack": comment_pack,
        "policy_exit_matrix": actual_matrix,
        "policy_results": policy_matrix,
    }


def validate_docs() -> dict[str, str]:
    docs = {
        "docs/cognitive-loop-code-review.md": [
            "verify_cognitive_loop_review_agent_adoption_drill.py --check",
        ],
        "docs/eval-frameworks.md": [
            "cognitive-loop-review-agent-adoption-drill-v1",
            "verify_cognitive_loop_review_agent_adoption_drill.py --check",
        ],
        "evals/README.md": [
            "verify_cognitive_loop_review_agent_adoption_drill.py --check",
        ],
        ".cognitive-loop/evals.yaml": [
            "cognitive-loop.review-agent-adoption-drill",
            "python3 scripts/verify_cognitive_loop_review_agent_adoption_drill.py --check",
        ],
        "scripts/release_check.sh": [
            "scripts/verify_cognitive_loop_review_agent_adoption_drill.py --check",
        ],
        "platform/packs/codex/README.md": [
            "verify_cognitive_loop_review_agent_adoption_drill.py --check",
        ],
        "platform/packs/kimi/README.md": [
            "verify_cognitive_loop_review_agent_adoption_drill.py --check",
        ],
        "platform/packs/workbuddy/README.md": [
            "verify_cognitive_loop_review_agent_adoption_drill.py --check",
        ],
    }
    checked: dict[str, str] = {}
    for relative, needles in docs.items():
        text = (ROOT / relative).read_text(encoding="utf-8")
        missing = [needle for needle in needles if needle not in text]
        require(not missing, f"{relative} missing Review Agent adoption drill references: {missing}")
        checked[relative] = "pass"
    return checked


def build_report() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-anything-review-agent-adoption-drill-") as tmp_name:
        scratch = Path(tmp_name)
        extracted_root = extract_pack(ADOPTION_PACK, scratch / "pack")
        pack = validate_pack_manifest(extracted_root)
        embedded_reports = validate_generated_report_schemas(extracted_root)
        workflow_install = validate_workflow_install(extracted_root, scratch)
        fixture_root = scratch / "fixtures"
        fixture_results = {
            fixture.removesuffix(".json"): run_fixture_drill(extracted_root, fixture, fixture_root)
            for fixture in REPORT_FIXTURES
        }

    decisions = {result["decision"] for result in fixture_results.values()}
    require(decisions == {"approved", "needs-review", "needs-fix"}, f"Adoption drill decision coverage drifted: {decisions}")
    docs = validate_docs()
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "purpose": "Prove a zip-only external adopter can run the full metadata-only Review Agent evidence path.",
        "adoption_pack": pack,
        "embedded_reports": embedded_reports,
        "workflow_install": workflow_install,
        "fixture_count": len(fixture_results),
        "fixtures": fixture_results,
        "quality_gates": {
            "zip_only_execution": "pass",
            "decision_path_coverage": sorted(decisions),
            "acceptance_bundle_generation": "pass",
            "bilingual_pr_comment_pack": "pass",
            "policy_gate_matrix": "pass",
            "manual_workflow_install": "pass",
            "metadata_only_outputs": "pass",
        },
        "privacy": {
            "raw_diff_included": False,
            "file_bodies_included": False,
            "finding_evidence_included": False,
            "report_summary_included": False,
            "raw_report_uploaded": False,
            "agent_endpoint_secrets_included": False,
            "real_model_keys_included": False,
            "hidden_chain_of_thought_included": False,
            "safe_to_attach_to_pr": True,
        },
        "docs": docs,
        "acceptance": {
            "minimum_command": "python3 scripts/verify_cognitive_loop_review_agent_adoption_drill.py --check",
            "generated_report": "platform/generated/study-anything-cognitive-loop-review-agent-adoption-drill.json",
            "pack_required": "platform/generated/study-anything-platform-adoption-pack.zip",
            "policy_matrix": EXPECTED_POLICY_EXITS,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", default=str(REPORT))
    args = parser.parse_args()

    output = Path(args.output)
    report = build_report()
    serialized = dump_json(report)
    if args.write:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
    if args.check:
        if not output.is_file():
            raise SystemExit(f"Cognitive Loop Review Agent adoption drill report is missing: {output}")
        current = output.read_text(encoding="utf-8")
        if current != serialized:
            raise SystemExit(
                "Cognitive Loop Review Agent adoption drill report is out of date. "
                "Run: python3 scripts/verify_cognitive_loop_review_agent_adoption_drill.py --write"
            )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReviewAgentAdoptionDrillError as exc:
        raise SystemExit(f"error: {exc}") from exc
