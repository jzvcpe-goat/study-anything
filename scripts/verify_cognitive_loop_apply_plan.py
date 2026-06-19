#!/usr/bin/env python3
"""Verify Cognitive Loop Governed Apply Plan Lite."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "cognitive_loop_apply_plan.py"
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-apply-plan.json"
SCHEMA_VERSION = "cognitive-loop-apply-plan-verification-v1"


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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def write_low_risk_proposal(root: Path) -> Path:
    path = root / ".cognitive-loop" / "artifacts" / "evolution" / "low-risk.json"
    write_json(
        path,
        {
            "schema_version": "cognitive-loop-evolution-report-lite-v1",
            "status": "ready",
            "proposed_improvements": [
                {
                    "target": "task",
                    "change": "Record an operator note for the next loop.",
                    "risk": "low",
                    "auto_apply": False,
                    "explicitly_allowed": True,
                    "requires_human_mastery_gate": False,
                    "target_path": ".cognitive-loop/artifacts/applied/apply-receipt.json",
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
    return path


def write_high_risk_proposal(root: Path) -> Path:
    path = root / ".cognitive-loop" / "artifacts" / "evolution" / "high-risk.json"
    write_json(
        path,
        {
            "schema_version": "cognitive-loop-evolution-report-lite-v1",
            "status": "needs_review",
            "proposed_improvements": [
                {
                    "target": "policy",
                    "change": "Require human review before risky changes.",
                    "risk": "high",
                    "requires_human_mastery_gate": True,
                    "target_path": ".cognitive-loop/artifacts/applied/apply-receipt.json",
                }
            ],
        },
    )
    return path


def write_forbidden_path_proposal(root: Path) -> Path:
    path = root / ".cognitive-loop" / "artifacts" / "evolution" / "forbidden-path.json"
    write_json(
        path,
        {
            "schema_version": "cognitive-loop-evolution-report-lite-v1",
            "status": "ready",
            "proposed_improvements": [
                {
                    "target": "doc",
                    "change": "Update public docs directly.",
                    "risk": "low",
                    "explicitly_allowed": True,
                    "requires_human_mastery_gate": False,
                    "target_path": "README.md",
                }
            ],
        },
    )
    return path


def run_apply_plan(root: Path, proposal: Path, extra: list[str]) -> tuple[dict[str, Any], str]:
    report = run_json(
        [
            sys.executable,
            str(CLI),
            "--root",
            str(root),
            "plan",
            "--proposal",
            str(proposal.relative_to(root)),
            "--html",
            "--json",
            "--generated-at",
            "2026-01-01T00:00:00Z",
            *extra,
        ]
    )
    html = (root / report["outputs"]["html_ref"]).read_text(encoding="utf-8")
    assert_no_forbidden_text(json.dumps(report, ensure_ascii=False), label="apply plan report")
    assert_no_forbidden_text(html, label="apply plan html")
    if "Cognitive Loop Governed Apply Plan Lite" not in html:
        raise RuntimeError("Apply Plan HTML missed product title.")
    if "Eligible Generated-Artifact Receipt Actions" not in html or "Manual-Only Actions" not in html:
        raise RuntimeError("Apply Plan HTML missed required sections.")
    if report["guardrails"]["dry_run_default"] is not True:
        raise RuntimeError("Apply Plan must be dry-run by default.")
    if report["guardrails"]["source_files_modified"] is not False:
        raise RuntimeError("Apply Plan must not modify source files.")
    return report, html


def verify_success_modes() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-anything-apply-plan-") as tmp:
        root = Path(tmp)
        proposal = write_low_risk_proposal(root)
        before_hash = sha256_file(proposal)
        dry_run, _ = run_apply_plan(root, proposal, [])
        after_dry_hash = sha256_file(proposal)
        if before_hash != after_dry_hash:
            raise RuntimeError("Dry-run modified proposal input.")
        if dry_run["status"] != "dry_run_ready":
            raise RuntimeError("Low-risk dry-run should be ready.")
        if dry_run["receipt"]["applied"] is not False:
            raise RuntimeError("Dry-run receipt must not be applied.")
        apply_without_allow = run_json(
            [
                sys.executable,
                str(CLI),
                "--root",
                str(root),
                "plan",
                "--proposal",
                str(proposal.relative_to(root)),
                "--apply",
                "--json",
            ],
            required=False,
        )
        applied, _ = run_apply_plan(root, proposal, ["--apply", "--allow-generated-artifacts"])
        first_receipt_hash = sha256_file(root / applied["outputs"]["receipt_ref"])
        applied_again, _ = run_apply_plan(root, proposal, ["--apply", "--allow-generated-artifacts"])
        second_receipt_hash = sha256_file(root / applied_again["outputs"]["receipt_ref"])
        after_apply_hash = sha256_file(proposal)
        if before_hash != after_apply_hash:
            raise RuntimeError("Apply modified proposal input.")
        if apply_without_allow["returncode"] == 0:
            raise RuntimeError("--apply without --allow-generated-artifacts should fail.")
        if applied["status"] != "applied" or applied["receipt"]["applied"] is not True:
            raise RuntimeError("Explicit low-risk apply should write an applied receipt.")
        if applied["receipt"]["receipt_id"] != applied_again["receipt"]["receipt_id"]:
            raise RuntimeError("Apply receipt id is not idempotent.")
        if first_receipt_hash != second_receipt_hash:
            raise RuntimeError("Apply receipt file is not idempotent.")
        marker = root / applied["outputs"]["marker_ref"]
        if not marker.is_file():
            raise RuntimeError("Apply marker was not written.")
    return {
        "dry_run_status": dry_run["status"],
        "apply_status": applied["status"],
        "eligible_action_count": len(applied["eligible_actions"]),
        "receipt_written": True,
        "marker_written": True,
        "input_hash_unchanged": True,
        "apply_requires_allow_flag": True,
        "idempotent_receipt": True,
        "html_json_created": True,
    }


def verify_manual_and_failure_modes() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-anything-apply-plan-failures-") as tmp:
        root = Path(tmp)
        high_risk = write_high_risk_proposal(root)
        forbidden_path = write_forbidden_path_proposal(root)
        high_dry, _ = run_apply_plan(root, high_risk, [])
        high_apply = run_json(
            [
                sys.executable,
                str(CLI),
                "--root",
                str(root),
                "plan",
                "--proposal",
                str(high_risk.relative_to(root)),
                "--apply",
                "--allow-generated-artifacts",
                "--json",
            ],
            required=False,
        )
        forbidden_apply = run_json(
            [
                sys.executable,
                str(CLI),
                "--root",
                str(root),
                "plan",
                "--proposal",
                str(forbidden_path.relative_to(root)),
                "--apply",
                "--allow-generated-artifacts",
                "--json",
            ],
            required=False,
        )
        secret = root / ".cognitive-loop" / "artifacts" / "evolution" / "secret.json"
        write_json(
            secret,
            {
                "schema_version": "cognitive-loop-evolution-report-lite-v1",
                "status": "ready",
                "proposed_improvements": [
                    {"target": "task", "risk": "low", "change": "OPENAI_API_KEY=sk-proj-abcdefghijklmnop"}
                ],
            },
        )
        raw_diff = root / ".cognitive-loop" / "artifacts" / "evolution" / "raw-diff.json"
        write_json(
            raw_diff,
            {
                "schema_version": "cognitive-loop-evolution-report-lite-v1",
                "status": "ready",
                "proposed_improvements": [
                    {"target": "task", "risk": "low", "change": "diff --git a/app.py b/app.py"}
                ],
            },
        )
        weak_policy = root / ".cognitive-loop" / "artifacts" / "evolution" / "weak-policy.json"
        write_json(
            weak_policy,
            {
                "schema_version": "cognitive-loop-evolution-report-lite-v1",
                "status": "ready",
                "proposed_improvements": [
                    {"target": "task", "risk": "low", "change": "disable tests to speed up release"}
                ],
            },
        )
        secret_result = run_json(
            [sys.executable, str(CLI), "--root", str(root), "plan", "--proposal", str(secret.relative_to(root)), "--json"],
            required=False,
        )
        diff_result = run_json(
            [sys.executable, str(CLI), "--root", str(root), "plan", "--proposal", str(raw_diff.relative_to(root)), "--json"],
            required=False,
        )
        weak_result = run_json(
            [sys.executable, str(CLI), "--root", str(root), "plan", "--proposal", str(weak_policy.relative_to(root)), "--json"],
            required=False,
        )
    if high_dry["status"] != "manual_only":
        raise RuntimeError("High-risk dry-run should degrade to manual-only.")
    if high_apply["returncode"] == 0:
        raise RuntimeError("High-risk apply should fail.")
    if forbidden_apply["returncode"] == 0:
        raise RuntimeError("Forbidden target apply should fail.")
    if secret_result["returncode"] == 0:
        raise RuntimeError("Secret-like proposal should fail.")
    if diff_result["returncode"] == 0:
        raise RuntimeError("Raw diff proposal should fail.")
    if weak_result["returncode"] == 0:
        raise RuntimeError("Policy-weakening proposal should fail.")
    return {
        "high_risk_manual_only": True,
        "high_risk_apply_rejected": True,
        "forbidden_path_apply_rejected": True,
        "secret_proposal_rejected": True,
        "raw_diff_proposal_rejected": True,
        "policy_weakening_rejected": True,
    }


def build_report() -> dict[str, Any]:
    success = verify_success_modes()
    failures = verify_manual_and_failure_modes()
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "version": "v0.3.31-alpha",
        "cli": "scripts/cognitive_loop_apply_plan.py",
        "artifact_schema": "cognitive-loop-apply-plan-lite-v1",
        "receipt_schema": "cognitive-loop-apply-receipt-lite-v1",
        "success_modes": success,
        "failure_modes": failures,
        "acceptance": {
            "minimum_command": "python3 scripts/verify_cognitive_loop_apply_plan.py --check",
            "example_command": "python3 scripts/cognitive_loop_apply_plan.py plan --proposal .cognitive-loop/artifacts/evolution/evolution-report-lite.json --html --json",
            "explicit_apply_command": "python3 scripts/cognitive_loop_apply_plan.py plan --proposal .cognitive-loop/artifacts/evolution/evolution-report-lite.json --apply --allow-generated-artifacts --html --json",
            "release_gate": "scripts/release_check.sh",
        },
        "privacy": {
            "source_text_included": False,
            "raw_diff_included": False,
            "learner_answers_included": False,
            "agent_endpoint_included": False,
            "agent_metadata_included": False,
            "prompt_text_included": False,
            "real_model_keys_stored": False,
            "model_called": False,
            "daemon_started": False,
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
                "Cognitive Loop Apply Plan Lite report is stale. "
                "Run `python3 scripts/verify_cognitive_loop_apply_plan.py --write`."
            )
        print("ok    Cognitive Loop Apply Plan Lite report is up to date")
        return 0
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
