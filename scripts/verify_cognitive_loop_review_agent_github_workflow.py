#!/usr/bin/env python3
"""Verify the safe GitHub workflow template for external Review Agent evidence."""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "platform" / "workflows" / "cognitive-loop-review-agent-manual.yml"
UNSAFE_WORKFLOW = ROOT / "fixtures" / "review-agent-github-workflows" / "unsafe-auto-pr.yml"
BUNDLE_CLI_PATH = ROOT / "scripts" / "cognitive_loop_review_agent_acceptance_bundle.py"
POLICY_GATE_CLI_PATH = ROOT / "scripts" / "cognitive_loop_review_agent_policy_gate.py"
REPORT_FIXTURE_DIR = ROOT / "fixtures" / "review-agent"
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-review-agent-github-workflow.json"

SCHEMA_VERSION = "cognitive-loop-review-agent-github-workflow-verification-v1"
REPORT_FIXTURES = ("approved.json", "needs-review.json", "needs-fix.json")
POLICIES = ("advisory", "soft", "strict")
FIXED_GENERATED_AT = "2026-06-18T00:00:00+00:00"

REQUIRED_WORKFLOW_NEEDLES = (
    "workflow_dispatch:",
    "evidence_kind:",
    "review_agent_report:",
    "acceptance_bundle_dir:",
    "policy:",
    "upload_metadata_bundle:",
    "scripts/cognitive_loop_review_agent_acceptance_bundle.py build",
    "scripts/cognitive_loop_review_agent_acceptance_bundle.py validate",
    "scripts/cognitive_loop_review_agent_policy_gate.py",
    "--output review-agent-policy-gate.json",
    "REVIEW_AGENT_POLICY_EXIT",
    'if [ "$ACCEPTANCE_BUNDLE_DIR" != "$OUTPUT_DIR" ]; then',
    "GITHUB_STEP_SUMMARY",
    "review-agent-policy-gate.json",
    "review-agent-checks-summary.md",
    "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
    "review-agent-ci-receipt.json",
    "review-agent-pr-comment-pack.json",
)
FORBIDDEN_WORKFLOW_NEEDLES = (
    "pull_request:",
    "push:",
    "schedule:",
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "ANTHROPIC_API_KEY",
    "secrets.",
    "curl ",
    "wget ",
    "diff --git",
    "@@ ",
    "raw-review-agent-report",
)
PRIVATE_NEEDLES = (
    "diff --git",
    "@@ ",
    "OPENAI_API_KEY=",
    "MOONSHOT_API_KEY=",
    "sk-proj-",
    "bearer ",
    "http://private-agent.local",
    "subprocess.run(user_command",
    "hidden chain-of-thought",
)


