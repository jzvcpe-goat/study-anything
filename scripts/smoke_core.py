#!/usr/bin/env python3
"""Run the deterministic core smoke flow without Docker."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from neural_console.core.agent_registry import AgentRegistry, AgentRouter
from neural_console.core.workflow import Answer, LearningWorkflow, new_session, submit_answers, submit_reading


def main() -> None:
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
    main()
