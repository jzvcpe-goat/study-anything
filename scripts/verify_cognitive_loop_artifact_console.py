#!/usr/bin/env python3
"""Verify Cognitive Loop HTML Artifact Console Lite."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-artifact-console.json"
CONSOLE = ROOT / "scripts" / "cognitive_loop_artifact_console.py"
CLI = ROOT / "scripts" / "cognitive_loop_cli.py"
WATCHER_INGEST = ROOT / "scripts" / "cognitive_loop_watcher_ingest.py"
WATCHER_RUNNER = ROOT / "scripts" / "cognitive_loop_watcher_runner.py"
EVOLUTION = ROOT / "scripts" / "cognitive_loop_evolution.py"
APPLY_PLAN = ROOT / "scripts" / "cognitive_loop_apply_plan.py"
IMPROVEMENT = ROOT / "scripts" / "cognitive_loop_improvement_comparator.py"
PATCH_PROPOSAL = ROOT / "scripts" / "cognitive_loop_patch_proposal.py"
EVOLUTION_RECEIPT = ROOT / "scripts" / "cognitive_loop_mastra_evolution_receipt.py"
EVOLUTION_REPLAY = ROOT / "scripts" / "cognitive_loop_mastra_evolution_replay.py"
PATCH_APPLY_SANDBOX = ROOT / "scripts" / "cognitive_loop_patch_apply_sandbox.py"
SCHEMA_VERSION = "cognitive-loop-artifact-console-verification-v1"
EVOLUTION_CHAIN_REFS = {
    "evolution_report": ".cognitive-loop/artifacts/evolution/evolution-report-lite.json",
    "apply_plan": ".cognitive-loop/artifacts/applied/apply-plan-lite.json",
    "improvement_comparison": ".cognitive-loop/artifacts/comparison/improvement-comparison-lite.json",
    "patch_proposal": ".cognitive-loop/artifacts/patches/patch-proposal-lite.json",
    "evolution_receipt_link": ".cognitive-loop/artifacts/mastra/mastra-evolution-receipt-link.json",
    "mastra_workflow_replay": ".cognitive-loop/artifacts/mastra/mastra-evolution-workflow-replay.json",
    "patch_apply_sandbox": ".cognitive-loop/artifacts/applied/patch-apply-sandbox-receipt.json",
}


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
        "raw private source text",
        "private source text",
        "learner answer:",
        "diff --git",
        "raw source text",
        "api_key",
        "agent endpoint:",
        "agent metadata:",
        "prompt:",
        "http://127.0.0.1:8787",
        "raw test output",
        "OPENAI_API_KEY",
        "MOONSHOT_API_KEY",
    ]
    lowered = text.lower()
    leaked = [needle for needle in forbidden if needle.lower() in lowered]
    if leaked:
        raise RuntimeError(f"{label} leaked forbidden text: {leaked}")


def init_project(root: Path) -> None:
    run_json(
        [
            sys.executable,
            str(CLI),
            "--root",
            str(root),
            "init",
            "--project-id",
            "artifact-console-project",
            "--project-name",
            "Artifact Console Project",
            "--json",
        ]
    )


def write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def build_console(root: Path, *, html: bool = True) -> tuple[dict[str, Any], str]:
    html_path = root / ".cognitive-loop" / "artifacts" / "console" / "index.html"
    manifest_path = root / ".cognitive-loop" / "artifacts" / "console" / "manifest.json"
    args = [
        sys.executable,
        str(CONSOLE),
        "build",
        "--root",
        str(root),
        "--json",
        "--output",
        ".cognitive-loop/artifacts/console/index.html",
        "--json-output",
        ".cognitive-loop/artifacts/console/manifest.json",
    ]
    if html:
        args.insert(args.index("--json"), "--html")
    report = run_json(args)
    html_text = html_path.read_text(encoding="utf-8") if html else ""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if report != manifest:
        raise RuntimeError("Console stdout JSON and manifest JSON drifted.")
    assert_no_forbidden_text(json.dumps(manifest, ensure_ascii=False), label="console manifest")
    if html:
        assert_no_forbidden_text(html_text, label="console HTML")
    return manifest, html_text


def run_watcher_runner(root: Path) -> dict[str, Any]:
    run_json([sys.executable, str(WATCHER_INGEST), "--root", str(root), "init-config", "--force"])
    return run_json(
        [
            sys.executable,
            str(WATCHER_RUNNER),
            "--root",
            str(root),
            "run",
            "--html",
            "--json",
            "--study-adapter",
            "--poll-cycles",
            "2",
            "--changed-path",
            "apps/api/study_anything/core/workflow.py",
            "--changed-path",
            "apps/api/study_anything/core/workflow.py",
            "--changed-path",
            ".env",
            "--git-diff-summary",
            "Metadata-only workflow boundary changed.",
            "--test-failure-summary",
            "API tests failed before the current fix.",
            "--generated-at",
            "2026-01-01T00:00:00Z",
        ]
    )


def run_evolution_chain(root: Path) -> dict[str, Any]:
    evidence = write_json(
        root / ".cognitive-loop" / "artifacts" / "evidence" / "healthy-loop.json",
        {
            "schema_version": "artifact-console-evolution-evidence-v1",
            "status": "pass",
            "summary": "healthy metadata-only loop evidence",
            "privacy": {
                "source_text_included": False,
                "raw_diff_included": False,
                "learner_answers_included": False,
                "agent_endpoints_included": False,
                "agent_metadata_included": False,
                "prompt_text_included": False,
                "model_keys_included": False,
            },
        },
    )
    evolution = run_json(
        [
            sys.executable,
            str(EVOLUTION),
            "--root",
            str(root),
            "build",
            "--evidence",
            str(evidence.relative_to(root)),
            "--html",
            "--json",
            "--generated-at",
            "2026-01-01T00:00:00Z",
        ]
    )
    apply_plan = run_json(
        [
            sys.executable,
            str(APPLY_PLAN),
            "--root",
            str(root),
            "plan",
            "--proposal",
            EVOLUTION_CHAIN_REFS["evolution_report"],
            "--html",
            "--json",
            "--generated-at",
            "2026-01-01T00:00:00Z",
        ]
    )
    comparison = run_json(
        [
            sys.executable,
            str(IMPROVEMENT),
            "--root",
            str(root),
            "compare",
            "--artifact",
            EVOLUTION_CHAIN_REFS["evolution_report"],
            "--artifact",
            EVOLUTION_CHAIN_REFS["apply_plan"],
            "--html",
            "--json",
            "--generated-at",
            "2026-01-01T00:00:00Z",
        ]
    )
    patch = run_json(
        [
            sys.executable,
            str(PATCH_PROPOSAL),
            "--root",
            str(root),
            "build",
            "--artifact",
            EVOLUTION_CHAIN_REFS["evolution_report"],
            "--artifact",
            EVOLUTION_CHAIN_REFS["apply_plan"],
            "--artifact",
            EVOLUTION_CHAIN_REFS["improvement_comparison"],
            "--html",
            "--json",
            "--generated-at",
            "2026-01-01T00:00:00Z",
        ]
    )
    receipt = run_json(
        [
            sys.executable,
            str(EVOLUTION_RECEIPT),
            "--root",
            str(root),
            "build",
            "--artifact",
            EVOLUTION_CHAIN_REFS["evolution_report"],
            "--artifact",
            EVOLUTION_CHAIN_REFS["apply_plan"],
            "--artifact",
            EVOLUTION_CHAIN_REFS["improvement_comparison"],
            "--artifact",
            EVOLUTION_CHAIN_REFS["patch_proposal"],
            "--html",
            "--json",
            "--generated-at",
            "2026-01-01T00:00:00Z",
        ]
    )
    replay = run_json(
        [
            sys.executable,
            str(EVOLUTION_REPLAY),
            "--root",
            str(root),
            "replay",
            "--receipt",
            EVOLUTION_CHAIN_REFS["evolution_receipt_link"],
            "--html",
            "--json",
            "--generated-at",
            "2026-01-01T00:00:00Z",
        ]
    )
    sandbox = run_json(
        [
            sys.executable,
            str(PATCH_APPLY_SANDBOX),
            "--root",
            str(root),
            "sandbox",
            "--html",
            "--json",
            "--generated-at",
            "2026-01-01T00:00:00Z",
        ]
    )
    return {
        "evolution_status": evolution["status"],
        "apply_plan_status": apply_plan["status"],
        "comparison_status": comparison["status"],
        "patch_status": patch["status"],
        "receipt_status": receipt["status"],
        "replay_status": replay["status"],
        "sandbox_status": sandbox["status"],
    }


def write_blocked_replay_chain(root: Path) -> dict[str, Any]:
    receipt = {
        "schema_version": "cognitive-loop-mastra-evolution-receipt-link-v1",
        "status": "blocked",
        "link_id": "blocked-console-fixture",
        "generated_at": "2026-01-01T00:00:00Z",
        "artifact_count": 4,
        "artifact_links": [
            {
                "role": role,
                "schema_version": f"fixture-{role}-v1",
                "status": "blocked" if role == "patch_proposal" else "ready",
                "ref": f".cognitive-loop/artifacts/fixtures/{role}.json",
                "sha256": "0" * 64,
                "accepted_for_mastra_receipt": role != "patch_proposal",
                "blockers": ["PatchProposal contains manual-only or review-required candidates"] if role == "patch_proposal" else [],
                "privacy_regressions": [],
            }
            for role in ("evolution_report", "apply_plan", "improvement_comparison", "patch_proposal")
        ],
        "missing_roles": [],
        "degraded_reasons": [],
        "blockers": [
            {
                "role": "patch_proposal",
                "ref": ".cognitive-loop/artifacts/fixtures/patch_proposal.json",
                "blockers": ["PatchProposal contains manual-only or review-required candidates"],
            }
        ],
        "receipt": {
            "ready_for_mastra": False,
            "linked_roles": ["evolution_report", "apply_plan", "improvement_comparison", "patch_proposal"],
            "human_mastery_gate_required": False,
            "manual_only_required": True,
        },
        "guardrails": {
            "read_only": True,
            "raw_unified_diff_generated": False,
            "apply_executed": False,
            "model_called": False,
            "daemon_started": False,
            "production_mastra_daemon_started": False,
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
            "model_called": False,
            "daemon_started": False,
        },
    }
    write_json(root / EVOLUTION_CHAIN_REFS["evolution_receipt_link"], receipt)
    replay = run_json(
        [
            sys.executable,
            str(EVOLUTION_REPLAY),
            "--root",
            str(root),
            "replay",
            "--receipt",
            EVOLUTION_CHAIN_REFS["evolution_receipt_link"],
            "--html",
            "--json",
            "--generated-at",
            "2026-01-01T00:00:00Z",
        ]
    )
    return {"receipt_status": "blocked", "replay_status": replay["status"]}


def verify_empty_console() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-anything-artifact-console-empty-") as tmp:
        root = Path(tmp)
        init_project(root)
        manifest, html = build_console(root)
    sections = manifest["sections"]
    if manifest["status"] != "ready":
        raise RuntimeError(f"Empty console should still be ready, got {manifest['status']}")
    if sections["event_store"]["event_count"] != 0:
        raise RuntimeError("Empty console should have zero Event Store rows.")
    if "No Event Store rows yet." not in html:
        raise RuntimeError("Empty console HTML does not explain the empty Event Store.")
    evolution = sections["evolution_chain"]
    if evolution["status"] != "degraded_missing_artifacts" or evolution["missing_artifact_count"] != 7:
        raise RuntimeError(f"Empty console should degrade the optional Evolution Chain section: {evolution}")
    if "Evolution Chain" not in html:
        raise RuntimeError("Empty console HTML missed Evolution Chain section.")
    return {
        "status": manifest["status"],
        "event_count": sections["event_store"]["event_count"],
        "artifact_count": sections["artifact_health"]["artifact_count"],
        "evolution_chain_status": evolution["status"],
        "missing_evolution_artifact_count": evolution["missing_artifact_count"],
        "html_has_empty_state": True,
    }


def verify_runner_console() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-anything-artifact-console-runner-") as tmp:
        root = Path(tmp)
        init_project(root)
        runner = run_watcher_runner(root)
        manifest, html = build_console(root)
        sections = manifest["sections"]
        runner_section = sections["watcher_runner"]
        study_section = sections["study_adapter"]
        event_section = sections["event_store"]
        if runner_section["accepted_observation_count"] < 3:
            raise RuntimeError(f"Expected runner observations in console: {runner_section}")
        if runner_section["duplicate_observation_count"] < 1:
            raise RuntimeError("Console did not carry runner duplicate debounce evidence.")
        if runner_section["skipped_observation_count"] < 1:
            raise RuntimeError("Console did not carry excluded-path evidence.")
        if runner_section["study_adapter_triggered"] is not True:
            raise RuntimeError("Console did not link Study Adapter gate trigger.")
        if study_section["study_adapter_artifact_count"] < 1:
            raise RuntimeError("Console missed Study Adapter artifacts.")
        if event_section["event_count"] < 3:
            raise RuntimeError("Console missed Event Store rows.")
        required_html = [
            '<meta name="viewport"',
            "@media (max-width: 760px)",
            "Cognitive Loop Artifact Console",
            "Watcher Runner",
            "Study Adapter",
            "Decision, Gate, Loop",
            "Evolution Chain",
            "Artifact Health",
            "Redacted Manifest",
        ]
        missing = [needle for needle in required_html if needle not in html]
        if missing:
            raise RuntimeError(f"Console HTML missed required structure: {missing}")
        evolution = sections["evolution_chain"]
        if evolution["status"] != "degraded_missing_artifacts":
            raise RuntimeError("Runner-only console should degrade missing optional Evolution Chain artifacts.")
        manifest_path = root / ".cognitive-loop" / "artifacts" / "console" / "manifest.json"
        deleted_source = root / event_section["latest_events"][0]["source_path"]
        deleted_source.unlink()
        degraded, _ = build_console(root)
    return {
        "runner_status": runner["status"],
        "console_status": manifest["status"],
        "event_count": event_section["event_count"],
        "accepted_observation_count": runner_section["accepted_observation_count"],
        "duplicate_observation_count": runner_section["duplicate_observation_count"],
        "skipped_observation_count": runner_section["skipped_observation_count"],
        "study_adapter_artifact_count": study_section["study_adapter_artifact_count"],
        "study_adapter_html_linked": bool(study_section["cards"][0]["html_ref"]),
        "evolution_chain_status": evolution["status"],
        "missing_evolution_artifact_count": evolution["missing_artifact_count"],
        "manifest_written": manifest_path.name == "manifest.json",
        "degraded_status": degraded["status"],
        "missing_event_source_count": degraded["sections"]["artifact_health"]["missing_event_source_count"],
        "mobile_structure": "ok",
    }


def verify_evolution_chain_console() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-anything-artifact-console-evolution-") as tmp:
        root = Path(tmp)
        init_project(root)
        chain = run_evolution_chain(root)
        manifest, html = build_console(root)
    evolution = manifest["sections"]["evolution_chain"]
    if evolution["artifact_count"] != 7 or evolution["missing_artifact_count"] != 0:
        raise RuntimeError(f"Console missed complete Evolution Chain artifacts: {evolution}")
    if not all(item.get("sha256") for item in evolution["artifacts"]):
        raise RuntimeError("Console Evolution Chain must include artifact SHA-256 values.")
    if not all(item.get("operator_next_command") for item in evolution["artifacts"]):
        raise RuntimeError("Console Evolution Chain must include operator next commands.")
    if not all(isinstance(item.get("privacy_flags"), dict) for item in evolution["artifacts"]):
        raise RuntimeError("Console Evolution Chain must expose privacy flags for every artifact.")
    required_html = [
        "Evolution Chain",
        "Evolution Report",
        "Governed Apply Plan",
        "Improvement Comparison",
        "Patch Proposal",
        "Evolution Receipt Link",
        "Mastra Workflow Replay",
        "Patch Apply Sandbox",
        "Professional Evolution Pack",
    ]
    missing = [needle for needle in required_html if needle not in html]
    if missing:
        raise RuntimeError(f"Console Evolution Chain HTML missed required text: {missing}")
    return {
        "status": evolution["status"],
        "artifact_count": evolution["artifact_count"],
        "missing_artifact_count": evolution["missing_artifact_count"],
        "manual_review_count": evolution["manual_review_count"],
        "blocking_count": evolution["blocking_count"],
        "export_status": manifest["sections"]["evolution_pack_export"]["status"],
        "export_command_present": bool(manifest["sections"]["evolution_pack_export"]["operator_next_command"]),
        "chain_statuses": chain,
        "html_has_evolution_chain": True,
        "html_has_professional_evolution_pack": True,
        "sha256_values_present": True,
        "operator_commands_present": True,
        "privacy_flags_present": True,
    }


def verify_blocked_replay_console() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-anything-artifact-console-blocked-") as tmp:
        root = Path(tmp)
        init_project(root)
        blocked = write_blocked_replay_chain(root)
        manifest, html = build_console(root)
    evolution = manifest["sections"]["evolution_chain"]
    replay_rows = [
        item for item in evolution["artifacts"] if item.get("role") == "mastra_workflow_replay"
    ]
    if blocked["replay_status"] != "blocked" or not replay_rows:
        raise RuntimeError("Blocked replay fixture did not create a blocked replay artifact.")
    if replay_rows[0].get("blocking_required") is not True:
        raise RuntimeError("Console did not preserve blocked replay state.")
    if evolution["status"] != "blocked":
        raise RuntimeError(f"Console Evolution Chain should be blocked when replay is blocked: {evolution}")
    if "blocked" not in html:
        raise RuntimeError("Console HTML missed blocked replay status.")
    return {
        "chain_status": evolution["status"],
        "receipt_status": blocked["receipt_status"],
        "replay_status": blocked["replay_status"],
        "blocking_count": evolution["blocking_count"],
        "blocked_replay_preserved": True,
    }


def verify_evolution_chain_rejection(name: str, payload: dict[str, Any]) -> bool:
    with tempfile.TemporaryDirectory(prefix=f"study-anything-artifact-console-{name}-") as tmp:
        root = Path(tmp)
        init_project(root)
        write_json(root / EVOLUTION_CHAIN_REFS["evolution_report"], payload)
        completed = subprocess.run(
            [
                sys.executable,
                str(CONSOLE),
                "build",
                "--root",
                str(root),
                "--html",
                "--json",
            ],
            cwd=str(ROOT),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    return completed.returncode != 0


def verify_evolution_chain_rejections() -> dict[str, bool]:
    base = {
        "schema_version": "cognitive-loop-evolution-report-lite-v1",
        "status": "ready",
        "generated_at": "2026-01-01T00:00:00Z",
        "title": "Safe fixture",
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
        },
        "policy_guardrails": {"policy_weakened": False},
        "outputs": {"html_ref": ".cognitive-loop/artifacts/evolution/evolution-report-lite.html"},
        "commands": {"build": "python3 scripts/cognitive_loop_evolution.py build --html --json"},
    }
    invalid_schema = {**base, "schema_version": "unknown-evolution-schema-v1"}
    secret = {**base, "title": "OPENAI_API_KEY=sk-proj-abcdefghijklmnop"}
    raw_diff = {**base, "title": "diff --git a/private b/private"}
    privacy_regression = {**base, "privacy": {**base["privacy"], "raw_diff_included": True}}
    policy_weakening = {**base, "title": "disable tests before release"}
    results = {
        "invalid_schema_rejected": verify_evolution_chain_rejection("invalid-schema", invalid_schema),
        "secret_like_rejected": verify_evolution_chain_rejection("secret", secret),
        "raw_diff_rejected": verify_evolution_chain_rejection("raw-diff", raw_diff),
        "privacy_regression_rejected": verify_evolution_chain_rejection("privacy-regression", privacy_regression),
        "policy_weakening_rejected": verify_evolution_chain_rejection("policy-weakening", policy_weakening),
    }
    failed = [key for key, value in results.items() if value is not True]
    if failed:
        raise RuntimeError(f"Console Evolution Chain unsafe fixture was not rejected: {failed}")
    return results


def verify_forbidden_text_rejection() -> bool:
    with tempfile.TemporaryDirectory(prefix="study-anything-artifact-console-secret-") as tmp:
        root = Path(tmp)
        init_project(root)
        events = root / ".cognitive-loop" / "events"
        events.mkdir(parents=True, exist_ok=True)
        (events / "private.json").write_text(
            json.dumps(
                {
                    "schema_version": "private-fixture-v1",
                    "status": "pass",
                    "summary": "diff --git a/private b/private",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        completed = subprocess.run(
            [
                sys.executable,
                str(CONSOLE),
                "build",
                "--root",
                str(root),
                "--html",
                "--json",
            ],
            cwd=str(ROOT),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    return completed.returncode != 0 and "private-looking text" in completed.stderr


def build_report() -> dict[str, Any]:
    empty = verify_empty_console()
    runner = verify_runner_console()
    evolution = verify_evolution_chain_console()
    blocked = verify_blocked_replay_console()
    evolution_rejections = verify_evolution_chain_rejections()
    forbidden_rejected = verify_forbidden_text_rejection()
    if not forbidden_rejected:
        raise RuntimeError("Console did not reject forbidden private-looking text.")
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "console_schema": "cognitive-loop-artifact-console-v1",
        "empty_console": empty,
        "runner_console": runner,
        "evolution_chain_console": evolution,
        "blocked_replay_console": blocked,
        "failure_modes": {
            "forbidden_private_text_rejected": forbidden_rejected,
            "missing_artifact_degrades_console": runner["degraded_status"] == "partial",
            "missing_evolution_chain_degrades_section": empty["evolution_chain_status"] == "degraded_missing_artifacts",
            "blocked_replay_preserved": blocked["blocked_replay_preserved"],
            **evolution_rejections,
        },
        "privacy": {
            "metadata_only": True,
            "event_json_contents_included": False,
            "html_contents_included": False,
            "markdown_contents_included": False,
            "source_text_included": False,
            "raw_diff_included": False,
            "test_output_included": False,
            "learner_answers_included": False,
            "agent_endpoints_included": False,
            "agent_metadata_included": False,
            "prompt_text_included": False,
            "model_keys_included": False,
            "standalone_frontend_required": False,
            "watcher_daemon_started": False,
            "production_mastra_started": False,
            "model_called": False,
            "apply_executed": False,
            "source_files_modified": False,
        },
        "commands": {
            "console": "python3 scripts/cognitive_loop_artifact_console.py build --html",
            "verify": "python3 scripts/verify_cognitive_loop_artifact_console.py --check",
            "runner": ".venv/bin/python scripts/cognitive_loop_watcher_runner.py run --html --study-adapter",
            "evolution_chain": "python3 scripts/cognitive_loop_artifact_console.py build --html --json",
            "evolution_pack_export": "python3 scripts/cognitive_loop_evolution_pack_export.py export --html --json --zip",
        },
    }


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
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
            raise SystemExit(f"Cognitive Loop artifact console report is missing: {output}")
        current = output.read_text(encoding="utf-8")
        if current != serialized:
            raise SystemExit(
                "Cognitive Loop artifact console report is stale. "
                "Run: python3 scripts/verify_cognitive_loop_artifact_console.py --write"
            )
    if not args.write and not args.check:
        print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
