#!/usr/bin/env python3
"""Verify the skill-friendly CLI against a running Study Anything API."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from localhost_diagnostics import contains_unredacted_local_path, redact_diagnostic, resolve_api_base


ROOT = SCRIPT_DIR.parent
CLI = ROOT / "scripts" / "study_anything_cli.py"
PRIVATE_USER = "skill-smoke-user"
PRIVATE_SOURCE_TEXT = (
    "A learning loop should bind a question to its source, grade a grounded answer, "
    "update mastery, and synthesize a reusable insight."
)
PRIVATE_ANSWER = "The learning loop uses source evidence to grade an answer and update mastery."
FORBIDDEN_LITERALS = (
    PRIVATE_USER,
    PRIVATE_SOURCE_TEXT,
    PRIVATE_ANSWER,
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "AGENT_LLM_API_KEY=",
    "raw_source_text=",
    "learner_answer=",
)


class SkillCliFlowError(RuntimeError):
    """Readable Skill Mode CLI verification failure."""


def api_base() -> str:
    return resolve_api_base()


def sanitize(text: str | None) -> str:
    value = text or ""
    replacements = {
        PRIVATE_USER: "<private-user>",
        PRIVATE_SOURCE_TEXT: "<private-source-text>",
        PRIVATE_ANSWER: "<private-answer>",
    }
    for literal, replacement in replacements.items():
        value = value.replace(literal, replacement)
    value = re.sub(r"(?i)a learning loop should bind a question[^\"'\n.]*\.?", "<private-source-text>", value)
    value = re.sub(r"(?i)the learning loop uses source evidence[^\"'\n.]*\.?", "<private-answer>", value)
    value = re.sub(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", "<uuid>", value)
    value = redact_diagnostic(value)
    value = re.sub(r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}", r"\1=<redacted>", value)
    value = re.sub(r"sk-(?:proj-)?[A-Za-z0-9_-]{12,}", "sk-<redacted>", value)
    return value.strip()[:1600]


def format_cli_failure(args: tuple[str, ...], completed: subprocess.CompletedProcess[str]) -> str:
    command = " ".join(["python3", "scripts/study_anything_cli.py", "--json", *args])
    hints = [
        "Run `./scripts/launch_skill_mode.sh` if the API is not running.",
        "Run `python3 scripts/diagnose_adoption.py` for a redacted local report.",
        "Set `API_BASE=http://127.0.0.1:<port>` or edit `.env` API_PORT if you launched Skill Mode on a custom port.",
    ]
    combined = f"{completed.stdout}\n{completed.stderr}".lower()
    if "unrecognized arguments" in combined:
        hints.append(
            "Check CLI argument order: pass the real session id printed by `start`, `demo`, or `sessions`; "
            "session commands accept positional id, --session, or --session-id."
        )
    if "connection refused" in combined or "timed out" in combined or "api_unreachable" in combined:
        hints.append("If localhost sockets are blocked, rerun from a normal terminal or host shell.")
    return (
        "Skill Mode CLI verification step failed.\n"
        f"Command: {command}\n"
        f"Exit code: {completed.returncode}\n"
        f"API base: {api_base()}\n"
        f"stdout:\n{sanitize(completed.stdout) or '(empty)'}\n"
        f"stderr:\n{sanitize(completed.stderr) or '(empty)'}\n"
        "Recovery:\n"
        + "\n".join(f"- {hint}" for hint in hints)
    )


def classify_failure(message: str) -> str:
    lowered = message.lower()
    if (
        "runner appears to block localhost sockets" in lowered
        or "blocks localhost" in lowered
        or "operation not permitted" in lowered
        or "permission denied" in lowered
        or "localhost_socket_blocked" in lowered
    ):
        return "localhost_socket_blocked"
    if "connection refused" in lowered or "api_unreachable" in lowered or "cannot reach" in lowered:
        return "api_unreachable"
    if "unrecognized arguments" in lowered or "missing required argument" in lowered:
        return "cli_argument_error"
    if "returned non-json output" in lowered:
        return "non_json_cli_output"
    if "agent eval required gates failed" in lowered or "agent eval artifact is not ready" in lowered:
        return "agent_eval_failed"
    if "agent audit did not verify" in lowered:
        return "agent_audit_failed"
    if "expected completed" in lowered or "expected mastery" in lowered or "completion event missing" in lowered:
        return "learning_flow_incomplete"
    if "discard should require explicit approval" in lowered:
        return "discard_guard_failed"
    if "leaked" in lowered:
        return "privacy_leak"
    return "skill_cli_flow_failed"


def failure_next_steps(classification: str) -> list[str]:
    common = [
        "./scripts/launch_skill_mode.sh",
        f"API_BASE={api_base()} python3 scripts/verify_skill_cli_flow.py",
        "python3 scripts/diagnose_adoption.py",
    ]
    matrix = {
        "localhost_socket_blocked": [
            "Run this verifier from a normal terminal or host shell that permits localhost sockets.",
            "If this came from Codex or another sandboxed Agent, collect this blocked report and rerun outside the sandbox.",
        ],
        "api_unreachable": [
            "Start the local API first with `./scripts/launch_skill_mode.sh`.",
            "If Skill Mode is running on another port, pass it with `API_BASE=http://127.0.0.1:<port>`.",
        ],
        "cli_argument_error": [
            "Run `python3 scripts/study_anything_cli.py --help` for the supported command shape.",
            "For session commands, pass the real session id printed by `start`, `demo`, or `sessions`; positional id, `--session`, and `--session-id` are supported.",
        ],
        "non_json_cli_output": [
            "Confirm the CLI and API server come from the same checkout.",
            "Rerun setup with `python3 scripts/setup_env.py` if the local environment is stale.",
        ],
        "agent_eval_failed": [
            "Run `python3 scripts/verify_agent_eval_flow.py` to isolate eval artifact failures.",
            "Required native eval gates must pass before release evidence is valid.",
        ],
        "agent_audit_failed": [
            "Inspect the session agent-audit endpoint locally for observed task coverage.",
            "The deterministic Skill Mode demo should use the fake Agent, not an external provider.",
        ],
        "learning_flow_incomplete": [
            "Check session events locally for the first failed workflow stage.",
            "Rerun the one-command demo with `./scripts/run_skill_mode_demo.sh` after restarting Skill Mode.",
        ],
        "discard_guard_failed": [
            "Do not publish release evidence until discard requires explicit approval.",
            "Inspect CLI discard behavior before rerunning the smoke.",
        ],
        "privacy_leak": [
            "Do not share the raw transcript publicly.",
            "Fix the leaking CLI/API output before using this run as evidence.",
        ],
    }
    return matrix.get(classification, ["Rerun after starting the local Skill Mode API."]) + common


def failure_report(exc: BaseException) -> dict[str, Any]:
    diagnostic = sanitize(str(exc))
    classification = classify_failure(diagnostic)
    report = {
        "status": "blocked",
        "classification": classification,
        "diagnostic": diagnostic,
        "next_steps": failure_next_steps(classification),
        "source": {
            "verifier": "verify_skill_cli_flow",
            "api_base": sanitize(api_base()),
        },
        "privacy": {
            "raw_source_text_included": False,
            "learner_answers_included": False,
            "real_model_keys_included": False,
            "local_absolute_paths_included": False,
        },
    }
    assert_failure_report_redacted(report)
    return report


def format_failure_for_human(report: dict[str, Any]) -> str:
    steps = [
        f"- {sanitize(str(step))}"
        for step in report.get("next_steps", [])
        if isinstance(step, str) and step.strip()
    ]
    return "\n".join(
        [
            "verify_skill_cli_flow failed:",
            f"classification: {sanitize(str(report.get('classification') or 'skill_cli_flow_failed'))}",
            f"Diagnostic: {sanitize(str(report.get('diagnostic') or '')) or '(empty)'}",
            "Next steps:",
            *(steps or ["- Run ./scripts/launch_skill_mode.sh, then rerun this verifier."]),
        ]
    )


def assert_failure_report_redacted(report: dict[str, Any]) -> None:
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in serialized]
    if contains_unredacted_local_path(serialized):
        leaks.append("local absolute path")
    if re.search(r"sk-(?:proj-)?[A-Za-z0-9_-]{12,}", serialized):
        leaks.append("secret-looking sk token")
    if leaks:
        raise SkillCliFlowError(f"Skill Mode CLI verifier failure report leaked private data: {leaks}")


def run_cli(*args: str, expect_ok: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        [sys.executable, str(CLI), "--json", *args],
        cwd=ROOT,
        env=os.environ.copy(),
        text=True,
        capture_output=True,
        check=False,
    )
    if expect_ok and completed.returncode != 0:
        raise SkillCliFlowError(format_cli_failure(args, completed))
    return completed


def parsed(*args: str) -> Any:
    completed = run_cli(*args)
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise SkillCliFlowError(
            "Skill Mode CLI returned non-JSON output.\n"
            f"Command: python3 scripts/study_anything_cli.py --json {' '.join(args)}\n"
            f"API base: {api_base()}\n"
            f"stdout:\n{sanitize(completed.stdout) or '(empty)'}\n"
            f"stderr:\n{sanitize(completed.stderr) or '(empty)'}\n"
            "Recovery:\n"
            "- Run `python3 scripts/diagnose_adoption.py` for a redacted local report.\n"
            "- Confirm the API and CLI versions come from the same checkout."
        ) from exc


def main() -> None:
    health = parsed("health")
    if health.get("status") != "ok":
        raise RuntimeError(f"API health is not ok: {health}")

    commercial_readiness: Dict[str, Any] = parsed("commercial-readiness")
    if commercial_readiness.get("schema_version") != "commercial-readiness-v1":
        raise RuntimeError(f"Unexpected commercial readiness schema: {commercial_readiness}")
    if commercial_readiness.get("launch_assessment", {}).get("hosted_paid_services") != "not_ready":
        raise RuntimeError(f"Hosted paid services should remain not ready: {commercial_readiness}")

    adoption_telemetry: Dict[str, Any] = parsed("adoption-telemetry")
    if adoption_telemetry.get("schema_version") != "adoption-telemetry-v1":
        raise RuntimeError(f"Unexpected adoption telemetry schema: {adoption_telemetry}")
    if adoption_telemetry.get("privacy", {}).get("aggregate_only") is not True:
        raise RuntimeError(f"Adoption telemetry must be aggregate-only: {adoption_telemetry}")

    pmf_readiness: Dict[str, Any] = parsed("pmf-readiness")
    if pmf_readiness.get("schema_version") != "pmf-readiness-v1":
        raise RuntimeError(f"Unexpected PMF readiness schema: {pmf_readiness}")
    if pmf_readiness.get("commercial_boundary", {}).get("hosted_paid_services_status") != "not_ready":
        raise RuntimeError(f"Hosted paid services should remain not ready: {pmf_readiness}")

    eval_policy: Dict[str, Any] = parsed("eval-policy")
    if eval_policy.get("schema_version") != "agent-eval-policy-v1":
        raise RuntimeError(f"Unexpected Agent eval policy schema: {eval_policy}")

    completed: Dict[str, Any] = parsed("demo", "--user-id", PRIVATE_USER)
    if completed.get("stage") != "completed":
        raise RuntimeError(f"Expected completed CLI demo, got: {completed}")
    if completed.get("mastery", {}).get("level", 0) < 0.5:
        raise RuntimeError(f"Expected mastery upgrade, got: {completed}")

    session_id = completed["session_id"]
    shown = parsed("show", session_id)
    if shown.get("session_id") != session_id:
        raise RuntimeError(f"CLI show returned the wrong session: {shown}")

    events: List[Dict[str, Any]] = parsed("events", session_id)
    if not any(item.get("type") == "session.completed" for item in events):
        raise RuntimeError(f"Completion event missing: {events}")

    agent_audit: Dict[str, Any] = parsed("agent-audit", session_id)
    if agent_audit.get("schema_version") != "agent-audit-v1":
        raise RuntimeError(f"Unexpected Agent audit schema: {agent_audit}")
    if agent_audit.get("status") != "verified":
        raise RuntimeError(f"Agent audit did not verify required tasks: {agent_audit}")
    required_tasks = {
        "teach.overview",
        "teach.glossary",
        "quiz.generate",
        "answer.grade",
        "insight.synthesize",
    }
    observed_tasks = set(agent_audit.get("observed_tasks") or [])
    if not required_tasks.issubset(observed_tasks):
        missing = sorted(required_tasks - observed_tasks)
        raise RuntimeError(f"Agent audit missed required multi-teacher tasks {missing}: {agent_audit}")
    if agent_audit.get("used_external_agent"):
        raise RuntimeError(f"Skill demo should use the deterministic fake Agent: {agent_audit}")

    agent_eval: Dict[str, Any] = parsed("agent-eval", session_id)
    if agent_eval.get("schema_version") != "agent-eval-artifact-v1":
        raise RuntimeError(f"Unexpected Agent eval artifact schema: {agent_eval}")
    if agent_eval.get("status") != "ready_for_external_eval":
        raise RuntimeError(f"Agent eval artifact is not ready: {agent_eval}")
    required_gates = [gate for gate in agent_eval.get("native_gates", []) if gate.get("required")]
    if not required_gates or any(gate.get("status") != "pass" for gate in required_gates):
        raise RuntimeError(f"Agent eval required gates failed: {agent_eval}")

    agent_eval_report: Dict[str, Any] = parsed("agent-eval-report", session_id)
    if agent_eval_report.get("schema_version") != "agent-eval-report-v1":
        raise RuntimeError(f"Unexpected Agent eval report schema: {agent_eval_report}")

    refused = run_cli("discard", session_id, expect_ok=False)
    refused_output = f"{refused.stdout}\n{refused.stderr}"
    if refused.returncode == 0 or "explicit approval" not in refused_output:
        raise RuntimeError("Discard should require explicit approval.")

    discarded = parsed("discard", session_id, "--yes")
    if discarded.get("stage") != "discarded" or not discarded.get("discarded"):
        raise RuntimeError(f"Expected discarded session, got: {discarded}")

    print(
        json.dumps(
            {
                "status": "ok",
                "session_id": session_id,
                "completed_stage": completed["stage"],
                "discarded_stage": discarded["stage"],
                "event_count": len(events),
                "agent_audit_status": agent_audit["status"],
                "agent_task_count": len(observed_tasks),
                "agent_eval_schema": agent_eval["schema_version"],
                "agent_eval_policy_schema": eval_policy["schema_version"],
                "agent_eval_report_schema": agent_eval_report["schema_version"],
                "commercial_readiness_schema": commercial_readiness["schema_version"],
                "adoption_telemetry_schema": adoption_telemetry["schema_version"],
                "pmf_readiness_schema": pmf_readiness["schema_version"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        report = failure_report(exc)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        print(format_failure_for_human(report), file=sys.stderr)
        sys.exit(1)
