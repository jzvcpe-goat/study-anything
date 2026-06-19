#!/usr/bin/env python3
"""Verify Cognitive Loop Mastra Evolution Workflow Replay Lite."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "cognitive_loop_mastra_evolution_replay.py"
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-mastra-evolution-replay.json"
SCHEMA_VERSION = "cognitive-loop-mastra-evolution-replay-verification-v1"
ARTIFACT_SCHEMA = "cognitive-loop-mastra-evolution-workflow-replay-v1"
RECEIPT_SCHEMA = "cognitive-loop-mastra-evolution-receipt-link-v1"
REQUIRED_ROLES = ("evolution_report", "apply_plan", "improvement_comparison", "patch_proposal")


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


def base_privacy() -> dict[str, bool]:
    return {
        "source_text_included": False,
        "raw_diff_included": False,
        "learner_answers_included": False,
        "agent_endpoint_included": False,
        "agent_metadata_included": False,
        "prompt_text_included": False,
        "real_model_keys_stored": False,
        "model_called": False,
        "daemon_started": False,
    }


def base_guardrails() -> dict[str, bool]:
    return {
        "read_only": True,
        "raw_unified_diff_generated": False,
        "apply_executed": False,
        "model_called": False,
        "daemon_started": False,
        "production_mastra_daemon_started": False,
        "mastra_workflow_started": False,
        "source_files_modified": False,
        "policy_weakened": False,
    }


def artifact_links(*, blocked_role: str | None = None, blocker: str | None = None) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    for role in REQUIRED_ROLES:
        blocked = role == blocked_role
        links.append(
            {
                "role": role,
                "schema_version": f"fixture-{role}-v1",
                "status": "blocked" if blocked else "ready",
                "ref": f".cognitive-loop/artifacts/fixtures/{role}.json",
                "sha256": "0" * 64,
                "accepted_for_mastra_receipt": not blocked,
                "blockers": [blocker] if blocked and blocker else [],
                "privacy_regressions": [],
            }
        )
    return links


def write_receipt(
    root: Path,
    *,
    status: str,
    missing_roles: list[str] | None = None,
    blocked_role: str | None = None,
    blocker: str | None = None,
    privacy_override: dict[str, Any] | None = None,
) -> Path:
    missing_roles = missing_roles or []
    links = [item for item in artifact_links(blocked_role=blocked_role, blocker=blocker) if item["role"] not in missing_roles]
    blockers = []
    if blocked_role and blocker:
        blockers.append({"role": blocked_role, "ref": f".cognitive-loop/artifacts/fixtures/{blocked_role}.json", "blockers": [blocker]})
    privacy = base_privacy()
    if privacy_override:
        privacy.update(privacy_override)
    payload = {
        "schema_version": RECEIPT_SCHEMA,
        "status": status,
        "link_id": f"link-{status}",
        "generated_at": "2026-01-01T00:00:00Z",
        "artifact_count": len(links),
        "artifact_links": links,
        "missing_roles": missing_roles,
        "degraded_reasons": [f"Missing required role(s): {', '.join(missing_roles)}"] if missing_roles else [],
        "blockers": blockers,
        "receipt": {
            "ready_for_mastra": status == "ready",
            "linked_roles": [item["role"] for item in links],
            "human_mastery_gate_required": bool(blocker and "Human Mastery Gate" in blocker),
            "manual_only_required": bool(blocker and "manual-only" in blocker),
        },
        "guardrails": base_guardrails(),
        "privacy": privacy,
    }
    return write_json(fixture_dir(root) / f"receipt-{status}-{len(missing_roles)}-{blocked_role or 'none'}.json", payload)


def run_replay(root: Path, receipt: Path) -> tuple[dict[str, Any], str]:
    command = [
        sys.executable,
        str(CLI),
        "--root",
        str(root),
        "replay",
        "--receipt",
        str(receipt.relative_to(root)),
        "--html",
        "--json",
        "--generated-at",
        "2026-01-01T00:00:00Z",
    ]
    report = run_json(command)
    html = (root / report["outputs"]["html_ref"]).read_text(encoding="utf-8")
    assert_no_forbidden_text(json.dumps(report, ensure_ascii=False), label="mastra replay report")
    assert_no_forbidden_text(html, label="mastra replay html")
    if report.get("schema_version") != ARTIFACT_SCHEMA:
        raise RuntimeError("Replay artifact schema drifted.")
    if "Cognitive Loop Mastra Evolution Workflow Replay Lite" not in html:
        raise RuntimeError("Replay HTML missed product title.")
    if "Workflow Steps" not in html:
        raise RuntimeError("Replay HTML missed workflow steps table.")
    if len(report.get("workflow_steps") or []) != 6:
        raise RuntimeError("Replay artifact must expose six workflow steps.")
    guardrails = report.get("guardrails") or {}
    if guardrails.get("read_only") is not True:
        raise RuntimeError("Replay guardrail read_only must be true.")
    for key in (
        "raw_unified_diff_generated",
        "apply_executed",
        "model_called",
        "daemon_started",
        "production_mastra_daemon_started",
        "mastra_workflow_started",
        "source_files_modified",
        "policy_weakened",
    ):
        if guardrails.get(key) is not False:
            raise RuntimeError(f"Replay guardrail {key} must be false.")
    return report, html


def verify_success_modes() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-anything-mastra-replay-") as tmp:
        root = Path(tmp)
        ready, _ = run_replay(root, write_receipt(root, status="ready"))
        degraded, _ = run_replay(root, write_receipt(root, status="degraded", missing_roles=["patch_proposal"]))
        blocked_high, _ = run_replay(
            root,
            write_receipt(
                root,
                status="blocked",
                blocked_role="evolution_report",
                blocker="high-risk artifact lacks Human Mastery Gate",
            ),
        )
        blocked_manual, _ = run_replay(
            root,
            write_receipt(
                root,
                status="blocked",
                blocked_role="patch_proposal",
                blocker="PatchProposal contains manual-only or review-required candidates",
            ),
        )
    if ready["status"] != "replay_ready":
        raise RuntimeError("Ready receipt should become replay_ready.")
    if degraded["status"] != "manual_review":
        raise RuntimeError("Degraded receipt should become manual_review.")
    if blocked_high["status"] != "blocked":
        raise RuntimeError("High-risk blocked receipt should remain blocked.")
    if blocked_manual["status"] != "blocked":
        raise RuntimeError("Manual-only patch receipt should remain blocked.")
    if ready["replay_summary"]["ready_for_future_mastra_workflow"] is not True:
        raise RuntimeError("Ready replay should mark future workflow readiness.")
    if degraded["replay_summary"]["manual_review_required"] is not True:
        raise RuntimeError("Degraded replay should require manual review.")
    if blocked_high["replay_summary"]["high_risk_blocked"] is not True:
        raise RuntimeError("High-risk blocker should be preserved in summary.")
    if blocked_manual["replay_summary"]["manual_patch_blocked"] is not True:
        raise RuntimeError("Manual-only patch blocker should be preserved in summary.")
    return {
        "ready_status": ready["status"],
        "degraded_status": degraded["status"],
        "blocked_high_risk_status": blocked_high["status"],
        "blocked_manual_patch_status": blocked_manual["status"],
        "workflow_step_count": len(ready["workflow_steps"]),
        "html_json_created": True,
        "read_only": True,
    }


def verify_failure_modes() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-anything-mastra-replay-failures-") as tmp:
        root = Path(tmp)
        invalid_schema = write_json(fixture_dir(root) / "invalid-schema.json", {"schema_version": "unknown-v1", "status": "ready"})
        unsupported_status = write_receipt(root, status="executed")
        ready_missing = write_receipt(root, status="ready", missing_roles=["patch_proposal"])
        high_risk_not_blocked = write_receipt(
            root,
            status="ready",
            blocked_role="evolution_report",
            blocker="high-risk artifact lacks Human Mastery Gate",
        )
        manual_not_blocked = write_receipt(
            root,
            status="degraded",
            blocked_role="patch_proposal",
            blocker="PatchProposal contains manual-only or review-required candidates",
        )
        privacy_regression = write_receipt(root, status="ready", privacy_override={"raw_diff_included": True})
        secret = write_json(
            fixture_dir(root) / "secret.json",
            {
                "schema_version": RECEIPT_SCHEMA,
                "status": "ready",
                "link_id": "secret",
                "artifact_links": [],
                "missing_roles": [],
                "degraded_reasons": ["OPENAI_API_KEY=sk-proj-abcdefghijklmnop"],
                "guardrails": base_guardrails(),
                "privacy": base_privacy(),
            },
        )
        raw_diff = write_json(
            fixture_dir(root) / "raw-diff.json",
            {
                "schema_version": RECEIPT_SCHEMA,
                "status": "ready",
                "link_id": "raw-diff",
                "artifact_links": [],
                "missing_roles": [],
                "degraded_reasons": ["diff --git a/app.py b/app.py"],
                "guardrails": base_guardrails(),
                "privacy": base_privacy(),
            },
        )
        weak_policy = write_json(
            fixture_dir(root) / "weak-policy.json",
            {
                "schema_version": RECEIPT_SCHEMA,
                "status": "ready",
                "link_id": "weak-policy",
                "artifact_links": [],
                "missing_roles": [],
                "degraded_reasons": ["disable tests before release"],
                "guardrails": base_guardrails(),
                "privacy": base_privacy(),
            },
        )

        def attempt(path: Path) -> dict[str, Any]:
            return run_json(
                [
                    sys.executable,
                    str(CLI),
                    "--root",
                    str(root),
                    "replay",
                    "--receipt",
                    str(path.relative_to(root)),
                    "--json",
                ],
                required=False,
            )

        results = {
            "invalid_schema_rejected": attempt(invalid_schema)["returncode"] != 0,
            "unsupported_status_rejected": attempt(unsupported_status)["returncode"] != 0,
            "ready_missing_roles_rejected": attempt(ready_missing)["returncode"] != 0,
            "high_risk_ungated_rejected": attempt(high_risk_not_blocked)["returncode"] != 0,
            "manual_only_patch_rejected": attempt(manual_not_blocked)["returncode"] != 0,
            "privacy_regression_rejected": attempt(privacy_regression)["returncode"] != 0,
            "secret_receipt_rejected": attempt(secret)["returncode"] != 0,
            "raw_diff_receipt_rejected": attempt(raw_diff)["returncode"] != 0,
            "policy_weakening_rejected": attempt(weak_policy)["returncode"] != 0,
        }
    failed = [key for key, value in results.items() if not value]
    if failed:
        raise RuntimeError(f"Replay failure-mode checks did not reject: {failed}")
    return results


def build_report() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "version": "v0.3.31-alpha",
        "cli": "scripts/cognitive_loop_mastra_evolution_replay.py",
        "artifact_schema": ARTIFACT_SCHEMA,
        "receipt_schema": RECEIPT_SCHEMA,
        "success_modes": verify_success_modes(),
        "failure_modes": verify_failure_modes(),
        "acceptance": {
            "minimum_command": "python3 scripts/verify_cognitive_loop_mastra_evolution_replay.py --check",
            "example_command": "python3 scripts/cognitive_loop_mastra_evolution_replay.py replay --receipt .cognitive-loop/artifacts/mastra/mastra-evolution-receipt-link.json --html --json",
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
            "production_mastra_daemon_started": False,
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
                "Cognitive Loop Mastra Evolution Workflow Replay Lite report is stale. "
                "Run `python3 scripts/verify_cognitive_loop_mastra_evolution_replay.py --write`."
            )
        print("ok    Cognitive Loop Mastra Evolution Workflow Replay Lite report is up to date")
        return 0
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
