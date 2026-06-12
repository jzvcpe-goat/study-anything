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
DEFAULT_HTTP_AGENT_CAPABILITIES = [
    "teach.overview",
    "teach.glossary",
    "teach.examples",
    "quiz.generate",
    "answer.grade",
    "insight.synthesize",
    "note.scribe",
    "source.verify",
    "embedding.create",
]


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


def load_json_file(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            values = json.load(handle)
    except OSError as exc:
        raise StudyAnythingError(f"Cannot read JSON file {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise StudyAnythingError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(values, dict):
        raise StudyAnythingError(f"{path} must contain a JSON object.")
    return values


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
    capabilities = args.capability or DEFAULT_HTTP_AGENT_CAPABILITIES
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


def cmd_agent_audit(args: argparse.Namespace) -> None:
    emit(args, request(f"/v1/sessions/{quote(args.session_id)}/agent-audit"))


def cmd_agent_eval(args: argparse.Namespace) -> None:
    emit(args, request(f"/v1/sessions/{quote(args.session_id)}/agent-eval/artifact"))


def cmd_retrieval_status(args: argparse.Namespace) -> None:
    emit(args, request("/v1/retrieval/status"))


def cmd_retrieval_rebuild(args: argparse.Namespace) -> None:
    emit(args, post(f"/v1/sessions/{quote(args.session_id)}/retrieval/rebuild"))


def cmd_retrieval_search(args: argparse.Namespace) -> None:
    query = urlencode({"q": args.query, "limit": args.limit})
    emit(args, request(f"/v1/sessions/{quote(args.session_id)}/retrieval/search?{query}"))


def cmd_retrieval_eval(args: argparse.Namespace) -> None:
    query = urlencode({"q": args.query, "limit": args.limit})
    emit(args, request(f"/v1/sessions/{quote(args.session_id)}/retrieval/eval?{query}"))


def cmd_retrieval_import(args: argparse.Namespace) -> None:
    payload = {
        "source_session_id": args.source_session_id,
        "query": args.query,
        "limit": args.limit,
        "user_id": args.user_id,
        "track": args.track,
        "use_demo_agent": args.agent_mode == "demo",
    }
    if args.session_id:
        response = post(
            f"/v1/sessions/{quote(args.session_id)}/retrieval/context-package",
            payload,
        )
    else:
        response = post("/v1/sessions/from-retrieval", payload)
    if args.session and isinstance(response, dict) and isinstance(response.get("session"), dict):
        print_session(response["session"])
        return
    emit(args, response)


def cmd_enrich(args: argparse.Namespace) -> None:
    metadata: Dict[str, Any] = {}
    if args.metadata_json:
        try:
            metadata = json.loads(args.metadata_json)
        except json.JSONDecodeError as exc:
            raise StudyAnythingError(f"--metadata-json is not valid JSON: {exc}") from exc
        if not isinstance(metadata, dict):
            raise StudyAnythingError("--metadata-json must decode to an object.")
    payload = {
        "title": args.bundle_title,
        "reference": args.bundle_reference,
        "items": [
            {
                "source_type": args.source_type,
                "reference": args.reference,
                "title": args.title,
                "text": args.text,
                "locator": args.locator or "cli-selection",
                "provenance": {
                    "collector": "study-anything-cli",
                    "capture_method": args.capture_method,
                    "source_owner": "user",
                },
                "redaction_policy": args.redaction_policy,
                "metadata": metadata,
            }
        ],
    }
    emit(args, post(f"/v1/sessions/{quote(args.session_id)}/enrichment", payload))


def cmd_context_validate(args: argparse.Namespace) -> None:
    package = load_json_file(args.package)
    emit(args, post("/v1/context-packages/validate", {"package": package}))


def _importer_inputs(args: argparse.Namespace) -> Dict[str, Any]:
    values: Dict[str, Any] = {}
    if args.input_file:
        values.update(load_json_file(args.input_file))
    if args.input_json:
        try:
            parsed = json.loads(args.input_json)
        except json.JSONDecodeError as exc:
            raise StudyAnythingError(f"--input-json is not valid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise StudyAnythingError("--input-json must decode to an object.")
        values.update(parsed)
    return values


def cmd_importer_run(args: argparse.Namespace) -> None:
    run = post(
        f"/v1/importers/{quote(args.plugin_id)}/run",
        {
            "inputs": _importer_inputs(args),
            "confirmed_permissions": args.confirm_permission,
            "allow_network": args.allow_network,
            "include_text": True,
        },
    )
    package = run.get("package")
    if not isinstance(package, dict):
        raise StudyAnythingError("Importer did not return a package object.")
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            json.dump(package, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
    response: Any = run
    if args.session_id:
        response = post(
            f"/v1/sessions/{quote(args.session_id)}/context-package",
            {"package": package},
        )
    elif args.create_session:
        response = post(
            "/v1/sessions/from-context-package",
            {
                "package": package,
                "user_id": args.user_id,
                "track": args.track,
                "use_demo_agent": args.agent_mode == "demo",
            },
        )
    if args.session and isinstance(response, dict) and isinstance(response.get("session"), dict):
        print_session(response["session"])
        return
    if args.output and response is run and not args.json:
        print(f"wrote: {args.output}")
        return
    emit(args, response)


def cmd_context_import(args: argparse.Namespace) -> None:
    package = load_json_file(args.package)
    if args.session_id:
        response = post(
            f"/v1/sessions/{quote(args.session_id)}/context-package",
            {"package": package},
        )
    else:
        response = post(
            "/v1/sessions/from-context-package",
            {
                "package": package,
                "user_id": args.user_id,
                "track": args.track,
                "use_demo_agent": args.agent_mode == "demo",
            },
        )
    if args.session and not args.json:
        session = response.get("session")
        if isinstance(session, dict):
            print_session(session)
            return
    emit(args, response)


def cmd_teach(args: argparse.Namespace) -> None:
    layers = args.layer or ["overview", "glossary"]
    payload = {
        "layers": layers,
        "language": args.language,
        "level": args.level,
        "max_terms": args.max_terms,
        "example_mode": args.example_mode,
    }
    emit(args, post(f"/v1/sessions/{quote(args.session_id)}/teaching-layers", payload))


def cmd_quality_eval(args: argparse.Namespace) -> None:
    emit(args, request(f"/v1/sessions/{quote(args.session_id)}/agent-eval/quality"))


def cmd_obsidian_export(args: argparse.Namespace) -> None:
    export = request(f"/v1/sessions/{quote(args.session_id)}/exports/obsidian")
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(str(export.get("markdown") or ""))
        if not args.json:
            print(f"wrote: {args.output}")
            return
    if args.markdown and not args.json:
        print(str(export.get("markdown") or ""))
        return
    emit(args, export)


def cmd_enrichment_artifact(args: argparse.Namespace) -> None:
    export = request(f"/v1/sessions/{quote(args.session_id)}/exports/enrichment-artifact")
    content_key = "html" if args.html else "markdown"
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(str(export.get(content_key) or ""))
        if not args.json:
            print(f"wrote: {args.output}")
            return
    if args.markdown and not args.json:
        print(str(export.get("markdown") or ""))
        return
    if args.html and not args.json:
        print(str(export.get("html") or ""))
        return
    emit(args, export)


def cmd_learning_package(args: argparse.Namespace) -> None:
    package = request(f"/v1/sessions/{quote(args.session_id)}/exports/learning-package")
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            json.dump(package, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        if not args.json:
            print(f"wrote: {args.output}")
            return
    emit(args, package)


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


def cmd_lesson(args: argparse.Namespace) -> None:
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
    if args.enrichment_text:
        post(
            f"/v1/sessions/{quote(session_id)}/enrichment",
            {
                "title": args.enrichment_bundle_title,
                "items": [
                    {
                        "source_type": args.enrichment_source_type,
                        "reference": args.enrichment_reference,
                        "title": args.enrichment_title,
                        "text": args.enrichment_text,
                        "locator": args.enrichment_locator or "cli-selection",
                        "provenance": {
                            "collector": "study-anything-cli",
                            "capture_method": args.enrichment_capture_method,
                            "source_owner": "user",
                        },
                        "redaction_policy": "reference_only",
                    }
                ],
            },
        )
    teaching = post(
        f"/v1/sessions/{quote(session_id)}/teaching-layers",
        {
            "layers": args.layer or ["overview", "glossary"],
            "language": args.language,
            "level": args.level,
        },
    )
    running = post(f"/v1/sessions/{quote(session_id)}/run")
    quiz = first_unanswered_quiz(running)
    if not quiz:
        raise StudyAnythingError("Lesson flow did not produce an unanswered quiz item.")
    completed = post(
        f"/v1/sessions/{quote(session_id)}/answers",
        {"answers": {quiz["item_id"]: args.answer}},
    )
    audit = request(f"/v1/sessions/{quote(session_id)}/agent-audit")
    artifact = request(f"/v1/sessions/{quote(session_id)}/agent-eval/artifact")
    quality = request(f"/v1/sessions/{quote(session_id)}/agent-eval/quality")
    obsidian = request(f"/v1/sessions/{quote(session_id)}/exports/obsidian")
    package = request(f"/v1/sessions/{quote(session_id)}/exports/learning-package")
    result = {
        "status": "ok" if completed.get("stage") == "completed" else "needs_review",
        "session": session_summary(completed),
        "teaching_schema": teaching.get("schema_version"),
        "agent_audit_status": audit.get("status"),
        "agent_eval_schema": artifact.get("schema_version"),
        "quality_status": quality.get("status"),
        "quality_schema": quality.get("schema_version"),
        "obsidian_schema": obsidian.get("schema_version"),
        "obsidian_filename": obsidian.get("filename"),
        "learning_package_schema": package.get("schema_version"),
        "learning_package_filename": package.get("filename"),
    }
    if args.json:
        emit(args, result)
        return
    print(f"session: {session_id}")
    print(f"stage: {completed.get('stage')}")
    print(f"agent_audit: {audit.get('status')}")
    print(f"quality: {quality.get('status')} ({quality.get('quality_score')})")
    print(f"obsidian: {obsidian.get('filename')}")
    print(f"learning_package: {package.get('filename')}")


def add_session_id(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("session_id", help="Study session id")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", help="Override STUDY_ANYTHING_API_BASE for this command")
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

    agent_audit = subparsers.add_parser("agent-audit", help="Show redacted Agent invocation proof")
    add_session_id(agent_audit)
    agent_audit.set_defaults(func=cmd_agent_audit)

    agent_eval = subparsers.add_parser("agent-eval", help="Show redacted Agent eval artifact")
    add_session_id(agent_eval)
    agent_eval.set_defaults(func=cmd_agent_eval)

    retrieval_status = subparsers.add_parser("retrieval-status", help="Show retrieval adapter status")
    retrieval_status.set_defaults(func=cmd_retrieval_status)

    retrieval_rebuild = subparsers.add_parser(
        "retrieval-rebuild",
        help="Rebuild the retrieval index for a session",
    )
    add_session_id(retrieval_rebuild)
    retrieval_rebuild.set_defaults(func=cmd_retrieval_rebuild)

    retrieval_search = subparsers.add_parser(
        "retrieval-search",
        help="Search a rebuilt retrieval index for one session",
    )
    add_session_id(retrieval_search)
    retrieval_search.add_argument("--query", required=True)
    retrieval_search.add_argument("--limit", type=int, default=5)
    retrieval_search.set_defaults(func=cmd_retrieval_search)

    retrieval_eval = subparsers.add_parser(
        "retrieval-eval",
        help="Show redacted retrieval/context quality gates",
    )
    add_session_id(retrieval_eval)
    retrieval_eval.add_argument("--query", required=True)
    retrieval_eval.add_argument("--limit", type=int, default=5)
    retrieval_eval.set_defaults(func=cmd_retrieval_eval)

    retrieval_import = subparsers.add_parser(
        "retrieval-import",
        help="Create or expand a session from retrieval results",
    )
    retrieval_import.add_argument("--source-session-id", required=True)
    retrieval_import.add_argument("--query", required=True)
    retrieval_import.add_argument("--limit", type=int, default=5)
    retrieval_import.add_argument("--session-id", help="Expand an existing session instead of creating one")
    retrieval_import.add_argument("--user-id", default="retrieval-import-user")
    retrieval_import.add_argument("--track")
    retrieval_import.add_argument("--agent-mode", choices=["demo", "configured"], default="demo")
    retrieval_import.add_argument("--session", action="store_true")
    retrieval_import.set_defaults(func=cmd_retrieval_import)

    enrich = subparsers.add_parser("enrich", help="Attach one enrichment item to a session")
    add_session_id(enrich)
    enrich.add_argument("--source-type", default="web")
    enrich.add_argument("--reference", required=True)
    enrich.add_argument("--title", required=True)
    enrich.add_argument("--text", required=True)
    enrich.add_argument("--locator")
    enrich.add_argument("--capture-method", default="manual_excerpt")
    enrich.add_argument(
        "--redaction-policy",
        choices=["reference_only", "hash_and_locator", "summary_only"],
        default="reference_only",
    )
    enrich.add_argument("--metadata-json")
    enrich.add_argument("--bundle-title", default="Learning Enrichment Bundle")
    enrich.add_argument("--bundle-reference")
    enrich.set_defaults(func=cmd_enrich)

    context_validate = subparsers.add_parser(
        "context-validate",
        help="Validate a Learning Context Package JSON file",
    )
    context_validate.add_argument("package", help="Path to learning-context-package-v1 JSON")
    context_validate.set_defaults(func=cmd_context_validate)

    importer_run = subparsers.add_parser(
        "importer-run",
        help="Run a confirmed local importer plugin and optionally create or expand a session",
    )
    importer_run.add_argument("plugin_id")
    importer_run.add_argument("--input-file", help="JSON object passed to build_context_package")
    importer_run.add_argument("--input-json", help="JSON object passed to build_context_package")
    importer_run.add_argument(
        "--confirm-permission",
        action="append",
        default=[],
        help="Manifest permission to confirm; repeat for every requested permission",
    )
    importer_run.add_argument("--allow-network", action="store_true")
    importer_run.add_argument("--output", help="Write the generated Learning Context Package JSON")
    importer_run.add_argument("--session-id", help="Expand an existing session with the generated package")
    importer_run.add_argument("--create-session", action="store_true")
    importer_run.add_argument("--user-id", default="importer-run-user")
    importer_run.add_argument("--track")
    importer_run.add_argument("--agent-mode", choices=["demo", "configured"], default="demo")
    importer_run.add_argument(
        "--session",
        action="store_true",
        help="Print a compact session summary when a session is created or expanded",
    )
    importer_run.set_defaults(func=cmd_importer_run)

    context_import = subparsers.add_parser(
        "context-import",
        help="Create or expand a session from a Learning Context Package JSON file",
    )
    context_import.add_argument("package", help="Path to learning-context-package-v1 JSON")
    context_import.add_argument("--session-id", help="Expand an existing session instead of creating one")
    context_import.add_argument("--user-id", default="context-import-user")
    context_import.add_argument("--track")
    context_import.add_argument("--agent-mode", choices=["demo", "configured"], default="demo")
    context_import.add_argument(
        "--session",
        action="store_true",
        help="Print a compact session summary when possible",
    )
    context_import.set_defaults(func=cmd_context_import)

    teach = subparsers.add_parser("teach", help="Generate source-bound teaching layers")
    add_session_id(teach)
    teach.add_argument("--layer", action="append", choices=["overview", "glossary", "examples", "scribe"])
    teach.add_argument("--language", default="zh")
    teach.add_argument("--level", default="beginner")
    teach.add_argument("--max-terms", type=int, default=8)
    teach.add_argument("--example-mode", default="mixed")
    teach.set_defaults(func=cmd_teach)

    quality_eval = subparsers.add_parser("quality-eval", help="Show deterministic teaching-quality gates")
    add_session_id(quality_eval)
    quality_eval.set_defaults(func=cmd_quality_eval)

    obsidian_export = subparsers.add_parser("obsidian-export", help="Export an Obsidian markdown note")
    add_session_id(obsidian_export)
    obsidian_export.add_argument("--markdown", action="store_true", help="Print only Markdown")
    obsidian_export.add_argument("--output", help="Write Markdown to a path")
    obsidian_export.set_defaults(func=cmd_obsidian_export)

    enrichment_artifact = subparsers.add_parser(
        "enrichment-artifact",
        help="Export a redacted Markdown/HTML enrichment micro-lesson",
    )
    add_session_id(enrichment_artifact)
    enrichment_artifact.add_argument("--markdown", action="store_true", help="Print only Markdown")
    enrichment_artifact.add_argument("--html", action="store_true", help="Print only HTML")
    enrichment_artifact.add_argument("--output", help="Write Markdown or HTML to a path")
    enrichment_artifact.set_defaults(func=cmd_enrichment_artifact)

    package_export = subparsers.add_parser("package-export", help="Export a portable learning package")
    add_session_id(package_export)
    package_export.add_argument("--output", help="Write package JSON to a path")
    package_export.set_defaults(func=cmd_learning_package)

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

    lesson = subparsers.add_parser("lesson", help="Complete one source-bound learning lesson")
    lesson.add_argument("--title", required=True)
    lesson.add_argument("--text", required=True)
    lesson.add_argument("--reference", default="local://lesson")
    lesson.add_argument("--source-type", default="local_text")
    lesson.add_argument("--answer", required=True)
    lesson.add_argument("--user-id", default="lesson-user")
    lesson.add_argument("--track", default="ACADEMIC")
    lesson.add_argument("--agent-mode", choices=["demo", "configured"], default="demo")
    lesson.add_argument("--layer", action="append", choices=["overview", "glossary", "examples", "scribe"])
    lesson.add_argument("--language", default="zh")
    lesson.add_argument("--level", default="beginner")
    lesson.add_argument("--enrichment-text")
    lesson.add_argument("--enrichment-source-type", default="web")
    lesson.add_argument("--enrichment-reference", default="https://example.test/lesson-enrichment")
    lesson.add_argument("--enrichment-title", default="Lesson Enrichment")
    lesson.add_argument("--enrichment-locator")
    lesson.add_argument("--enrichment-capture-method", default="manual_excerpt")
    lesson.add_argument("--enrichment-bundle-title", default="Lesson Enrichment Bundle")
    lesson.set_defaults(func=cmd_lesson)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.api_base:
        os.environ["STUDY_ANYTHING_API_BASE"] = args.api_base
    args.func(args)


if __name__ == "__main__":
    try:
        main()
    except StudyAnythingError as exc:
        print(f"study-anything: {exc}", file=sys.stderr)
        sys.exit(1)
