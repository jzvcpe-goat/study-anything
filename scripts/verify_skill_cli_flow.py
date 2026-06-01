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
