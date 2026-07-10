#!/usr/bin/env python3
"""Verify Cognitive Loop Governed Patch Apply Sandbox Lite."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from shutil import copyfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "cognitive_loop_patch_apply_sandbox.py"
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-patch-apply-sandbox.json"
SCHEMA_VERSION = "cognitive-loop-patch-apply-sandbox-verification-v1"
RECEIPT_SCHEMA_VERSION = "cognitive-loop-patch-apply-sandbox-receipt-v1"

PATCH_PROPOSAL = ".cognitive-loop/artifacts/patches/patch-proposal-lite.json"
APPLY_PLAN = ".cognitive-loop/artifacts/applied/apply-plan-lite.json"
EVOLUTION_RECEIPT = ".cognitive-loop/artifacts/mastra/mastra-evolution-receipt-link.json"
EVOLUTION_REPLAY = ".cognitive-loop/artifacts/mastra/mastra-evolution-workflow-replay.json"
SECRET_PATCH_FIXTURE = (
    ROOT / "fixtures" / "codeql-negative" / "patch-apply-proposal-secret.json"
)


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


def privacy_flags() -> dict[str, bool]:
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


def guardrails() -> dict[str, bool]:
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


def write_ready_chain(root: Path) -> None:
    write_json(
        root / PATCH_PROPOSAL,
        {
            "schema_version": "cognitive-loop-patch-proposal-lite-v1",
            "status": "ready",
            "proposal_id": "patch-proposal-fixture",
            "patch_candidates": [
                {
                    "patch_id": "patch-fixture",
                    "category": "task",
                    "target_path": ".cognitive-loop/artifacts/patches/task-proposal.json",
                    "intent": "Create a bounded task patch specification.",
                    "risk": "low",
                    "requires_human_mastery_gate": False,
                    "manual_only": False,
                }
            ],
            "manual_only_candidates": [],
            "guardrails": guardrails(),
            "privacy": privacy_flags(),
        },
    )
    write_json(
        root / APPLY_PLAN,
        {
            "schema_version": "cognitive-loop-apply-plan-lite-v1",
            "status": "dry_run_ready",
            "plan_id": "apply-plan-fixture",
            "eligible_actions": [
                {
                    "action_id": "apply-fixture",
                    "target": "task",
                    "target_path": ".cognitive-loop/artifacts/applied/apply-receipt.json",
                    "change": "Record generated-artifact receipt.",
                    "risk": "low",
                    "source_files_modified": False,
                }
            ],
            "manual_only_actions": [],
            "human_mastery_gate": {"required": False, "status": "not_required"},
            "guardrails": guardrails() | {"dry_run_default": True, "explicit_apply_required": True},
            "privacy": privacy_flags(),
        },
    )
    write_json(
        root / EVOLUTION_RECEIPT,
        {
            "schema_version": "cognitive-loop-mastra-evolution-receipt-link-v1",
            "status": "ready",
            "link_id": "receipt-link-fixture",
            "artifact_links": [],
            "missing_roles": [],
            "guardrails": guardrails(),
            "privacy": privacy_flags(),
        },
    )
    write_json(
        root / EVOLUTION_REPLAY,
        {
            "schema_version": "cognitive-loop-mastra-evolution-workflow-replay-v1",
            "status": "replay_ready",
            "replay_id": "replay-fixture",
            "replay_summary": {
                "manual_review_required": False,
                "blocked": False,
                "replay_status": "replay_ready",
            },
            "guardrails": guardrails(),
            "privacy": privacy_flags(),
        },
    )


def mutate_manual_chain(root: Path) -> None:
    payload = json.loads((root / APPLY_PLAN).read_text(encoding="utf-8"))
    payload["status"] = "manual_only"
    payload["eligible_actions"] = []
    payload["manual_only_actions"] = [
        {
            "action_id": "manual-fixture",
            "target": "task",
            "target_path": ".cognitive-loop/artifacts/applied/manual-review.json",
            "reason": "Manual review required before sandbox preview.",
            "risk": "medium",
            "source_files_modified": False,
        }
    ]
    payload["human_mastery_gate"] = {"required": True, "status": "manual_review_required"}
    write_json(root / APPLY_PLAN, payload)


def mutate_blocked_chain(root: Path) -> None:
    payload = json.loads((root / EVOLUTION_RECEIPT).read_text(encoding="utf-8"))
    payload["status"] = "blocked"
    payload["blockers"] = ["manual review must be resolved before promotion"]
    write_json(root / EVOLUTION_RECEIPT, payload)
    replay = json.loads((root / EVOLUTION_REPLAY).read_text(encoding="utf-8"))
    replay["status"] = "blocked"
    replay["replay_summary"]["blocked"] = True
    write_json(root / EVOLUTION_REPLAY, replay)


def run_sandbox(root: Path) -> tuple[dict[str, Any], str]:
    report = run_json(
        [
            sys.executable,
            str(CLI),
            "--root",
            str(root),
            "sandbox",
            "--html",
            "--json",
            "--generated-at",
            "2026-01-01T00:00:00Z",
        ]
    )
    html = (root / report["outputs"]["html_ref"]).read_text(encoding="utf-8")
    assert_no_forbidden_text(json.dumps(report, ensure_ascii=False), label="patch apply sandbox report")
    assert_no_forbidden_text(html, label="patch apply sandbox html")
    if report["schema_version"] != RECEIPT_SCHEMA_VERSION:
        raise RuntimeError("Patch Apply Sandbox emitted an unexpected schema.")
    if report["sandbox"]["no_real_source_mutation"] is not True:
        raise RuntimeError("Patch Apply Sandbox must assert no real source mutation.")
    if report["rollback_proof"]["proved"] is not True:
        raise RuntimeError("Patch Apply Sandbox must include rollback proof.")
    if report["guardrails"]["apply_executed"] is not False:
        raise RuntimeError("Patch Apply Sandbox must not execute apply.")
    if report["guardrails"]["source_files_modified"] is not False:
        raise RuntimeError("Patch Apply Sandbox must not modify source files.")
    if "Cognitive Loop Governed Patch Apply Sandbox Lite" not in html:
        raise RuntimeError("Patch Apply Sandbox HTML missed product title.")
    if "Artifact Chain" not in html or "Sandbox Boundary" not in html:
        raise RuntimeError("Patch Apply Sandbox HTML missed required sections.")
    if 'name="viewport"' not in html or "@media" not in html:
        raise RuntimeError("Patch Apply Sandbox HTML missed mobile-friendly structure.")
    return report, html


def verify_success_modes() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-anything-patch-sandbox-ready-") as tmp:
        root = Path(tmp)
        write_ready_chain(root)
        source = root / "source.py"
        source.write_text("print('unchanged')\n", encoding="utf-8")
        before = source.read_bytes()
        ready, _ = run_sandbox(root)
        after = source.read_bytes()
        if before != after:
            raise RuntimeError("Patch Apply Sandbox modified a source fixture.")
    if ready["status"] != "sandbox_ready":
        raise RuntimeError("Ready chain should become sandbox_ready.")
    if ready["artifact_count"] != 4 or ready["missing_artifact_count"] != 0:
        raise RuntimeError("Ready chain must include all four sandbox inputs.")
    if ready["dry_run"]["eligible_actions"] != 1:
        raise RuntimeError("Ready chain should expose one eligible dry-run action.")
    return {
        "ready_status": ready["status"],
        "artifact_count": ready["artifact_count"],
        "rollback_proved": ready["rollback_proof"]["proved"],
        "source_fixture_unchanged": True,
        "html_json_created": True,
    }


def verify_non_ready_modes() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-anything-patch-sandbox-non-ready-") as tmp:
        manual_root = Path(tmp) / "manual"
        manual_root.mkdir()
        write_ready_chain(manual_root)
        mutate_manual_chain(manual_root)
        manual, _ = run_sandbox(manual_root)

        blocked_root = Path(tmp) / "blocked"
        blocked_root.mkdir()
        write_ready_chain(blocked_root)
        mutate_blocked_chain(blocked_root)
        blocked, _ = run_sandbox(blocked_root)

        missing_root = Path(tmp) / "missing"
        missing_root.mkdir()
        missing, _ = run_sandbox(missing_root)
    if manual["status"] != "manual_review":
        raise RuntimeError("Manual chain should require manual_review.")
    if blocked["status"] != "blocked":
        raise RuntimeError("Blocked chain should stay blocked.")
    if missing["status"] != "degraded_missing_artifacts":
        raise RuntimeError("Missing chain should degrade instead of failing.")
    if missing["missing_artifact_count"] != 4:
        raise RuntimeError("Missing chain should report all missing sandbox artifacts.")
    return {
        "manual_status": manual["status"],
        "blocked_status": blocked["status"],
        "missing_status": missing["status"],
        "missing_artifact_count": missing["missing_artifact_count"],
    }


def write_unsafe_patch(root: Path, name: str, patch_payload: dict[str, Any]) -> None:
    del name
    write_ready_chain(root)
    write_json(root / PATCH_PROPOSAL, patch_payload)


def write_static_unsafe_patch(root: Path, fixture_path: Path) -> None:
    write_ready_chain(root)
    target = root / PATCH_PROPOSAL
    target.parent.mkdir(parents=True, exist_ok=True)
    copyfile(fixture_path, target)


def expect_failure(root: Path, name: str, patch_payload: dict[str, Any]) -> bool:
    write_unsafe_patch(root, name, patch_payload)
    result = run_json(
        [
            sys.executable,
            str(CLI),
            "--root",
            str(root),
            "sandbox",
            "--json",
            "--generated-at",
            "2026-01-01T00:00:00Z",
        ],
        required=False,
    )
    if result["returncode"] == 0:
        raise RuntimeError(f"Unsafe fixture was not rejected: {name}")
    return True


def expect_static_failure(root: Path, name: str, fixture_path: Path) -> bool:
    write_static_unsafe_patch(root, fixture_path)
    result = run_json(
        [
            sys.executable,
            str(CLI),
            "--root",
            str(root),
            "sandbox",
            "--json",
            "--generated-at",
            "2026-01-01T00:00:00Z",
        ],
        required=False,
    )
    if result["returncode"] == 0:
        raise RuntimeError(f"Unsafe fixture was not rejected: {name}")
    return True


def verify_failure_modes() -> dict[str, bool]:
    base = {
        "schema_version": "cognitive-loop-patch-proposal-lite-v1",
        "status": "ready",
        "patch_candidates": [
            {
                "patch_id": "patch-fixture",
                "category": "task",
                "target_path": ".cognitive-loop/artifacts/patches/task-proposal.json",
                "intent": "Create a bounded task patch specification.",
                "risk": "low",
            }
        ],
        "manual_only_candidates": [],
        "guardrails": guardrails(),
        "privacy": privacy_flags(),
    }
    with tempfile.TemporaryDirectory(prefix="study-anything-patch-sandbox-failures-") as tmp:
        root = Path(tmp)
        invalid_schema = dict(base, schema_version="wrong-schema")
        raw_diff = dict(base, patch_candidates=[dict(base["patch_candidates"][0], intent="diff --git a/file b/file")])
        privacy = dict(base, privacy=privacy_flags() | {"raw_diff_included": True})
        policy = dict(base, patch_candidates=[dict(base["patch_candidates"][0], intent="disable tests for this patch")])
        protected = dict(base, patch_candidates=[dict(base["patch_candidates"][0], target_path=".env")])
        results = {
            "invalid_schema_rejected": expect_failure(root / "invalid", "invalid_schema", invalid_schema),
            "secret_like_rejected": expect_static_failure(
                root / "secret",
                "secret",
                SECRET_PATCH_FIXTURE,
            ),
            "raw_diff_rejected": expect_failure(root / "raw-diff", "raw_diff", raw_diff),
            "privacy_regression_rejected": expect_failure(root / "privacy", "privacy", privacy),
            "policy_weakening_rejected": expect_failure(root / "policy", "policy", policy),
            "protected_path_rejected": expect_failure(root / "protected", "protected", protected),
        }
    return results


def build_report() -> dict[str, Any]:
    success = verify_success_modes()
    non_ready = verify_non_ready_modes()
    failures = verify_failure_modes()
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "sandbox_receipt_schema": RECEIPT_SCHEMA_VERSION,
        "cli": "scripts/cognitive_loop_patch_apply_sandbox.py",
        "commands": {
            "sandbox": "python3 scripts/cognitive_loop_patch_apply_sandbox.py sandbox --html --json",
            "verify": "python3 scripts/verify_cognitive_loop_patch_apply_sandbox.py --check",
            "console": "python3 scripts/cognitive_loop_artifact_console.py build --html --json",
        },
        "success_modes": success,
        "non_ready_modes": non_ready,
        "failure_modes": failures,
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
            "production_mastra_started": False,
            "apply_executed": False,
            "real_source_mutated": False,
        },
        "runtime_boundaries": {
            "standalone_frontend_required": False,
            "production_mastra_daemon_started": False,
            "model_called": False,
            "real_worktree_apply_executed": False,
            "source_files_modified": False,
        },
    }
    assert_no_forbidden_text(json.dumps(report, ensure_ascii=False), label="patch apply sandbox verification report")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Write generated verification report.")
    parser.add_argument("--check", action="store_true", help="Require generated verification report to be up to date.")
    args = parser.parse_args()
    report = build_report()
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.write:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(rendered, encoding="utf-8")
        print(f"wrote {REPORT.relative_to(ROOT)}")
        return 0
    if args.check:
        current = REPORT.read_text(encoding="utf-8") if REPORT.is_file() else ""
        if current != rendered:
            raise SystemExit("generated patch apply sandbox report is stale; run with --write")
        print("ok    Cognitive Loop patch apply sandbox report is up to date")
        return 0
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
