#!/usr/bin/env python3
"""Small standard-library CLI for the Study Anything public API."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, Iterable, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


DEFAULT_API_BASE = "http://127.0.0.1:8000"
CORE_CAPABILITIES = ["quiz.generate", "answer.grade", "insight.synthesize"]


class StudyAnythingError(RuntimeError):
    """Readable CLI failure."""


def api_base() -> str:
    return os.getenv("STUDY_ANYTHING_API_BASE", os.getenv("API_BASE", DEFAULT_API_BASE)).rstrip("/")


def request(path: str, payload: Optional[Dict[str, Any]] = None) -> Any:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(
        f"{api_base()}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )
    try:
        with urlopen(req, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8")
        raise StudyAnythingError(f"API returned {exc.code} for {path}: {detail}") from exc
    except URLError as exc:
        raise StudyAnythingError(
            f"Cannot reach Study Anything at {api_base()}. Start the API or set "
            "STUDY_ANYTHING_API_BASE."
        ) from exc


def post(path: str, payload: Optional[Dict[str, Any]] = None) -> Any:
    return request(path, payload or {})


def first_unanswered_quiz(session: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    answered = {answer["item_id"] for answer in session.get("answers", [])}
    return next(
        (item for item in session.get("quiz_items", []) if item.get("item_id") not in answered),
        None,
    )


def session_summary(session: Dict[str, Any]) -> Dict[str, Any]:
    active_quiz = first_unanswered_quiz(session)
    source = session.get("source") or {}
    mastery = session.get("mastery") or {}
    open_hitl = [
        item for item in session.get("hitl_interrupts", []) if item.get("status") == "open"
    ]
    return {
        "session_id": session.get("session_id"),
        "stage": session.get("stage"),
        "source_title": source.get("title"),
        "mastery": {
            "level": mastery.get("level", 0.0),
            "bloom": mastery.get("bloom", "remember"),
        },
        "question": active_quiz,
        "grading_results": session.get("grading_results", []),
        "insights": session.get("insights", []),
        "open_hitl": open_hitl,
        "discarded": session.get("discarded", False),
    }


def print_session(session: Dict[str, Any]) -> None:
    summary = session_summary(session)
    mastery = summary["mastery"]
    print(f"session: {summary['session_id']}")
    print(f"stage: {summary['stage']}")
    if summary["source_title"]:
        print(f"source: {summary['source_title']}")
    print(f"mastery: {mastery['level']} ({mastery['bloom']})")
    question = summary["question"]
    if question:
        print(f"question_id: {question['item_id']}")
        print(f"question: {question['prompt']}")
    for result in summary["grading_results"]:
        print(f"feedback: {result.get('feedback', '')} score={result.get('score', '')}")
    for insight in summary["insights"]:
        print(f"insight: {insight}")
    for item in summary["open_hitl"]:
        print(f"hitl: {item.get('task_id')} {item.get('kind')}: {item.get('message')}")
    if summary["discarded"]:
        print("discarded: yes")


def print_rows(rows: Iterable[Dict[str, Any]]) -> None:
    rows = list(rows)
    if not rows:
        print("none")
        return
    for row in rows:
        print(json.dumps(row, ensure_ascii=False, sort_keys=True))


def emit(args: argparse.Namespace, data: Any, *, session: bool = False) -> None:
    if args.json:
        payload = session_summary(data) if session else data
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    elif session:
        print_session(data)
    elif isinstance(data, list):
        print_rows(data)
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))


def create_session(args: argparse.Namespace) -> Dict[str, Any]:
    session = post(
        "/v1/sessions",
        {
            "user_id": args.user_id,
            "track": args.track,
            "use_demo_agent": args.agent_mode == "demo",
        },
    )
    session_id = session["session_id"]
    post(
        f"/v1/sessions/{quote(session_id)}/reading",
        {
            "source_type": args.source_type,
            "reference": args.reference,
            "title": args.title,
            "text": args.text,
        },
    )
    return post(f"/v1/sessions/{quote(session_id)}/run")


def cmd_health(args: argparse.Namespace) -> None:
    emit(args, request("/v1/health"))


def cmd_agents(args: argparse.Namespace) -> None:
    emit(args, request(f"/v1/agents/status?{urlencode({'user_id': args.user_id})}"))


def cmd_agent_add_http(args: argparse.Namespace) -> None:
    capabilities = args.capability or CORE_CAPABILITIES
    provider = post(
        "/v1/agents/providers",
        {
            "kind": "http_agent",
            "label": args.label,
            "endpoint": args.endpoint,
            "capabilities": capabilities,
            "timeout_seconds": args.timeout,
        },
    )
    if args.set_default:
        for capability in capabilities:
            post(
                "/v1/agents/defaults",
                {
                    "user_id": args.user_id,
                    "capability": capability,
                    "provider_id": provider["provider_id"],
                },
            )
    emit(args, provider)


def cmd_agent_test(args: argparse.Namespace) -> None:
    emit(args, post("/v1/agents/test", {"provider_id": args.provider_id}))


def cmd_sessions(args: argparse.Namespace) -> None:
    sessions = request("/v1/sessions")
    if args.json:
        emit(args, [session_summary(item) for item in sessions])
        return
    if not sessions:
        print("none")
        return
    for session in sessions:
        summary = session_summary(session)
        print(
            f"{summary['session_id']} stage={summary['stage']} "
            f"mastery={summary['mastery']['level']} source={summary['source_title'] or '-'}"
        )


def cmd_show(args: argparse.Namespace) -> None:
    emit(args, request(f"/v1/sessions/{quote(args.session_id)}"), session=True)


def cmd_start(args: argparse.Namespace) -> None:
    emit(args, create_session(args), session=True)


def cmd_answer(args: argparse.Namespace) -> None:
    session = request(f"/v1/sessions/{quote(args.session_id)}")
    item_id = args.item_id
    if not item_id:
        quiz = first_unanswered_quiz(session)
        if not quiz:
            raise StudyAnythingError("Session has no unanswered quiz item.")
        item_id = quiz["item_id"]
    completed = post(
        f"/v1/sessions/{quote(args.session_id)}/answers",
        {"answers": {item_id: args.text}},
    )
    emit(args, completed, session=True)


def cmd_resume(args: argparse.Namespace) -> None:
    emit(args, post(f"/v1/sessions/{quote(args.session_id)}/resume"), session=True)


def cmd_mastery(args: argparse.Namespace) -> None:
    emit(args, request(f"/v1/sessions/{quote(args.session_id)}/mastery"))


def cmd_events(args: argparse.Namespace) -> None:
    emit(args, request(f"/v1/sessions/{quote(args.session_id)}/events"))


def cmd_hitl(args: argparse.Namespace) -> None:
    emit(args, request("/v1/hitl"))


def cmd_resolve(args: argparse.Namespace) -> None:
    resolved = post(
        f"/v1/hitl/{quote(args.task_id)}/resolve",
        {"session_id": args.session_id, "payload": {"note": args.note}},
    )
    emit(args, resolved, session=True)


def cmd_discard(args: argparse.Namespace) -> None:
    if not args.yes:
        raise StudyAnythingError("Discard requires explicit approval. Re-run with --yes.")
    emit(args, post(f"/v1/sessions/{quote(args.session_id)}/discard"), session=True)


def cmd_demo(args: argparse.Namespace) -> None:
    args.user_id = args.user_id or "skill-demo-user"
    args.track = "ACADEMIC"
    args.agent_mode = "demo"
    args.source_type = "local_text"
    args.reference = "demo://skill-cli"
    args.title = "Study Anything CLI Demo"
    args.text = (
        "A learning loop should bind a question to its source, grade a grounded answer, "
        "update mastery, and synthesize a reusable insight."
    )
    session = create_session(args)
    quiz = first_unanswered_quiz(session)
    if not quiz:
        raise StudyAnythingError("Demo agent did not create a quiz item.")
    args.session_id = session["session_id"]
    args.item_id = quiz["item_id"]
    args.text = "The learning loop uses source evidence to grade an answer and update mastery."
    cmd_answer(args)


def add_session_id(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("session_id", help="Study session id")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    subparsers = parser.add_subparsers(dest="command", required=True)

    health = subparsers.add_parser("health", help="Check API health")
    health.set_defaults(func=cmd_health)

    agents = subparsers.add_parser("agents", help="List configured agent providers")
    agents.add_argument("--user-id", default="local-user")
    agents.set_defaults(func=cmd_agents)

    add_http = subparsers.add_parser("agent-add-http", help="Configure a user-owned HTTP agent")
    add_http.add_argument("--label", required=True)
    add_http.add_argument("--endpoint", required=True)
    add_http.add_argument("--capability", action="append", default=[])
    add_http.add_argument("--timeout", type=int, default=15)
    add_http.add_argument("--user-id", default="local-user")
    add_http.add_argument("--set-default", action="store_true")
    add_http.set_defaults(func=cmd_agent_add_http)

    test_agent = subparsers.add_parser("agent-test", help="Run an agent health check")
    test_agent.add_argument("provider_id")
    test_agent.set_defaults(func=cmd_agent_test)

    sessions = subparsers.add_parser("sessions", help="List learning sessions")
    sessions.set_defaults(func=cmd_sessions)

    show = subparsers.add_parser("show", help="Inspect one learning session")
    add_session_id(show)
    show.set_defaults(func=cmd_show)

    start = subparsers.add_parser("start", help="Start a source-bound learning session")
    start.add_argument("--title", required=True)
    start.add_argument("--text", required=True)
    start.add_argument("--reference", default="local://cli")
    start.add_argument("--source-type", default="local_text")
    start.add_argument("--user-id", default="local-user")
    start.add_argument("--track", default="ACADEMIC")
    start.add_argument("--agent-mode", choices=["demo", "configured"], default="demo")
    start.set_defaults(func=cmd_start)

    answer = subparsers.add_parser("answer", help="Submit one quiz answer")
    add_session_id(answer)
    answer.add_argument("--item-id")
    answer.add_argument("--text", required=True)
    answer.set_defaults(func=cmd_answer)

    resume = subparsers.add_parser("resume", help="Resume a learning workflow")
    add_session_id(resume)
    resume.set_defaults(func=cmd_resume)

    mastery = subparsers.add_parser("mastery", help="Show session mastery")
    add_session_id(mastery)
    mastery.set_defaults(func=cmd_mastery)

    events = subparsers.add_parser("events", help="Show session events")
    add_session_id(events)
    events.set_defaults(func=cmd_events)

    hitl = subparsers.add_parser("hitl", help="List open human-review tasks")
    hitl.set_defaults(func=cmd_hitl)

    resolve = subparsers.add_parser("resolve", help="Resolve a human-review task")
    resolve.add_argument("task_id")
    resolve.add_argument("--session-id", required=True)
    resolve.add_argument("--note", default="Resolved from CLI.")
    resolve.set_defaults(func=cmd_resolve)

    discard = subparsers.add_parser("discard", help="Discard a session with explicit approval")
    add_session_id(discard)
    discard.add_argument("--yes", action="store_true")
    discard.set_defaults(func=cmd_discard)

    demo = subparsers.add_parser("demo", help="Complete a deterministic local demo")
    demo.add_argument("--user-id", default="skill-demo-user")
    demo.set_defaults(func=cmd_demo)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    try:
        main()
    except StudyAnythingError as exc:
        print(f"study-anything: {exc}", file=sys.stderr)
        sys.exit(1)
