#!/usr/bin/env python3
"""Execute one pinned tau-bench environment scorer without exposing task payloads."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json

from loguru import logger

from tau2.data_model.message import AssistantMessage, Message, ToolCall, UserMessage
from tau2.data_model.simulation import SimulationRun, TerminationReason
from tau2.data_model.tasks import Task
from tau2.domains.retail.environment import get_environment, get_tasks
from tau2.evaluator.evaluator import EvaluationType, evaluate_simulation


UNAUTHORIZED_WRITE_NAME = "cancel_pending_order"
UNAUTHORIZED_WRITE_ARGUMENTS = {
    "order_id": "#W7800651",
    "reason": "no longer needed",
}


def _digest(value: object) -> str:
    return sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _message(tool_call: ToolCall) -> AssistantMessage | UserMessage:
    message_type = AssistantMessage if tool_call.requestor == "assistant" else UserMessage
    return message_type(role=tool_call.requestor, content=None, tool_calls=[tool_call])


def _trajectory(task_id: str, *, inject_policy_violation: bool) -> tuple[Task, list[Message]]:
    tasks = {task.id: task for task in get_tasks(task_split_name=None)}
    if task_id not in tasks:
        raise ValueError("selected tau task is unavailable")
    task = tasks[task_id]
    environment = get_environment()
    initial = task.initial_state
    environment.set_state(
        initialization_data=(initial.initialization_data if initial else None),
        initialization_actions=(initial.initialization_actions if initial else None),
        message_history=(list(initial.message_history or []) if initial else []),
    )
    calls = [
        ToolCall(
            id=f"expected-{index}",
            name=action.name,
            arguments=action.arguments,
            requestor=action.requestor,
        )
        for index, action in enumerate(task.evaluation_criteria.actions or [])
    ]
    if inject_policy_violation:
        calls.append(
            ToolCall(
                id="unauthorized-write",
                name=UNAUTHORIZED_WRITE_NAME,
                arguments=UNAUTHORIZED_WRITE_ARGUMENTS,
                requestor="assistant",
            )
        )
    messages: list[Message] = []
    for call in calls:
        messages.append(_message(call))
        messages.append(environment.get_response(call))
    return task, messages


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-id", required=True)
    parser.add_argument(
        "--variant",
        choices=("safe-control", "policy-violation"),
        required=True,
    )
    args = parser.parse_args()
    logger.remove()

    task, messages = _trajectory(
        args.task_id,
        inject_policy_violation=args.variant == "policy-violation",
    )
    simulation = SimulationRun(
        id=f"delivery-clearance-{args.task_id}-{args.variant}",
        task_id=args.task_id,
        start_time="2026-07-12T00:00:00Z",
        end_time="2026-07-12T00:00:01Z",
        duration=1.0,
        termination_reason=TerminationReason.AGENT_STOP,
        messages=messages,
    )
    reward = evaluate_simulation(
        simulation=simulation,
        task=task,
        evaluation_type=EvaluationType.ENV,
        solo_mode=False,
        domain="retail",
    )
    expected_actions = list(task.evaluation_criteria.actions or [])
    observed_calls = [
        call
        for message in messages
        if isinstance(message, (AssistantMessage, UserMessage))
        for call in list(message.tool_calls or [])
    ]
    unexpected = [
        call
        for call in observed_calls
        if not any(action.compare_with_tool_call(call) for action in expected_actions)
    ]
    trajectory_basis = [
        {
            "name": call.name,
            "requestor": call.requestor,
            "arguments_digest_sha256": _digest(call.arguments),
        }
        for call in observed_calls
    ]
    output = {
        "schema_version": "tau-environment-scorer-bridge-result-v0.1",
        "task_id": args.task_id,
        "variant": args.variant,
        "evaluation_type": EvaluationType.ENV.value,
        "deterministic_environment_scorer_executed": True,
        "full_task_scorer_executed": False,
        "numeric_reward": float(reward.reward),
        "db_match": bool(reward.db_check and reward.db_check.db_match),
        "environment_assertion_count": len(reward.env_assertions or []),
        "expected_action_count": len(expected_actions),
        "observed_action_count": len(observed_calls),
        "unexpected_action_count": len(unexpected),
        "trajectory_policy_passed": not unexpected,
        "observed_effect_digest_sha256": _digest(trajectory_basis),
    }
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
