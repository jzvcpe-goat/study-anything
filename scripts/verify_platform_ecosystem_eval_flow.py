#!/usr/bin/env python3
"""Verify platform ecosystem path with importer, enrichment, retrieval, and eval gates."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from localhost_diagnostics import format_api_unreachable, resolve_api_base, verifier_name_from_file


API_BASE = resolve_api_base()
REQUEST_TIMEOUT_SECONDS = int(os.getenv("PLATFORM_ECOSYSTEM_EVAL_TIMEOUT_SECONDS", "15"))
ROOT = Path(__file__).resolve().parents[1]
VERIFIER_NAME = verifier_name_from_file(__file__)
DEFAULT_PRIVATE_USER = "platform-ecosystem-eval-user"
DEFAULT_QUERY = "AI product manager learning feedback vocabulary"
PRIVATE_IMPORTER_TEXT = (
    "Private importer note: AI PM learning improves when concepts, source evidence, "
    "glossary terms, feedback, and spaced review are connected."
)
PRIVATE_PLATFORM_CONTEXT = (
    "Private platform browser/video context: the learner needs a term map for retrieval "
    "practice, mastery deltas, and source-grounded synthesis."
)
PRIVATE_ANSWER = "Private " + "answer: source evidence plus feedback makes recall more durable."
FORBIDDEN_LITERALS = (
    DEFAULT_PRIVATE_USER,
    PRIVATE_IMPORTER_TEXT,
    PRIVATE_PLATFORM_CONTEXT,
    PRIVATE_ANSWER,
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "AGENT_LLM_API_KEY=",
    "raw_source_text=",
    "learner_answer=",
)


class VerificationError(RuntimeError):
    """Readable ecosystem-smoke failure."""


def sanitize_text(value: str | bytes | None) -> str:
    if value is None:
        text = ""
    elif isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = value
    replacements = {
        DEFAULT_PRIVATE_USER: "<private-user>",
        PRIVATE_IMPORTER_TEXT: "<private-importer-text>",
        PRIVATE_PLATFORM_CONTEXT: "<private-platform-context>",
        PRIVATE_ANSWER: "<private-answer>",
    }
    for literal, replacement in replacements.items():
        text = text.replace(literal, replacement)
    text = re.sub(r"(?i)private importer note:[^\"'\n.]*\.?", "<private-importer-text>", text)
    text = re.sub(r"(?i)private platform browser/video context:[^\"'\n.]*\.?", "<private-platform-context>", text)
    text = re.sub(r"(?i)private answer:[^\"'\n.]*\.?", "<private-answer>", text)
    text = re.sub(r"(?i)private fixture [^:]{1,80} excerpt:[^\"'\n.]*\.?", "<private-fixture-text>", text)
    text = re.sub(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", "<uuid>", text)
    text = re.sub(r"/Users/[^\s\"'?&]+", "<local-path>", text)
    text = re.sub(r"/private/var/folders/[^\s\"'?&]+", "<temp-path>", text)
    text = re.sub(r"/var/folders/[^\s\"'?&]+", "<temp-path>", text)
    text = re.sub(r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}", r"\1=<redacted>", text)
    text = re.sub(r"sk-(?:proj-)?[A-Za-z0-9_-]{12,}", "sk-<redacted>", text)
    text = re.sub(r"([?&](?:api[_-]?key|token|secret)=)[^&\s\"']+", r"\1<redacted>", text, flags=re.IGNORECASE)
    return text.strip()[:1600]


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
    if "cannot reach study anything" in lowered or "connection refused" in lowered or "urlopen error" in lowered:
        return "api_unreachable"
    if "health check failed" in lowered:
        return "api_health_not_ok"
    if "retrieval must be healthy" in lowered:
        return "retrieval_unhealthy"
    if "returned invalid schema" in lowered:
        return "response_schema_invalid"
    if "plugin package validation failed" in lowered or "plugin validation should not" in lowered:
        return "plugin_contract_failed"
    if "importer did not return" in lowered or "context package did not create" in lowered:
        return "importer_context_failed"
    if "retrieval rebuild did not index" in lowered or "retrieval quality did not pass" in lowered:
        return "retrieval_quality_failed"
    if "retrieval did not create a lesson" in lowered or "did not produce quiz items" in lowered:
        return "learning_flow_incomplete"
    if "lesson did not complete" in lowered:
        return "learning_flow_incomplete"
    if "audit/quality gates failed" in lowered or "agent eval report native gate failed" in lowered:
        return "agent_eval_failed"
    if "external eval" in lowered and "failed" in lowered:
        return "external_eval_failed"
    if "leaked private data" in lowered or "strict privacy boundary" in lowered:
        return "privacy_leak"
    return "platform_ecosystem_eval_flow_failed"


def failure_next_steps(classification: str) -> list[str]:
    common = [
        "./scripts/launch_skill_mode.sh",
        f"STUDY_ANYTHING_RETRIEVAL_BACKEND=memory API_BASE={API_BASE} python3 scripts/verify_platform_ecosystem_eval_flow.py",
        "python3 scripts/diagnose_adoption.py",
    ]
    matrix = {
        "localhost_socket_blocked": [
            "Run the verifier from a normal terminal or host shell that permits localhost sockets.",
            "If this came from Codex or another sandboxed Agent, collect this blocked report and rerun outside the sandbox.",
        ],
        "api_unreachable": [
            "Start the Study Anything API first with `./scripts/launch_skill_mode.sh`.",
            "If the API is already running on another port, pass it with `API_BASE=http://127.0.0.1:<port>`.",
        ],
        "api_health_not_ok": [
            "Open `/v1/health` on the configured API_BASE and inspect the reported service status.",
            "Restart Skill Mode, then rerun the ecosystem eval verifier.",
        ],
        "retrieval_unhealthy": [
            "Run Skill Mode with `STUDY_ANYTHING_RETRIEVAL_BACKEND=memory` for local validation.",
            "Check `/v1/retrieval/status` before running the full ecosystem flow.",
        ],
        "response_schema_invalid": [
            "Confirm the API server and verifier come from the same checkout.",
            "Rerun setup with `python3 scripts/setup_env.py` if the API surface is stale.",
        ],
        "plugin_contract_failed": [
            "Run plugin capability and package validation checks before the full ecosystem verifier.",
            "Confirm plugin validation remains metadata-only and does not copy or execute packages.",
        ],
        "importer_context_failed": [
            "Verify the example importer returns a valid Learning Context Package.",
            "Run `python3 scripts/verify_importer_lesson_flow.py` first to isolate importer issues.",
        ],
        "retrieval_quality_failed": [
            "Rebuild retrieval for the source session and inspect `/retrieval/eval` locally.",
            "Use the memory retrieval backend for the first local smoke.",
        ],
        "learning_flow_incomplete": [
            "Check session events locally for the first failed workflow stage.",
            "Rerun the simpler `verify_platform_lesson_flow.py` before the full ecosystem verifier.",
        ],
        "agent_eval_failed": [
            "Run `python3 scripts/verify_agent_eval_flow.py` first to isolate eval failures.",
            "Do not publish raw source, context, or answers while debugging.",
        ],
        "external_eval_failed": [
            "Run `python3 scripts/run_external_agent_evals.py` for the failing adapter shown in the diagnostic.",
            "If optional eval dependencies are missing, install the project dev dependencies and retry.",
        ],
        "privacy_leak": [
            "Do not share the raw transcript publicly.",
            "Fix the leaking evidence/export boundary before using this run as release evidence.",
        ],
    }
    return matrix.get(classification, ["Rerun after starting the local API with retrieval enabled."]) + common


def failure_report(exc: BaseException) -> dict[str, Any]:
    diagnostic = sanitize_text(str(exc))
    classification = classify_failure(diagnostic)
    report = {
        "status": "blocked",
        "classification": classification,
        "diagnostic": diagnostic,
        "next_steps": failure_next_steps(classification),
        "source": {
            "verifier": VERIFIER_NAME,
            "api_base": sanitize_text(API_BASE),
            "retrieval_backend": sanitize_text(os.getenv("STUDY_ANYTHING_RETRIEVAL_BACKEND", "")),
        },
        "privacy": {
            "raw_source_text_included": False,
            "raw_enrichment_text_included": False,
            "learner_answers_included": False,
            "external_eval_stdout_stderr_redacted": True,
            "real_model_keys_included": False,
            "local_absolute_paths_included": False,
        },
    }
    assert_failure_report_redacted(report)
    return report


def format_failure_for_human(report: dict[str, Any]) -> str:
    steps = [
        f"- {sanitize_text(str(step))}"
        for step in report.get("next_steps", [])
        if isinstance(step, str) and step.strip()
    ]
    return "\n".join(
        [
            f"{VERIFIER_NAME} failed:",
            f"classification: {sanitize_text(str(report.get('classification') or 'platform_ecosystem_eval_failed'))}",
            f"Diagnostic: {sanitize_text(str(report.get('diagnostic') or '')) or '(empty)'}",
            "Next steps:",
            *(steps or ["- Start the local API with retrieval enabled, then rerun this verifier."]),
        ]
    )


def assert_failure_report_redacted(report: dict[str, Any]) -> None:
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in serialized]
    if re.search(r"(?i)private (?:importer|platform|answer|fixture)[^\"']+", serialized):
        leaks.append("private smoke text")
    if re.search(r"/Users/[^\s\"']+", serialized):
        leaks.append("local absolute path")
    if re.search(r"/private/(?:var/)?folders/[^\s\"']+", serialized):
        leaks.append("local temp path")
    if re.search(r"sk-(?:proj-)?[A-Za-z0-9_-]{12,}", serialized):
        leaks.append("secret-looking sk token")
    if leaks:
        raise VerificationError(f"Ecosystem eval verifier failure report leaked private data: {leaks}")


def request(path: str, payload: Optional[Dict[str, Any]] = None) -> Any:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(
        f"{API_BASE}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )
    try:
        with urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8")
        raise VerificationError(f"API returned {exc.code} for {path}: {detail}") from exc
    except (URLError, OSError) as exc:
        raise VerificationError(
            format_api_unreachable(API_BASE, exc, verifier=VERIFIER_NAME)
        ) from exc


def assert_schema(value: Dict[str, Any], schema_version: str, label: str) -> None:
    if value.get("schema_version") != schema_version:
        raise VerificationError(f"{label} returned invalid schema: {value}")


def assert_no_leaks(label: str, value: object, forbidden: list[str]) -> None:
    serialized = json.dumps(value, ensure_ascii=False)
    leaks = [fragment for fragment in forbidden if fragment and fragment in serialized]
    if re.search(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}", serialized):
        leaks.append("secret-looking sk token")
    if re.search(r"(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{12,}", serialized):
        leaks.append("secret-looking key/value text")
    if leaks:
        raise VerificationError(f"{label} leaked private data: {leaks}")


def first_quiz_item(session: Dict[str, Any]) -> Dict[str, Any]:
    items = session.get("quiz_items") or []
    if not items or not isinstance(items[0], dict):
        raise VerificationError(f"Session did not produce quiz items: {session}")
    return items[0]


def run_external_eval(tool: str, session_id: str, *, query: str = "") -> Dict[str, Any]:
    command = [
        sys.executable,
        str(ROOT / "scripts" / "run_external_agent_evals.py"),
        "--tool",
        tool,
        "--api-base",
        API_BASE,
        "--session-id",
        session_id,
        "--required",
        "--timeout-seconds",
        "45",
    ]
    if tool == "deepeval":
        command.append("--allow-native-quality-fallback")
    if tool == "retrieval":
        command.extend(["--query", query, "--limit", "3"])
    completed = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
        cwd=ROOT,
    )
    if completed.returncode != 0:
        raise VerificationError(
            f"{tool} external eval failed.\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    try:
        return json.loads(completed.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise VerificationError(f"Could not parse {tool} external eval output: {completed.stdout}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id", default=DEFAULT_PRIVATE_USER)
    parser.add_argument(
        "--query",
        default=DEFAULT_QUERY,
    )
    args = parser.parse_args()

    health = request("/v1/health")
    if health.get("status") != "ok":
        raise VerificationError(f"Health check failed: {health}")
    eval_policy = request("/v1/evals/policy")
    plugin_sdk = request("/v1/plugins/sdk")
    plugin_capabilities = request("/v1/plugins/capabilities")
    plugin_validation = request(
        "/v1/plugins/validate-package",
        {"source_path": "example-enrichment-importer"},
    )
    assert_schema(eval_policy, "agent-eval-policy-v1", "Agent eval policy")
    assert_schema(plugin_sdk, "plugin-sdk-v1", "plugin SDK")
    assert_schema(plugin_capabilities, "plugin-capability-index-v1", "plugin capabilities")
    assert_schema(plugin_validation, "plugin-package-validation-v1", "plugin package validation")
    if plugin_validation.get("status") != "valid":
        raise VerificationError(f"Plugin package validation failed: {plugin_validation}")
    if plugin_validation.get("execution_allowed_by_validation"):
        raise VerificationError(f"Plugin validation should not execute plugin code: {plugin_validation}")
    if (plugin_validation.get("privacy") or {}).get("package_copied"):
        raise VerificationError(f"Plugin validation should not copy plugin packages: {plugin_validation}")

    retrieval_status = request("/v1/retrieval/status")
    if retrieval_status.get("status") != "healthy":
        raise VerificationError(
            "Retrieval must be healthy for the ecosystem eval flow. "
            "Use STUDY_ANYTHING_RETRIEVAL_BACKEND=memory for local Skill Mode."
        )

    importer = request(
        "/v1/importers/example-note-importer/run",
        {
            "inputs": {
                "note_reference": "obsidian://Study Anything/Platform Ecosystem Eval",
                "title": "Platform Ecosystem Eval",
                "markdown_excerpt": PRIVATE_IMPORTER_TEXT,
                "obsidian_backlinks": ["AI PM", "Retrieval", "Agent Eval"],
            },
            "confirmed_permissions": ["write:context"],
            "include_text": True,
        },
    )
    assert_schema(importer, "importer-run-v1", "importer runtime")
    package = importer.get("package")
    if not isinstance(package, dict):
        raise VerificationError(f"Importer did not return a package: {importer}")

    created_source = request(
        "/v1/sessions/from-context-package",
        {
            "user_id": args.user_id,
            "use_demo_agent": True,
            "package": package,
        },
    )
    source_session = created_source.get("session")
    if not isinstance(source_session, dict):
        raise VerificationError(f"Context package did not create a source session: {created_source}")
    source_session_id = str(source_session["session_id"])

    enrichment = request(
        f"/v1/sessions/{quote(source_session_id)}/enrichment",
        {
            "title": "Platform Agent External Context",
            "items": [
                {
                    "source_type": "web",
                    "reference": "https://platform.local/browser/ai-pm-learning",
                    "title": "Browser Context",
                    "locator": "section=ai-pm-learning",
                    "text": PRIVATE_PLATFORM_CONTEXT,
                    "provenance": {
                        "collector": "platform-agent-ecosystem-smoke",
                        "capture_method": "browser_excerpt",
                        "source_owner": "user",
                    },
                    "redaction_policy": "reference_only",
                    "metadata": {"collector": "platform-agent"},
                },
                {
                    "source_type": "video_slice",
                    "reference": "video://platform/ai-pm/clip-1",
                    "title": "Video Slice Context",
                    "locator": "00:01:12-00:02:05",
                    "text": PRIVATE_PLATFORM_CONTEXT,
                    "provenance": {
                        "collector": "platform-agent-ecosystem-smoke",
                        "capture_method": "video_transcript_slice",
                        "source_owner": "user",
                    },
                    "redaction_policy": "reference_only",
                    "metadata": {"collector": "platform-agent"},
                },
            ],
        },
    )
    assert_schema(enrichment, "learning-enrichment-v1", "platform enrichment")
    assert_no_leaks("platform enrichment response", enrichment, [PRIVATE_PLATFORM_CONTEXT])

    rebuilt = request(f"/v1/sessions/{quote(source_session_id)}/retrieval/rebuild", {})
    if rebuilt.get("indexed_count", 0) < 2:
        raise VerificationError(f"Retrieval rebuild did not index platform context: {rebuilt}")

    query_string = urlencode({"q": args.query, "limit": 3})
    retrieval_quality = request(
        f"/v1/sessions/{quote(source_session_id)}/retrieval/eval?{query_string}"
    )
    assert_schema(retrieval_quality, "retrieval-quality-eval-v1", "retrieval quality")
    if retrieval_quality.get("status") != "pass":
        raise VerificationError(f"Retrieval quality did not pass: {retrieval_quality}")
    assert_no_leaks(
        "retrieval quality",
        retrieval_quality,
        [PRIVATE_IMPORTER_TEXT, PRIVATE_PLATFORM_CONTEXT],
    )

    created_lesson = request(
        "/v1/sessions/from-retrieval",
        {
            "source_session_id": source_session_id,
            "query": args.query,
            "user_id": f"{args.user_id}-lesson",
            "use_demo_agent": True,
        },
    )
    assert_schema(created_lesson, "retrieval-session-v1", "retrieval lesson")
    lesson_session = created_lesson.get("session")
    if not isinstance(lesson_session, dict):
        raise VerificationError(f"Retrieval did not create a lesson: {created_lesson}")
    lesson_session_id = str(lesson_session["session_id"])

    teaching = request(
        f"/v1/sessions/{quote(lesson_session_id)}/teaching-layers",
        {"layers": ["overview", "glossary"], "language": "zh", "level": "beginner"},
    )
    assert_schema(teaching, "teaching-layers-v1", "teaching layers")
    running = request(f"/v1/sessions/{quote(lesson_session_id)}/run", {})
    quiz = first_quiz_item(running)
    completed = request(
        f"/v1/sessions/{quote(lesson_session_id)}/answers",
        {"answers": {str(quiz["item_id"]): PRIVATE_ANSWER}},
    )
    if completed.get("stage") != "completed":
        raise VerificationError(f"Lesson did not complete: {completed}")

    audit = request(f"/v1/sessions/{quote(lesson_session_id)}/agent-audit")
    artifact = request(f"/v1/sessions/{quote(lesson_session_id)}/agent-eval/artifact")
    quality = request(f"/v1/sessions/{quote(lesson_session_id)}/agent-eval/quality")
    eval_report = request(f"/v1/sessions/{quote(lesson_session_id)}/agent-eval/report")
    enrichment_artifact = request(
        f"/v1/sessions/{quote(lesson_session_id)}/exports/enrichment-artifact"
    )
    obsidian = request(f"/v1/sessions/{quote(lesson_session_id)}/exports/obsidian")
    learning_package = request(f"/v1/sessions/{quote(lesson_session_id)}/exports/learning-package")
    second_brain = request(f"/v1/sessions/{quote(lesson_session_id)}/exports/second-brain-handoff")
    assert_schema(audit, "agent-audit-v1", "agent audit")
    assert_schema(artifact, "agent-eval-artifact-v1", "agent eval artifact")
    assert_schema(quality, "agent-quality-eval-v1", "agent quality")
    assert_schema(eval_report, "agent-eval-report-v1", "Agent eval report")
    assert_schema(enrichment_artifact, "learning-enrichment-artifact-v1", "enrichment artifact")
    assert_schema(obsidian, "obsidian-markdown-export-v1", "obsidian export")
    assert_schema(learning_package, "learning-package-v1", "learning package")
    assert_schema(second_brain, "second-brain-handoff-v1", "second-brain handoff")
    if audit.get("status") != "verified" or quality.get("status") != "pass":
        raise VerificationError(f"Audit/quality gates failed: audit={audit} quality={quality}")
    if (eval_report.get("native_fast_gate") or {}).get("status") != "pass":
        raise VerificationError(f"Agent eval report native gate failed: {eval_report}")

    retrieval_runner = run_external_eval("retrieval", source_session_id, query=args.query)
    report_runner = run_external_eval("report", lesson_session_id)
    deepeval_runner = run_external_eval("deepeval", lesson_session_id)
    if (
        retrieval_runner.get("status") != "ok"
        or report_runner.get("status") != "ok"
        or deepeval_runner.get("status") != "ok"
    ):
        raise VerificationError(
            "External eval adapters did not pass: "
            f"retrieval={retrieval_runner}, report={report_runner}, deepeval={deepeval_runner}"
        )

    redacted_eval_surfaces = {
        "audit": audit,
        "artifact": artifact,
        "quality": quality,
        "eval_policy": eval_policy,
        "eval_report": eval_report,
        "retrieval_quality": retrieval_quality,
        "retrieval_runner": retrieval_runner,
        "report_runner": report_runner,
        "deepeval_runner": deepeval_runner,
    }
    assert_no_leaks(
        "ecosystem eval evidence",
        redacted_eval_surfaces,
        [PRIVATE_IMPORTER_TEXT, PRIVATE_PLATFORM_CONTEXT, PRIVATE_ANSWER, args.user_id],
    )
    # User-owned exports may include the learner's own answer and review history, but
    # they still must not accidentally contain credentials or secret-looking values.
    assert_no_leaks(
        "user-owned exports",
        {
            "enrichment_artifact": enrichment_artifact,
            "obsidian": obsidian,
            "learning_package": learning_package,
            "second_brain": second_brain,
        },
        [],
    )
    assert_no_leaks(
        "second-brain strict privacy boundary",
        second_brain,
        [PRIVATE_IMPORTER_TEXT, PRIVATE_PLATFORM_CONTEXT, PRIVATE_ANSWER, args.user_id],
    )

    print(
        json.dumps(
            {
                "status": "ok",
                "api_base": API_BASE,
                "source_session_id": source_session_id,
                "lesson_session_id": lesson_session_id,
                "indexed_count": rebuilt["indexed_count"],
                "retrieval_quality_status": retrieval_quality["status"],
                "agent_quality_status": quality["status"],
                "agent_eval_policy_schema": eval_policy["schema_version"],
                "agent_eval_report_schema": eval_report["schema_version"],
                "retrieval_eval_tool": retrieval_runner["framework"],
                "report_eval_tool": report_runner["framework"],
                "deepeval_tool": deepeval_runner["tool"],
                "enrichment_artifact_schema": enrichment_artifact["schema_version"],
                "obsidian_schema": obsidian["schema_version"],
                "learning_package_schema": learning_package["schema_version"],
                "second_brain_schema": second_brain["schema_version"],
                "plugin_sdk_schema": plugin_sdk["schema_version"],
                "plugin_capability_index_schema": plugin_capabilities["schema_version"],
                "plugin_package_validation_schema": plugin_validation["schema_version"],
            },
            ensure_ascii=False,
            sort_keys=True,
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