class ReviewAgentGithubWorkflowVerificationError(RuntimeError):
    """Readable Review Agent GitHub workflow verification failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReviewAgentGithubWorkflowVerificationError(message)


def load_bundle_cli() -> Any:
    spec = importlib.util.spec_from_file_location("study_anything_review_agent_acceptance_bundle", BUNDLE_CLI_PATH)
    if spec is None or spec.loader is None:
        raise ReviewAgentGithubWorkflowVerificationError(f"Cannot load bundle CLI: {BUNDLE_CLI_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_policy_gate_cli() -> Any:
    spec = importlib.util.spec_from_file_location("study_anything_review_agent_policy_gate", POLICY_GATE_CLI_PATH)
    if spec is None or spec.loader is None:
        raise ReviewAgentGithubWorkflowVerificationError(f"Cannot load policy gate CLI: {POLICY_GATE_CLI_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def reject_private_text(value: Any, *, label: str) -> None:
    serialized = value if isinstance(value, str) else dump_json(value)
    lowered = serialized.lower()
    leaked = [needle for needle in PRIVATE_NEEDLES if needle.lower() in lowered]
    if leaked:
        raise ReviewAgentGithubWorkflowVerificationError(f"{label} contains private or raw Review Agent text: {leaked}")


def validate_workflow_template(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    missing = [needle for needle in REQUIRED_WORKFLOW_NEEDLES if needle not in text]
    require(not missing, f"{path.relative_to(ROOT)} missing required workflow text: {missing}")
    forbidden = [needle for needle in FORBIDDEN_WORKFLOW_NEEDLES if needle in text]
    require(not forbidden, f"{path.relative_to(ROOT)} contains unsafe workflow text: {forbidden}")
    require("path: REVIEW_AGENT_REPORT.json" not in text, "Workflow must not upload the raw report path.")
    require("path: ${{ inputs.review_agent_report }}" not in text, "Workflow must not upload the raw report input.")
    require("contents: read" in text, "Workflow must keep read-only repository permissions.")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "trigger": "workflow_dispatch",
        "automatic_pr_trigger": False,
        "invokes_real_model": False,
        "requires_external_agent_secret": False,
        "uploads_raw_report": False,
        "uploads_metadata_bundle": True,
        "runs_policy_gate": True,
        "policy_input": True,
    }


def validate_unsafe_fixture() -> str:
    try:
        validate_workflow_template(UNSAFE_WORKFLOW)
    except Exception as exc:
        return str(exc)
    raise ReviewAgentGithubWorkflowVerificationError("Unsafe GitHub workflow fixture unexpectedly passed.")


def render_checks_summary(bundle_dir: Path, policy_gate: dict[str, Any]) -> str:
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    comment_pack = json.loads((bundle_dir / "review-agent-pr-comment-pack.json").read_text(encoding="utf-8"))
    checks = comment_pack["checks_summary"]
    decision = manifest["decision_summary"]
    source = manifest["source"]
    policy_result = policy_gate["policy_result"]
    lines = [
        f"## {checks['title']}",
        "",
        f"- Decision: `{decision['decision']}`",
        f"- Risk: `{decision['overall_risk']}`",
        f"- Findings: `{decision['finding_count']}` total, `{decision['critical_count']}` critical",
        f"- Human action: `{decision['human_action']}`",
        f"- Policy: `{policy_gate['policy']}` -> `{policy_gate['status']}` / exit `{policy_gate['exit_code']}`",
        f"- Policy message: {policy_result['human_message']}",
        f"- Ref: `{source['pr_ref']}` at `{source['commit_sha']}`",
        f"- Report hash: `{source['report_sha256']}`",
        "",
        "Privacy: this workflow summary and policy gate output are metadata-only and exclude raw diffs, source bodies, finding evidence, report prose, endpoint secrets, model keys, and hidden reasoning traces.",
        "",
    ]
    summary = "\n".join(lines)
    reject_private_text(summary, label="Review Agent GitHub workflow dry-run summary")
    return summary


def evaluate_policy_matrix(policy_cli: Any, bundle_dir: Path) -> dict[str, dict[str, Any]]:
    matrix: dict[str, dict[str, Any]] = {}
    for policy in POLICIES:
        args = argparse.Namespace(
            bundle_dir=str(bundle_dir),
            receipt=None,
            policy=policy,
            output=None,
            generated_at=FIXED_GENERATED_AT,
        )
        payload = policy_cli.evaluate(args)
        summary = policy_cli.validate_gate_payload(payload)
        reject_private_text(payload, label=f"{bundle_dir.name} {policy} policy gate")
        matrix[policy] = {
            "decision": summary["decision"],
            "status": summary["status"],
            "exit_code": summary["exit_code"],
        }
    return matrix


def build_dry_run_for_fixture(module: Any, policy_cli: Any, fixture_name: str, output_root: Path) -> dict[str, Any]:
    fixture_id = fixture_name.removesuffix(".json")
    output_dir = output_root / fixture_id / "review-agent-acceptance"
    args = argparse.Namespace(
        report=str(REPORT_FIXTURE_DIR / fixture_name),
        output_dir=str(output_dir),
        provider_id=f"github-fixture-{fixture_id}-review-agent",
        provider_label=f"GitHub fixture {fixture_id} Review Agent",
        execution_surface="ci",
        pr_ref=f"PR-fixture-{fixture_id}",
        commit_sha=f"sha-fixture-{fixture_id}",
        base_ref="main",
        head_ref=f"codex/fixture-{fixture_id}",
        generated_at=FIXED_GENERATED_AT,
        validation_command="python3 scripts/cognitive_loop_review_agent_handoff.py validate --report REVIEW_AGENT_REPORT.json",
    )
    manifest = module.build_bundle(args)
    summary = module.validate_bundle_dir(output_dir)
    policy_matrix = evaluate_policy_matrix(policy_cli, output_dir)
    soft_args = argparse.Namespace(
        bundle_dir=str(output_dir),
        receipt=None,
        policy="soft",
        output=None,
        generated_at=FIXED_GENERATED_AT,
    )
    soft_policy_payload = policy_cli.evaluate(soft_args)
    policy_cli.validate_gate_payload(soft_policy_payload)
    checks_summary = render_checks_summary(output_dir, soft_policy_payload)
    serialized_public = dump_json(manifest) + checks_summary
    reject_private_text(serialized_public, label=f"{fixture_name} GitHub workflow dry-run output")
    return {
        "bundle_summary": summary,
        "checks_title": json.loads((output_dir / "review-agent-pr-comment-pack.json").read_text(encoding="utf-8"))[
            "checks_summary"
        ]["title"],
        "default_policy": "soft",
        "policy_matrix": policy_matrix,
        "checks_summary_sha256": module.load_module(module.RECEIPT_CLI_PATH, "study_anything_review_agent_receipt").sha256_text(
            checks_summary
        ),
        "uploaded_files": [
            "manifest.json",
            "SUMMARY.md",
            "review-agent-ci-receipt.json",
            "review-agent-pr-comment-pack.json",
            "review-agent-policy-gate.json",
            "review-agent-checks-summary.md",
        ],
    }


def validate_docs() -> dict[str, str]:
    docs = {
        "docs/cognitive-loop-code-review.md": [
            "platform/workflows/cognitive-loop-review-agent-manual.yml",
            "verify_cognitive_loop_review_agent_github_workflow.py --check",
        ],
        "docs/github-review-agent-workflow.md": [
            "workflow_dispatch",
            "metadata-only",
            "policy",
            "review-agent-policy-gate.json",
            "不调用真实模型",
            "verify_cognitive_loop_review_agent_github_workflow.py --check",
        ],
        "docs/eval-frameworks.md": [
            "cognitive-loop-review-agent-github-workflow-verification-v1",
            "verify_cognitive_loop_review_agent_github_workflow.py --check",
        ],
        "evals/README.md": [
            "verify_cognitive_loop_review_agent_github_workflow.py --check",
        ],
        ".cognitive-loop/evals.yaml": [
            "cognitive-loop.review-agent-github-workflow",
            "python3 scripts/verify_cognitive_loop_review_agent_github_workflow.py --check",
        ],
        "scripts/release_check.sh": [
            "scripts/verify_cognitive_loop_review_agent_github_workflow.py --check",
        ],
        "platform/packs/kimi/README.md": [
            "platform/workflows/cognitive-loop-review-agent-manual.yml",
            "verify_cognitive_loop_review_agent_github_workflow.py --check",
        ],
        "platform/packs/codex/README.md": [
            "platform/workflows/cognitive-loop-review-agent-manual.yml",
            "verify_cognitive_loop_review_agent_github_workflow.py --check",
        ],
        "platform/packs/workbuddy/README.md": [
            "platform/workflows/cognitive-loop-review-agent-manual.yml",
            "verify_cognitive_loop_review_agent_github_workflow.py --check",
        ],
        "scripts/generate_platform_bundle_manifest.py": [
            "platform/generated/study-anything-cognitive-loop-review-agent-github-workflow.json",
        ],
        "scripts/generate_platform_adoption_pack.py": [
            "platform/workflows/cognitive-loop-review-agent-manual.yml",
            "scripts/verify_cognitive_loop_review_agent_github_workflow.py",
        ],
    }
    checked: dict[str, str] = {}
    for relative, needles in docs.items():
        text = (ROOT / relative).read_text(encoding="utf-8")
        missing = [needle for needle in needles if needle not in text]
        require(not missing, f"{relative} missing Review Agent GitHub workflow references: {missing}")
        checked[relative] = "pass"
    return checked


def validate_platform_packs() -> dict[str, str]:
    required_assets = {
        "docs/github-review-agent-workflow.md",
        "platform/workflows/cognitive-loop-review-agent-manual.yml",
        "scripts/verify_cognitive_loop_review_agent_github_workflow.py",
        "platform/generated/study-anything-cognitive-loop-review-agent-github-workflow.json",
    }
    required_command = "python3 scripts/verify_cognitive_loop_review_agent_github_workflow.py --check"
    required_evidence = (
        "cognitive_loop_review_agent_github_workflow.schema_version == "
        "cognitive-loop-review-agent-github-workflow-verification-v1"
    )
    checked: dict[str, str] = {}
    for pack_id in ("codex", "kimi", "workbuddy", "hermes"):
        pack_path = ROOT / "platform" / "packs" / pack_id / "pack.json"
        pack = json.loads(pack_path.read_text(encoding="utf-8"))
        assets = {str(item) for item in pack.get("import_assets", [])}
        commands = "\n".join(str(item) for item in pack.get("local_verification_commands", []))
        evidence = {str(item) for item in pack.get("acceptance_evidence", [])}
        missing_assets = sorted(required_assets - assets)
        require(not missing_assets, f"{pack_path.relative_to(ROOT)} missing GitHub workflow assets: {missing_assets}")
        require(required_command in commands, f"{pack_path.relative_to(ROOT)} missing GitHub workflow command.")
        require(required_evidence in evidence, f"{pack_path.relative_to(ROOT)} missing GitHub workflow evidence.")
        checked[pack_id] = "pass"
    return checked


def build_report() -> dict[str, Any]:
    workflow = validate_workflow_template(WORKFLOW)
    negative = {"unsafe-auto-pr.yml": validate_unsafe_fixture()}
    module = load_bundle_cli()
    policy_cli = load_policy_gate_cli()
    with tempfile.TemporaryDirectory(prefix="study-anything-review-agent-github-workflow-") as tmp_name:
        output_root = Path(tmp_name)
        dry_runs = {
            fixture: build_dry_run_for_fixture(module, policy_cli, fixture, output_root)
            for fixture in REPORT_FIXTURES
        }
        existing_bundle = output_root / "existing-bundle"
        source_bundle = output_root / "needs-review" / "review-agent-acceptance"
        shutil.copytree(source_bundle, existing_bundle)
        existing_summary = module.validate_bundle_dir(existing_bundle)
    decisions = {value["bundle_summary"]["decision"] for value in dry_runs.values()}
    require(decisions == {"approved", "needs-review", "needs-fix"}, f"Dry-run decision coverage drifted: {sorted(decisions)}")
    policy_matrix = {
        fixture.removesuffix(".json"): dry_run["policy_matrix"] for fixture, dry_run in dry_runs.items()
    }
    require(
        policy_matrix["approved"]["strict"]["exit_code"] == 0,
        "Approved strict policy should pass.",
    )
    require(
        policy_matrix["needs-review"]["strict"]["exit_code"] == 2,
        "Needs-review strict policy should fail.",
    )
    require(
        policy_matrix["needs-review"]["soft"]["exit_code"] == 0,
        "Needs-review soft policy should not fail.",
    )
    require(
        policy_matrix["needs-fix"]["soft"]["exit_code"] == 2,
        "Needs-fix soft policy should fail.",
    )
    docs = validate_docs()
    packs = validate_platform_packs()
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "workflow_template": workflow,
        "dry_run_fixture_count": len(dry_runs),
        "dry_runs": dry_runs,
        "policy_matrix": policy_matrix,
        "existing_bundle_validation": existing_summary,
        "negative_workflows": negative,
        "docs": docs,
        "platform_packs": packs,
        "quality_gates": {
            "manual_only_trigger": "pass",
            "no_real_model_call": "pass",
            "no_external_agent_secret_required": "pass",
            "metadata_only_artifact_upload": "pass",
            "raw_report_not_uploaded": "pass",
            "policy_gate_wired": "pass",
            "policy_exit_preserved_after_artifact_upload": "pass",
            "checks_summary_metadata_only": "pass",
            "decision_path_coverage": sorted(decisions),
            "policy_path_coverage": list(POLICIES),
            "unsafe_workflow_rejection": "pass",
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
        "acceptance": {
            "workflow_template": "platform/workflows/cognitive-loop-review-agent-manual.yml",
            "minimum_command": "python3 scripts/verify_cognitive_loop_review_agent_github_workflow.py --check",
            "generated_report": "platform/generated/study-anything-cognitive-loop-review-agent-github-workflow.json",
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
            raise SystemExit(f"Cognitive Loop Review Agent GitHub workflow report is missing: {output}")
        current = output.read_text(encoding="utf-8")
        if current != serialized:
            raise SystemExit(
                "Cognitive Loop Review Agent GitHub workflow report is out of date. "
                "Run: python3 scripts/verify_cognitive_loop_review_agent_github_workflow.py --write"
            )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReviewAgentGithubWorkflowVerificationError as exc:
        raise SystemExit(f"error: {exc}") from exc
