#!/usr/bin/env python3
"""Run the deterministic core smoke flow without Docker."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
API_ROOT = ROOT / "apps" / "api"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from localhost_diagnostics import redact_diagnostic  # noqa: E402


MIN_PYTHON = (3, 11)


def runtime_failure_payload(
    *,
    classification: str,
    diagnostic: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "core-smoke-error-v1",
        "status": "blocked",
        "classification": classification,
        "diagnostic": redact_diagnostic(diagnostic),
        "details": details or {},
        "next_steps": [
            ".venv/bin/python scripts/smoke_core.py",
            "python3 scripts/setup_env.py",
            "./scripts/run_skill_mode_demo.sh",
        ],
        "privacy": {
            "local_absolute_paths_included": False,
            "secrets_recorded": False,
        },
    }


def runtime_failure(
    message: str,
    *,
    classification: str = "core_smoke_failed",
    details: dict[str, Any] | None = None,
) -> None:
    print(
        json.dumps(
            runtime_failure_payload(
                classification=classification,
                diagnostic=message,
                details=details,
            ),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        file=sys.stderr,
    )
    sys.exit(1)


def main() -> None:
    if sys.version_info < MIN_PYTHON:  # pragma: no cover - depends on local interpreter
        runtime_failure(
            "smoke_core requires Python 3.11 or newer.",
            classification="python_version_unsupported",
            details={"python_version": sys.version.split()[0]},
        )

    try:
        from study_anything.core.agent_registry import AgentRegistry, AgentRouter  # noqa: PLC0415
        from study_anything.core.workflow import (  # noqa: PLC0415
            Answer,
            LearningWorkflow,
            new_session,
            submit_answers,
            submit_reading,
        )
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on local interpreter
        runtime_failure(
            f"Python dependencies are missing for this interpreter ({exc.name}).",
            classification="python_dependency_missing",
            details={"missing_module": redact_diagnostic(exc.name or "required module")},
        )

    registry = AgentRegistry()
    registry.set_demo_defaults("local-user")
    workflow = LearningWorkflow(AgentRouter(registry))
    state = new_session("local-user")
    state = submit_reading(
        state,
        source_type="local_text",
        reference="demo://smoke",
        title="Smoke Reading",
        text="Reading should create grounded quiz items and update mastery after graded answers.",
    )
    state = workflow.run(state)
    quiz = state.quiz_items[0]
    state = submit_answers(state, [Answer(item_id=quiz.item_id, text="A grounded answer.")])
    state = workflow.run(state)
    print(state.public_dict()["stage"])
    print(state.public_dict()["mastery"])


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # pragma: no cover - CLI failure path
        runtime_failure(str(exc), classification="core_smoke_failed")
