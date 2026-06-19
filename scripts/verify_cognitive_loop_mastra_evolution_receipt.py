#!/usr/bin/env python3
"""Verify Cognitive Loop Mastra Evolution Receipt Link Lite."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "cognitive_loop_mastra_evolution_receipt.py"
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-mastra-evolution-receipt.json"
SCHEMA_VERSION = "cognitive-loop-mastra-evolution-receipt-verification-v1"
ARTIFACT_SCHEMA = "cognitive-loop-mastra-evolution-receipt-link-v1"


def run_json(command: list[str], *, cwd: Path = ROOT, required: bool = True) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if required and completed.returncode != 0:
        raise RuntimeError(
            f"Command failed ({completed.returncode}): {' '.join(command)}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    if completed.returncode != 0:
        return {"returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Command did not emit JSON: {' '.join(command)}\n{completed.stdout}") from exc


def assert_no_forbidden_text(text: str, *, label: str) -> None:
    forbidden = [
        "sk-proj-",
        "bearer ",
        "raw source text",
        "raw diff",
        "learner answer:",
        "diff --git",
        "api_key",
        "agent endpoint:",
        "agent metadata:",
        "http://127.0.0.1:8787",
        "OPENAI_API_KEY",
        "MOONSHOT_API_KEY",
        "disable tests",
        "lower risk threshold",
        "bypass human gate",
    ]
    lowered = text.lower()
    leaked = [needle for needle in forbidden if needle.lower() in lowered]
    if leaked:
        raise RuntimeError(f"{label} leaked forbidden text: {leaked}")


def write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def fixture_dir(root: Path) -> Path:
    return root / ".cognitive-loop" / "artifacts" / "mastra-fixtures"


def write_evolution(root: Path, *, risk: str = "low", gate: bool = False, status: str = "ready") -> Path:
    return write_json(
        fixture_dir(root) / f"evolution-{risk}-{gate}.json",
        {
            "schema_version": "cognitive-loop-evolution-report-lite-v1",
            "status": status,
            "proposed_improvements": [
                {
                    "target": "task",
                    "target_path": ".cognitive-loop/artifacts/patches/task-proposal.json",
                    "change": "Create a bounded task proposal for the next loop.",
                    "risk": risk,
                    "requires_human_mastery_gate": gate,
                }
            ],
            "privacy": {
                "source_text_included": False,
                "raw_diff_included": False,
                "learner_answers_included": False,
                "agent_endpoint_included": False,
                "agent_metadata_included": False,
                "prompt_text_included": False,
                "real_model_keys_stored": False,
            },
        },
    )


def write_apply_plan(root: Path) -> Path:
    return write_json(
        fixture_dir(root) / "apply-plan.json",
        {
            "schema_version": "cognitive-loop-apply-plan-lite-v1",
            "status": "dry_run_ready",
            "eligible_actions": [
                {
                    "target": "doc",
                    "target_path": ".cognitive-loop/artifacts/applied/apply-receipt.json",
                    "change": "Write a generated receipt marker only.",
                    "risk": "low",
                    "requires_human_mastery_gate": False,
                }
            ],
            "privacy": {
                "source_text_included": False,
                "raw_diff_included": False,
                "learner_answers_included": False,
                "agent_endpoint_included": False,
                "agent_metadata_included": False,
                "prompt_text_included": False,
                "real_model_keys_stored": False,
            },
        },
    )


def write_comparison(root: Path, status: str = "improved") -> Path:
    return write_json(
        fixture_dir(root) / f"comparison-{status}.json",
        {
            "schema_version": "cognitive-loop-improvement-comparison-lite-v1",
            "status": status,
            "artifact_metrics": [{"artifact_ref": "current", "score": 1.0}],
            "privacy": {
                "source_text_included": False,
                "raw_diff_included": False,
                "learner_answers_included": False,
                "agent_endpoint_included": False,
                "agent_metadata_included": False,
                "prompt_text_included": False,
                "real_model_keys_stored": False,
            },
        },
    )


def write_patch(root: Path, *, manual_only: bool = False) -> Path:
    return write_json(
        fixture_dir(root) / ("patch-manual.json" if manual_only else "patch-ready.json"),
        {
            "schema_version": "cognitive-loop-patch-proposal-lite-v1",
            "status": "needs_review" if manual_only else "ready",
            "patch_candidates": [] if manual_only else [
                {
                    "patch_id": "patch-doc",
                    "category": "doc",
                    "target_path": "docs/operator-note.md",
                    "intent": "Add a bounded operator note.",
                    "risk": "low",
                    "requires_human_mastery_gate": False,
                    "manual_only": False,
                    "manual_reason": "",
                }
            ],
            "manual_only_candidates": [
                {
                    "patch_id": "patch-policy",
                    "category": "policy",
                    "target_path": ".cognitive-loop/risk.yaml",
                    "intent": "Review risk policy manually.",
                    "risk": "high",
                    "requires_human_mastery_gate": True,
                    "manual_only": True,
                    "manual_reason": "Policy change requires maintainer review.",
                }
            ]
            if manual_only
            else [],
            "guardrails": {
                "read_only": True,
                "raw_unified_diff_generated": False,
                "apply_executed": False,
                "model_called": False,
                "daemon_started": False,
                "source_files_modified": False,
                "policy_weakened": False,
            },
            "privacy": {
                "source_text_included": False,
                "raw_diff_included": False,
                "learner_answers_included": False,
                "agent_endpoint_included": False,
                "agent_metadata_included": False,
                "prompt_text_included": False,
                "real_model_keys_stored": False,
            },
        },
    )


def run_link(root: Path, artifacts: list[Path]) -> tuple[dict[str, Any], str]:
    command = [
        sys.executable,
        str(CLI),
        "--root",
        str(root),
        "build",
        "--html",
        "--json",
        "--generated-at",
        "2026-01-01T00:00:00Z",
    ]
    for artifact in artifacts:
        command.extend(["--artifact", str(artifact.relative_to(root))])
    report = run_json(command)
    html = (root / report["outputs"]["html_ref"]).read_text(encoding="utf-8")
    assert_no_forbidden_text(json.dumps(report, ensure_ascii=False), label="mastra receipt report")
    assert_no_forbidden_text(html, label="mastra receipt html")
    if "Cognitive Loop Mastra Evolution Receipt Link Lite" not in html:
        raise RuntimeError("Mastra receipt HTML missed product title.")
    if "Artifact Links" not in html:
        raise RuntimeError("Mastra receipt HTML missed artifact links table.")
    guardrails = report.get("guardrails") or {}
    for key in ("read_only",):
        if guardrails.get(key) is not True:
            raise RuntimeError(f"Mastra receipt guardrail {key} must be true.")
    for key in ("raw_unified_diff_generated", "apply_executed", "model_called", "daemon_started", "mastra_workflow_started", "source_files_modified", "policy_weakened"):
        if guardrails.get(key) is not False:
            raise RuntimeError(f"Mastra receipt guardrail {key} must be false.")
    return report, html


def verify_success_modes() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-anything-mastra-evolution-") as tmp:
        root = Path(tmp)
        full_report, _ = run_link(
            root,
            [write_evolution(root), write_apply_plan(root), write_comparison(root), write_patch(root)],
        )
        single_report, _ = run_link(root, [write_evolution(root)])
        degraded_report, _ = run_link(
            root,
            [write_evolution(root), write_apply_plan(root), write_comparison(root, "insufficient"), write_patch(root)],
        )
    if full_report["status"] != "ready":
        raise RuntimeError("Full artifact set should be ready for Mastra receipt linkage.")
    if full_report["receipt"]["ready_for_mastra"] is not True:
        raise RuntimeError("Full artifact set should be marked ready_for_mastra.")
    if len(full_report["workflow_steps"]) != 4:
        raise RuntimeError("Mastra receipt link must expose four workflow steps.")
    if single_report["status"] != "degraded":
        raise RuntimeError("Single artifact should degrade due to missing roles.")
    if degraded_report["status"] != "degraded":
        raise RuntimeError("Insufficient comparison should degrade.")
    return {
        "full_set_status": full_report["status"],
        "single_artifact_status": single_report["status"],
        "insufficient_comparison_status": degraded_report["status"],
        "workflow_step_count": len(full_report["workflow_steps"]),
        "html_json_created": True,
        "read_only": True,
    }


def verify_blocked_modes() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-anything-mastra-evolution-blocked-") as tmp:
        root = Path(tmp)
        high_report, _ = run_link(root, [write_evolution(root, risk="high", gate=False), write_apply_plan(root), write_comparison(root), write_patch(root)])
        manual_report, _ = run_link(root, [write_evolution(root), write_apply_plan(root), write_comparison(root), write_patch(root, manual_only=True)])
        privacy = fixture_dir(root) / "privacy-regression.json"
        write_json(
            privacy,
            {
                "schema_version": "cognitive-loop-apply-plan-lite-v1",
                "status": "dry_run_ready",
                "privacy": {"raw_diff_included": True},
            },
        )
        privacy_report, _ = run_link(root, [write_evolution(root), privacy, write_comparison(root), write_patch(root)])
    if high_report["status"] != "blocked":
        raise RuntimeError("High-risk ungated artifact should block runtime linkage.")
    if manual_report["status"] != "blocked":
        raise RuntimeError("Manual-only PatchProposal should block runtime linkage.")
    if privacy_report["status"] != "blocked":
        raise RuntimeError("Privacy flag regression should block runtime linkage.")
    return {
        "high_risk_gate_blocked": True,
        "manual_patch_blocked": True,
        "privacy_regression_blocked": True,
    }


def verify_failure_modes() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-anything-mastra-evolution-failures-") as tmp:
        root = Path(tmp)
        unsupported = write_json(fixture_dir(root) / "unsupported.json", {"schema_version": "unknown-v1", "status": "ready"})
        secret = write_json(
            fixture_dir(root) / "secret.json",
            {
                "schema_version": "cognitive-loop-evolution-report-lite-v1",
                "status": "ready",
                "proposed_improvements": [{"target": "task", "change": "OPENAI_API_KEY=sk-proj-abcdefghijklmnop", "risk": "low"}],
            },
        )
        raw_diff = write_json(
            fixture_dir(root) / "raw-diff.json",
            {
                "schema_version": "cognitive-loop-evolution-report-lite-v1",
                "status": "ready",
                "proposed_improvements": [{"target": "task", "change": "diff --git a/app.py b/app.py", "risk": "low"}],
            },
        )
        weak_policy = write_json(
            fixture_dir(root) / "weak-policy.json",
            {
                "schema_version": "cognitive-loop-evolution-report-lite-v1",
                "status": "ready",
                "proposed_improvements": [{"target": "task", "change": "disable tests before release", "risk": "low"}],
            },
        )
        unsupported_result = run_json([sys.executable, str(CLI), "--root", str(root), "build", "--artifact", str(unsupported.relative_to(root)), "--json"], required=False)
        secret_result = run_json([sys.executable, str(CLI), "--root", str(root), "build", "--artifact", str(secret.relative_to(root)), "--json"], required=False)
        diff_result = run_json([sys.executable, str(CLI), "--root", str(root), "build", "--artifact", str(raw_diff.relative_to(root)), "--json"], required=False)
        weak_result = run_json([sys.executable, str(CLI), "--root", str(root), "build", "--artifact", str(weak_policy.relative_to(root)), "--json"], required=False)
    if unsupported_result["returncode"] == 0:
        raise RuntimeError("Unsupported schema should fail.")
    if secret_result["returncode"] == 0:
        raise RuntimeError("Secret-like artifact should fail.")
    if diff_result["returncode"] == 0:
        raise RuntimeError("Raw diff artifact should fail.")
    if weak_result["returncode"] == 0:
        raise RuntimeError("Policy weakening artifact should fail.")
    return {
        "unsupported_schema_rejected": True,
        "secret_artifact_rejected": True,
        "raw_diff_artifact_rejected": True,
        "policy_weakening_rejected": True,
    }


def build_report() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "version": "v0.3.31-alpha",
        "cli": "scripts/cognitive_loop_mastra_evolution_receipt.py",
        "artifact_schema": ARTIFACT_SCHEMA,
        "success_modes": verify_success_modes(),
        "blocked_modes": verify_blocked_modes(),
        "failure_modes": verify_failure_modes(),
        "acceptance": {
            "minimum_command": "python3 scripts/verify_cognitive_loop_mastra_evolution_receipt.py --check",
            "example_command": "python3 scripts/cognitive_loop_mastra_evolution_receipt.py build --artifact evidence.json --html --json",
            "release_gate": "scripts/release_check.sh",
        },
        "privacy": {
            "read_only": True,
            "source_text_included": False,
            "raw_diff_included": False,
            "learner_answers_included": False,
            "agent_endpoint_included": False,
            "agent_metadata_included": False,
            "prompt_text_included": False,
            "real_model_keys_stored": False,
            "model_called": False,
            "daemon_started": False,
            "mastra_workflow_started": False,
            "apply_executed": False,
            "raw_unified_diff_generated": False,
            "policy_weakened": False,
            "source_files_modified": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = build_report()
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    assert_no_forbidden_text(text, label="verification report")
    if args.write:
        REPORT.write_text(text, encoding="utf-8")
        return 0
    if args.check:
        if not REPORT.exists():
            raise RuntimeError(f"Missing generated report: {REPORT.relative_to(ROOT)}")
        current = REPORT.read_text(encoding="utf-8")
        if current != text:
            raise RuntimeError(
                "Cognitive Loop Mastra Evolution Receipt Link Lite report is stale. "
                "Run `python3 scripts/verify_cognitive_loop_mastra_evolution_receipt.py --write`."
            )
        print("ok    Cognitive Loop Mastra Evolution Receipt Link Lite report is up to date")
        return 0
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
