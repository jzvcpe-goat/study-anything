#!/usr/bin/env python3
"""Verify the skill-friendly CLI against a running Study Anything API."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "scripts" / "study_anything_cli.py"


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
        raise RuntimeError(f"CLI failed: {' '.join(args)}\n{completed.stderr}")
    return completed


def parsed(*args: str) -> Any:
    return json.loads(run_cli(*args).stdout)


def main() -> None:
    health = parsed("health")
    if health.get("status") != "ok":
        raise RuntimeError(f"API health is not ok: {health}")

    completed: Dict[str, Any] = parsed("demo", "--user-id", "skill-smoke-user")
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

    refused = run_cli("discard", session_id, expect_ok=False)
    if refused.returncode == 0 or "explicit approval" not in refused.stderr:
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
                "agent_eval_schema": agent_eval["schema_version"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_skill_cli_flow failed: {exc}", file=sys.stderr)
        sys.exit(1)
