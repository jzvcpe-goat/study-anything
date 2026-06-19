#!/usr/bin/env python3
"""Verify Cognitive Loop Professional Evolution Pack Export Lite."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any
import zipfile
import hashlib


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "cognitive_loop_evolution_pack_export.py"
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-evolution-pack-export.json"
SCHEMA_VERSION = "cognitive-loop-evolution-pack-export-verification-v1"
MANIFEST_SCHEMA_VERSION = "cognitive-loop-evolution-pack-manifest-v1"
ARCHIVE_ROOT = "cognitive-loop-professional-evolution-pack"

CONSOLE = ".cognitive-loop/artifacts/console/manifest.json"
EVOLUTION_REPORT = ".cognitive-loop/artifacts/evolution/evolution-report-lite.json"
APPLY_PLAN = ".cognitive-loop/artifacts/applied/apply-plan-lite.json"
IMPROVEMENT = ".cognitive-loop/artifacts/comparison/improvement-comparison-lite.json"
PATCH_PROPOSAL = ".cognitive-loop/artifacts/patches/patch-proposal-lite.json"
EVOLUTION_RECEIPT = ".cognitive-loop/artifacts/mastra/mastra-evolution-receipt-link.json"
EVOLUTION_REPLAY = ".cognitive-loop/artifacts/mastra/mastra-evolution-workflow-replay.json"
PATCH_SANDBOX = ".cognitive-loop/artifacts/applied/patch-apply-sandbox-receipt.json"


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


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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


def write_html(path: Path, title: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "<!doctype html><html><head><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>{title}</title></head><body><h1>{title}</h1></body></html>\n",
        encoding="utf-8",
    )


def privacy_flags() -> dict[str, bool]:
    return {
        "metadata_only": True,
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
        "metadata_only": True,
        "raw_unified_diff_generated": False,
        "apply_executed": False,
        "model_called": False,
        "daemon_started": False,
        "production_mastra_daemon_started": False,
        "mastra_workflow_started": False,
        "source_files_modified": False,
        "real_source_mutated": False,
        "policy_weakened": False,
    }


def outputs_for(json_ref: str) -> dict[str, str]:
    html_ref = json_ref.removesuffix(".json") + ".html"
    return {"json_ref": json_ref, "html_ref": html_ref}


def write_artifact(root: Path, relative: str, payload: dict[str, Any], title: str) -> None:
    payload.setdefault("privacy", privacy_flags())
    payload.setdefault("guardrails", guardrails())
    payload.setdefault("outputs", outputs_for(relative))
    write_json(root / relative, payload)
    write_html(root / payload["outputs"]["html_ref"], title)


def write_ready_pack(root: Path) -> None:
    write_artifact(
        root,
        CONSOLE,
        {
            "schema_version": "cognitive-loop-artifact-console-v1",
            "status": "ready",
            "title": "Cognitive Loop HTML Artifact Console Lite",
            "sections": {"evolution_chain": {"status": "ready", "artifact_count": 7}},
            "artifact_refs": {"html": ".cognitive-loop/artifacts/console/index.html", "manifest": CONSOLE},
        },
        "Artifact Console",
    )
    write_artifact(
        root,
        EVOLUTION_REPORT,
        {
            "schema_version": "cognitive-loop-evolution-report-lite-v1",
            "status": "ready",
            "report_id": "evolution-report-fixture",
            "proposed_improvements": [{"category": "docs", "risk": "low", "summary": "Clarify operator handoff."}],
        },
        "Evolution Report",
    )
    write_artifact(
        root,
        APPLY_PLAN,
        {
            "schema_version": "cognitive-loop-apply-plan-lite-v1",
            "status": "dry_run_ready",
            "plan_id": "apply-plan-fixture",
            "eligible_actions": [
                {
                    "action_id": "apply-fixture",
                    "target": "generated-artifact",
                    "target_path": ".cognitive-loop/artifacts/applied/apply-receipt.json",
                    "risk": "low",
                    "source_files_modified": False,
                }
            ],
            "manual_only_actions": [],
            "human_mastery_gate": {"required": False, "status": "not_required"},
        },
        "Governed Apply Plan",
    )
    write_artifact(
        root,
        IMPROVEMENT,
        {
            "schema_version": "cognitive-loop-improvement-comparison-lite-v1",
            "status": "improved",
            "comparison_id": "comparison-fixture",
            "metrics": {"before": 0.7, "after": 0.9},
        },
        "Improvement Comparison",
    )
    write_artifact(
        root,
        PATCH_PROPOSAL,
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
        },
        "Patch Proposal",
    )
    write_artifact(
        root,
        EVOLUTION_RECEIPT,
        {
            "schema_version": "cognitive-loop-mastra-evolution-receipt-link-v1",
            "status": "ready",
            "link_id": "receipt-link-fixture",
            "artifact_links": [],
            "missing_roles": [],
        },
        "Evolution Receipt Link",
    )
    write_artifact(
        root,
        EVOLUTION_REPLAY,
        {
            "schema_version": "cognitive-loop-mastra-evolution-workflow-replay-v1",
            "status": "replay_ready",
            "replay_id": "replay-fixture",
            "replay_summary": {
                "manual_review_required": False,
                "blocked": False,
                "replay_status": "replay_ready",
            },
        },
        "Mastra Workflow Replay",
    )
    write_artifact(
        root,
        PATCH_SANDBOX,
        {
            "schema_version": "cognitive-loop-patch-apply-sandbox-receipt-v1",
            "status": "sandbox_ready",
            "receipt_id": "patch-sandbox-fixture",
            "sandbox": {
                "mode": "metadata_only_temp_preview",
                "sandbox_path_hash": "abc123",
                "sandbox_ref": "temp://patch-apply-sandbox/fixture",
                "temporary_workspace_removed": True,
                "real_worktree_apply_executed": False,
                "source_files_modified": False,
                "no_real_source_mutation": True,
            },
            "rollback_proof": {
                "required": True,
                "proved": True,
                "temporary_workspace_removed": True,
                "source_files_modified": False,
                "no_real_source_mutation": True,
            },
        },
        "Patch Apply Sandbox",
    )


def mutate_manual(root: Path) -> None:
    payload = json.loads((root / APPLY_PLAN).read_text(encoding="utf-8"))
    payload["status"] = "manual_only"
    payload["eligible_actions"] = []
    payload["manual_only_actions"] = [
        {
            "action_id": "manual-fixture",
            "target": "generated-artifact",
            "target_path": ".cognitive-loop/artifacts/applied/manual-review.json",
            "reason": "Manual review required before export handoff.",
            "risk": "medium",
            "source_files_modified": False,
        }
    ]
    payload["human_mastery_gate"] = {"required": True, "status": "manual_review_required"}
    write_json(root / APPLY_PLAN, payload)


def mutate_blocked(root: Path) -> None:
    payload = json.loads((root / EVOLUTION_REPLAY).read_text(encoding="utf-8"))
    payload["status"] = "blocked"
    payload["blockers"] = ["manual review must resolve blocked replay before export"]
    payload["replay_summary"]["blocked"] = True
    write_json(root / EVOLUTION_REPLAY, payload)


def run_export(root: Path) -> tuple[dict[str, Any], str, bytes]:
    report = run_json(
        [
            sys.executable,
            str(CLI),
            "--root",
            str(root),
            "export",
            "--html",
            "--json",
            "--zip",
            "--generated-at",
            "2026-01-01T00:00:00Z",
        ]
    )
    manifest_path = root / report["outputs"]["json_ref"]
    html_path = root / report["outputs"]["html_ref"]
    zip_path = root / report["outputs"]["zip_ref"]
    if json.loads(manifest_path.read_text(encoding="utf-8")) != report:
        raise RuntimeError("Evolution pack stdout JSON and manifest file drifted.")
    html = html_path.read_text(encoding="utf-8")
    zip_bytes = zip_path.read_bytes()
    assert_no_forbidden_text(json.dumps(report, ensure_ascii=False), label="evolution pack manifest")
    assert_no_forbidden_text(html, label="evolution pack html")
    if report["schema_version"] != MANIFEST_SCHEMA_VERSION:
        raise RuntimeError("Evolution Pack emitted an unexpected schema.")
    if report["no_real_source_mutation"] is not True:
        raise RuntimeError("Evolution Pack must assert no real source mutation.")
    if report["no_model_calls"] is not True or report["no_raw_payloads"] is not True:
        raise RuntimeError("Evolution Pack must assert no model calls and no raw payloads.")
    if "Cognitive Loop Professional Evolution Pack" not in html:
        raise RuntimeError("Evolution Pack HTML missed product title.")
    if "Artifact Chain" not in html or "Pack Files" not in html:
        raise RuntimeError("Evolution Pack HTML missed required sections.")
    if 'name="viewport"' not in html or "@media" not in html:
        raise RuntimeError("Evolution Pack HTML missed mobile-friendly structure.")
    verify_zip(zip_path, report)
    return report, html, zip_bytes


def verify_zip(zip_path: Path, manifest: dict[str, Any]) -> None:
    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
        required = {f"{ARCHIVE_ROOT}/manifest.json", f"{ARCHIVE_ROOT}/index.html"}
        missing = required - names
        if missing:
            raise RuntimeError(f"Evolution Pack ZIP missed required entries: {sorted(missing)}")
        zipped_manifest = json.loads(archive.read(f"{ARCHIVE_ROOT}/manifest.json").decode("utf-8"))
        if zipped_manifest != manifest:
            raise RuntimeError("Evolution Pack ZIP manifest drifted from output manifest.")
        for record in manifest["pack_files"]:
            archive_path = record["archive_path"]
            if archive_path not in names:
                raise RuntimeError(f"Evolution Pack ZIP missed pack file: {archive_path}")
            if sha256_bytes(archive.read(archive_path)) != record["sha256"]:
                raise RuntimeError(f"Evolution Pack ZIP entry hash drifted: {archive_path}")


def verify_success_modes() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-anything-evolution-pack-ready-") as tmp:
        root = Path(tmp)
        write_ready_pack(root)
        source = root / "source.py"
        source.write_text("print('unchanged')\n", encoding="utf-8")
        before = source.read_bytes()
        ready, _html, zip_bytes = run_export(root)
        after = source.read_bytes()
        if before != after:
            raise RuntimeError("Evolution Pack export modified a source fixture.")
    if ready["status"] != "pack_ready":
        raise RuntimeError("Ready chain should become pack_ready.")
    if ready["artifact_count"] != 8 or ready["missing_artifact_count"] != 0:
        raise RuntimeError("Ready chain must include all eight pack inputs.")
    if len(ready["pack_files"]) < 9:
        raise RuntimeError("Evolution Pack should include index plus artifact files.")
    return {
        "ready_status": ready["status"],
        "artifact_count": ready["artifact_count"],
        "pack_file_count": len(ready["pack_files"]),
        "zip_sha256": sha256_bytes(zip_bytes),
        "source_fixture_unchanged": True,
        "zip_extract_verified": True,
    }


def verify_non_ready_modes() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-anything-evolution-pack-non-ready-") as tmp:
        manual_root = Path(tmp) / "manual"
        manual_root.mkdir()
        write_ready_pack(manual_root)
        mutate_manual(manual_root)
        manual, _html, _zip = run_export(manual_root)

        blocked_root = Path(tmp) / "blocked"
        blocked_root.mkdir()
        write_ready_pack(blocked_root)
        mutate_blocked(blocked_root)
        blocked, _html, _zip = run_export(blocked_root)

        missing_root = Path(tmp) / "missing"
        missing_root.mkdir()
        missing, _html, _zip = run_export(missing_root)
    if manual["status"] != "manual_review":
        raise RuntimeError("Manual chain should require manual_review.")
    if blocked["status"] != "blocked":
        raise RuntimeError("Blocked chain should stay blocked.")
    if missing["status"] != "degraded_missing_artifacts":
        raise RuntimeError("Missing chain should degrade instead of failing.")
    if missing["missing_artifact_count"] != 8:
        raise RuntimeError("Missing chain should report all missing pack artifacts.")
    return {
        "manual_status": manual["status"],
        "blocked_status": blocked["status"],
        "missing_status": missing["status"],
        "missing_artifact_count": missing["missing_artifact_count"],
    }


def write_unsafe_patch(root: Path, patch_payload: dict[str, Any]) -> None:
    write_ready_pack(root)
    write_json(root / PATCH_PROPOSAL, patch_payload)


def expect_failure(root: Path, name: str, patch_payload: dict[str, Any]) -> bool:
    write_unsafe_patch(root, patch_payload)
    result = run_json(
        [
            sys.executable,
            str(CLI),
            "--root",
            str(root),
            "export",
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
        "outputs": outputs_for(PATCH_PROPOSAL),
    }
    with tempfile.TemporaryDirectory(prefix="study-anything-evolution-pack-failures-") as tmp:
        root = Path(tmp)
        invalid_schema = dict(base, schema_version="wrong-schema")
        secret = dict(base, patch_candidates=[dict(base["patch_candidates"][0], intent="OPENAI_API_KEY=sk-proj-abcdefghijklmnop")])
        raw_diff = dict(base, patch_candidates=[dict(base["patch_candidates"][0], intent="diff --git a/file b/file")])
        privacy = dict(base, privacy=privacy_flags() | {"raw_diff_included": True})
        policy = dict(base, patch_candidates=[dict(base["patch_candidates"][0], intent="disable tests for this patch")])
        protected = dict(base, patch_candidates=[dict(base["patch_candidates"][0], target_path=".env")])
        results = {
            "invalid_schema_rejected": expect_failure(root / "invalid", "invalid_schema", invalid_schema),
            "secret_like_rejected": expect_failure(root / "secret", "secret", secret),
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
        "manifest_schema": MANIFEST_SCHEMA_VERSION,
        "cli": "scripts/cognitive_loop_evolution_pack_export.py",
        "commands": {
            "export": "python3 scripts/cognitive_loop_evolution_pack_export.py export --html --json --zip",
            "verify": "python3 scripts/verify_cognitive_loop_evolution_pack_export.py --check",
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
            "raw_payloads_included": False,
        },
        "runtime_boundaries": {
            "standalone_frontend_required": False,
            "production_mastra_daemon_started": False,
            "model_called": False,
            "real_worktree_apply_executed": False,
            "source_files_modified": False,
        },
    }
    assert_no_forbidden_text(json.dumps(report, ensure_ascii=False), label="evolution pack verification report")
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
            raise SystemExit("generated evolution pack export report is stale; run with --write")
        print("ok    Cognitive Loop evolution pack export report is up to date")
        return 0
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
