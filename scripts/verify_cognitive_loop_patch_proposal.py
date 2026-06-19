#!/usr/bin/env python3
"""Verify Cognitive Loop Patch Proposal Lite."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "cognitive_loop_patch_proposal.py"
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-patch-proposal.json"
SCHEMA_VERSION = "cognitive-loop-patch-proposal-verification-v1"
PATCH_CATEGORIES = ("prompt", "policy", "eval", "task", "doc", "retrieval")


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


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_low_risk_artifact(root: Path) -> Path:
    path = root / ".cognitive-loop" / "artifacts" / "patch-fixtures" / "low-risk.json"
    write_json(
        path,
        {
            "schema_version": "cognitive-loop-evolution-report-lite-v1",
            "status": "ready",
            "proposed_improvements": [
                {
                    "target": category,
                    "target_path": f"{'docs' if category == 'doc' else 'evals' if category == 'eval' else '.cognitive-loop/artifacts/patches'}/{category}-proposal.json",
                    "change": f"Create a bounded {category} patch specification.",
                    "risk": "low",
                    "requires_human_mastery_gate": False,
                }
                for category in PATCH_CATEGORIES
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
    return path


def write_mixed_artifact(root: Path) -> Path:
    path = root / ".cognitive-loop" / "artifacts" / "patch-fixtures" / "mixed.json"
    write_json(
        path,
        {
            "schema_version": "cognitive-loop-apply-plan-lite-v1",
            "status": "dry_run_ready",
            "eligible_actions": [
                {
                    "target": "doc",
                    "target_path": "docs/operator-note.md",
                    "change": "Add a bounded operator note.",
                    "risk": "low",
                    "requires_human_mastery_gate": False,
                }
            ],
            "manual_only_actions": [
                {
                    "target": "policy",
                    "target_path": ".cognitive-loop/risk.yaml",
                    "reason": "Risk policy changes need manual review.",
                    "risk": "high",
                    "requires_human_mastery_gate": True,
                }
            ],
        },
    )
    return path


def write_single_improvement(root: Path, name: str, **item: Any) -> Path:
    path = root / ".cognitive-loop" / "artifacts" / "patch-fixtures" / f"{name}.json"
    payload = {
        "schema_version": "cognitive-loop-evolution-report-lite-v1",
        "status": "ready",
        "proposed_improvements": [item],
    }
    write_json(path, payload)
    return path


def write_comparison(root: Path, name: str, status: str) -> Path:
    path = root / ".cognitive-loop" / "artifacts" / "patch-fixtures" / f"{name}.json"
    write_json(
        path,
        {
            "schema_version": "cognitive-loop-improvement-comparison-lite-v1",
            "status": status,
            "artifact_metrics": [],
            "delta": {},
        },
    )
    return path


def run_patch(root: Path, artifacts: list[Path]) -> tuple[dict[str, Any], str]:
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
    assert_no_forbidden_text(json.dumps(report, ensure_ascii=False), label="patch proposal report")
    assert_no_forbidden_text(html, label="patch proposal html")
    if "Cognitive Loop Patch Proposal Lite" not in html:
        raise RuntimeError("Patch Proposal HTML missed product title.")
    if "Patch Candidates" not in html or "Manual-Only Candidates" not in html:
        raise RuntimeError("Patch Proposal HTML missed required sections.")
    if report["guardrails"]["read_only"] is not True:
        raise RuntimeError("Patch Proposal must be read-only.")
    if report["guardrails"]["raw_unified_diff_generated"] is not False:
        raise RuntimeError("Patch Proposal must not generate raw unified diffs.")
    if report["guardrails"]["source_files_modified"] is not False:
        raise RuntimeError("Patch Proposal must not modify source files.")
    if report["guardrails"]["apply_executed"] is not False:
        raise RuntimeError("Patch Proposal must not execute apply.")
    return report, html


def verify_success_modes() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-anything-patch-proposal-") as tmp:
        root = Path(tmp)
        low = write_low_risk_artifact(root)
        mixed = write_mixed_artifact(root)
        low_report, _ = run_patch(root, [low])
        mixed_report, _ = run_patch(root, [mixed])
    if low_report["status"] != "ready":
        raise RuntimeError("Low-risk patch proposal should be ready.")
    if len(low_report["patch_candidates"]) != len(PATCH_CATEGORIES):
        raise RuntimeError("Low-risk patch proposal missed one or more categories.")
    for category in PATCH_CATEGORIES:
        if low_report["coverage"].get(category) != 1:
            raise RuntimeError(f"Patch category {category} must be covered.")
    if mixed_report["status"] != "needs_review":
        raise RuntimeError("Mixed patch proposal should require review.")
    if len(mixed_report["manual_only_candidates"]) < 1:
        raise RuntimeError("Mixed patch proposal must keep manual-only candidates.")
    return {
        "low_risk_status": low_report["status"],
        "category_count": len(PATCH_CATEGORIES),
        "mixed_status": mixed_report["status"],
        "mixed_manual_only_count": len(mixed_report["manual_only_candidates"]),
        "html_json_created": True,
        "read_only": True,
    }


def verify_manual_and_degraded_modes() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-anything-patch-proposal-manual-") as tmp:
        root = Path(tmp)
        high = write_single_improvement(
            root,
            "high",
            target="task",
            target_path=".cognitive-loop/artifacts/patches/high.json",
            change="Record a high risk task change.",
            risk="high",
        )
        gated = write_single_improvement(
            root,
            "gated",
            target="task",
            target_path=".cognitive-loop/artifacts/patches/gated.json",
            change="Record a gated task change.",
            risk="low",
            requires_human_mastery_gate=True,
        )
        forbidden = write_single_improvement(
            root,
            "forbidden",
            target="policy",
            target_path=".env",
            change="Record protected path change.",
            risk="low",
        )
        insufficient = write_comparison(root, "insufficient", "insufficient")
        high_report, _ = run_patch(root, [high])
        gated_report, _ = run_patch(root, [gated])
        forbidden_report, _ = run_patch(root, [forbidden])
        degraded_report, _ = run_patch(root, [insufficient])
    if high_report["status"] != "manual_only":
        raise RuntimeError("High-risk proposal should be manual-only.")
    if gated_report["status"] != "manual_only":
        raise RuntimeError("Human-gated proposal should be manual-only.")
    if forbidden_report["status"] != "manual_only":
        raise RuntimeError("Forbidden target proposal should be manual-only.")
    if degraded_report["status"] != "degraded":
        raise RuntimeError("Insufficient comparison should degrade.")
    return {
        "high_risk_manual_only": True,
        "human_gate_manual_only": True,
        "forbidden_path_manual_only": True,
        "insufficient_comparison_degraded": True,
    }


def verify_failure_modes() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-anything-patch-proposal-failures-") as tmp:
        root = Path(tmp)
        secret = write_single_improvement(
            root,
            "secret",
            target="task",
            change="OPENAI_API_KEY=sk-proj-abcdefghijklmnop",
            risk="low",
        )
        raw_diff = write_single_improvement(
            root,
            "raw-diff",
            target="task",
            change="diff --git a/app.py b/app.py",
            risk="low",
        )
        weak_policy = write_single_improvement(
            root,
            "weak-policy",
            target="task",
            change="disable tests to speed up release",
            risk="low",
        )
        invalid_schema = root / ".cognitive-loop" / "artifacts" / "patch-fixtures" / "invalid-schema.json"
        write_json(invalid_schema, {"status": "ready"})
        secret_result = run_json(
            [sys.executable, str(CLI), "--root", str(root), "build", "--artifact", str(secret.relative_to(root)), "--json"],
            required=False,
        )
        diff_result = run_json(
            [sys.executable, str(CLI), "--root", str(root), "build", "--artifact", str(raw_diff.relative_to(root)), "--json"],
            required=False,
        )
        weak_result = run_json(
            [sys.executable, str(CLI), "--root", str(root), "build", "--artifact", str(weak_policy.relative_to(root)), "--json"],
            required=False,
        )
        invalid_result = run_json(
            [sys.executable, str(CLI), "--root", str(root), "build", "--artifact", str(invalid_schema.relative_to(root)), "--json"],
            required=False,
        )
    if secret_result["returncode"] == 0:
        raise RuntimeError("Secret-like proposal should fail.")
    if diff_result["returncode"] == 0:
        raise RuntimeError("Raw diff proposal should fail.")
    if weak_result["returncode"] == 0:
        raise RuntimeError("Policy weakening proposal should fail.")
    if invalid_result["returncode"] == 0:
        raise RuntimeError("Invalid schema proposal should fail.")
    return {
        "secret_proposal_rejected": True,
        "raw_diff_proposal_rejected": True,
        "policy_weakening_rejected": True,
        "invalid_schema_rejected": True,
    }


def build_report() -> dict[str, Any]:
    success = verify_success_modes()
    manual = verify_manual_and_degraded_modes()
    failures = verify_failure_modes()
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "version": "v0.3.31-alpha",
        "cli": "scripts/cognitive_loop_patch_proposal.py",
        "artifact_schema": "cognitive-loop-patch-proposal-lite-v1",
        "success_modes": success,
        "manual_modes": manual,
        "failure_modes": failures,
        "acceptance": {
            "minimum_command": "python3 scripts/verify_cognitive_loop_patch_proposal.py --check",
            "example_command": "python3 scripts/cognitive_loop_patch_proposal.py build --artifact evidence.json --html --json",
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
                "Cognitive Loop Patch Proposal Lite report is stale. "
                "Run `python3 scripts/verify_cognitive_loop_patch_proposal.py --write`."
            )
        print("ok    Cognitive Loop Patch Proposal Lite report is up to date")
        return 0
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
