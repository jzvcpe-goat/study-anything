#!/usr/bin/env python3
"""CLI bridge from Cognitive Loop ProjectEvent/DecisionCard to Study Anything."""

from __future__ import annotations

import argparse
import hashlib
from html import escape
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.core import cognitive_loop_contracts as contracts  # noqa: E402
from study_anything.core.cognitive_loop_learning_adapter import (  # noqa: E402
    COGNITIVE_LOOP_STUDY_ADAPTER_SCHEMA_VERSION,
    run_cognitive_loop_study_adapter,
)


CLI_SCHEMA_VERSION = "cognitive-loop-study-anything-adapter-cli-v1"

FORBIDDEN_PATTERNS = [
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"(?i)\bdiff --git\b"),
    re.compile(r"http://127\.0\.0\.1:8787[^\s\"']*"),
    re.compile(r"/Users/[^\s\"']+"),
]
FORBIDDEN_LITERALS = [
    "Private raw diff",
    "Private source text",
    "learner answer:",
    "AGENT_ENDPOINT=http",
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "This decision should be explained from the cited summary",
]


class CognitiveLoopStudyAdapterCliError(RuntimeError):
    """Readable Study Adapter CLI failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def load_json_file(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise CognitiveLoopStudyAdapterCliError(f"{label} JSON file does not exist: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CognitiveLoopStudyAdapterCliError(f"{label} JSON is malformed: {path}") from exc
    if not isinstance(payload, dict):
        raise CognitiveLoopStudyAdapterCliError(f"{label} JSON must be an object: {path}")
    return payload


def public_input_ref(root: Path, path: Path, *, label: str) -> dict[str, str]:
    data = path.read_bytes()
    try:
        display_path = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        display_path = f"<external-{label}-json>"
    contracts._assert_public_value(f"{label}_input_ref", display_path)  # type: ignore[attr-defined]
    return {
        "path": display_path,
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def resolve_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def resolve_output(root: Path, value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    return path


def build_study_adapter_cli_report(
    *,
    root: Path,
    event_path: Path,
    decision_path: Path,
    generated_at: str,
    objective: str,
    json_ref: str,
    html_ref: str,
) -> dict[str, Any]:
    event_payload = load_json_file(event_path, label="ProjectEvent")
    decision_payload = load_json_file(decision_path, label="DecisionCard")
    adapter_report = run_cognitive_loop_study_adapter(
        project_event=event_payload,
        decision_card=decision_payload,
        generated_at=generated_at,
    )
    projection = adapter_report["cognitive_loop_projection"]
    mastery_record = projection["mastery_record"]
    loop_run = projection["loop_run"]
    learning_loop = adapter_report["study_anything_loop"]
    learning_context = adapter_report["learning_context"]
    agent = adapter_report["agent_evidence"]

    study_card = {
        "schema_version": "study-card-v1",
        "card_id": f"study-card-{mastery_record['record_id']}",
        "title": learning_context["title"],
        "subject": mastery_record["subject"],
        "track": learning_loop["track"],
        "source_reference": learning_loop["source_reference"],
        "source_excerpt_hash": learning_loop["source_excerpt_hash"],
        "mastery_level": mastery_record["level"],
        "bloom": mastery_record["bloom"],
        "practice_questions": [
            "Can the operator explain the decision from the public summary only?",
            "Can the operator name the risk boundary, verification proof, and rollback path?",
            "Can the operator describe what must stay outside Cognitive Loop evidence?",
        ],
        "evidence_refs": mastery_record["evidence_refs"],
        "content_included": False,
    }
    understanding_gaps = [
        {
            "gap_id": "risk-boundary",
            "status": "watch",
            "question": "Operator should explain why raw diffs, answers, Agent endpoints, and keys stay outside evidence.",
            "evidence_ref": f"mastery-record:{mastery_record['record_id']}",
        },
        {
            "gap_id": "rollback-path",
            "status": "watch",
            "question": "Operator should identify how to disable or bypass the learning adapter if the bridge is unhealthy.",
            "evidence_ref": f"loop-run:{loop_run['run_id']}",
        },
    ]
    scribe_summary = {
        "schema_version": "scribe-summary-v1",
        "entry_count": learning_loop["scribe_entry_count"],
        "captured": "counts_and_public_refs_only",
        "source_reference": learning_loop["source_reference"],
        "source_excerpt_hash": learning_loop["source_excerpt_hash"],
        "content_included": False,
        "answers_included": False,
        "feedback_included": False,
    }
    report = {
        "schema_version": CLI_SCHEMA_VERSION,
        "status": "pass",
        "generated_at": generated_at,
        "title": "Cognitive Loop Study Anything Adapter CLI Lite",
        "objective": objective,
        "input_refs": {
            "project_event": public_input_ref(root, event_path, label="project-event"),
            "decision_card": public_input_ref(root, decision_path, label="decision-card"),
            "content_included": False,
        },
        "adapter_core": {
            "schema_version": adapter_report["schema_version"],
            "status": adapter_report["status"],
            "core_schema_expected": COGNITIVE_LOOP_STUDY_ADAPTER_SCHEMA_VERSION,
            "purpose": "Execute a metadata-only Cognitive Loop learning gate through Study Anything.",
        },
        "learning_status": {
            "stage": learning_loop["stage"],
            "track": learning_loop["track"],
            "teaching_layer_count": learning_loop["teaching_layer_count"],
            "quiz_item_count": learning_loop["quiz_item_count"],
            "grading_result_count": learning_loop["grading_result_count"],
            "insight_count": learning_loop["insight_count"],
            "scribe_entry_count": learning_loop["scribe_entry_count"],
            "learning_context_schema": learning_context["schema_version"],
            "learning_context_item_count": learning_context["item_count"],
            "learning_context_text_included": False,
        },
        "study_card": study_card,
        "understanding_gaps": understanding_gaps,
        "scribe_summary": scribe_summary,
        "agent_task_coverage": {
            "audit_status": agent["audit_status"],
            "eval_status": agent["eval_status"],
            "observed_tasks": agent["observed_tasks"],
            "used_fake_agent": agent["used_fake_agent"],
            "used_external_agent": agent["used_external_agent"],
        },
        "mastery_record": mastery_record,
        "loop_run": loop_run,
        "artifact_refs": {
            "json": json_ref,
            "html": html_ref,
        },
        "privacy": {
            "metadata_only_cognitive_loop_evidence": True,
            "raw_source_text_included": False,
            "raw_diff_included": False,
            "learner_answers_included": False,
            "grading_feedback_included": False,
            "agent_endpoints_included": False,
            "agent_metadata_included": False,
            "model_keys_included": False,
            "input_file_contents_included": False,
            "standalone_frontend_required": False,
        },
        "commands": {
            "run_cli": (
                ".venv/bin/python scripts/cognitive_loop_cli.py study-adapter "
                "--event fixtures/cognitive-loop-study-adapter/project-event.json "
                "--decision fixtures/cognitive-loop-study-adapter/decision-card.json --html"
            ),
            "verify_cli": ".venv/bin/python scripts/verify_cognitive_loop_study_adapter_cli.py --check",
            "core_adapter_check": ".venv/bin/python scripts/verify_cognitive_loop_study_anything_adapter.py --check",
            "release_check": "./scripts/release_check.sh",
        },
        "current_limits": [
            "This is a CLI Lite bridge, not a daemonized watcher or full HTML Artifact console.",
            "The fake deterministic Agent is used for local proof; real reasoning remains outside Study Anything.",
            "JSON and HTML reports contain metadata, hashes, status, and public refs only.",
        ],
    }
    assert_no_private_text(report)
    contracts.validate_mastery_record(report["mastery_record"])
    contracts.validate_loop_run(report["loop_run"])
    return report


def assert_no_private_text(payload: Any) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in serialized]
    leaks.extend(pattern.pattern for pattern in FORBIDDEN_PATTERNS if pattern.search(serialized))
    if leaks:
        raise CognitiveLoopStudyAdapterCliError(f"Study Adapter CLI report leaked private text: {leaks}")
    contracts._assert_public_value("study_adapter_cli_report", payload)  # type: ignore[attr-defined]


def _items(values: list[Any], *, key: str = "") -> str:
    if not values:
        return "<li>none</li>"
    if key:
        return "\n".join(
            f"<li>{escape(str(item.get(key, '')))}</li>" for item in values if isinstance(item, Mapping)
        )
    return "\n".join(f"<li>{escape(str(item))}</li>" for item in values)


def render_study_adapter_cli_html(report: Mapping[str, Any]) -> str:
    assert_no_private_text(report)

    def value(path: str, fallback: str = "") -> str:
        current: Any = report
        for part in path.split("."):
            if not isinstance(current, Mapping):
                return fallback
            current = current.get(part)
        return fallback if current is None else str(current)

    learning = report.get("learning_status")
    if not isinstance(learning, Mapping):
        learning = {}
    study_card = report.get("study_card")
    if not isinstance(study_card, Mapping):
        study_card = {}
    gaps = report.get("understanding_gaps")
    if not isinstance(gaps, list):
        gaps = []
    scribe = report.get("scribe_summary")
    if not isinstance(scribe, Mapping):
        scribe = {}
    agent = report.get("agent_task_coverage")
    if not isinstance(agent, Mapping):
        agent = {}
    tasks = agent.get("observed_tasks")
    if not isinstance(tasks, list):
        tasks = []
    commands = report.get("commands")
    if not isinstance(commands, Mapping):
        commands = {}
    command_rows = "\n".join(
        f"<tr><td>{escape(str(key))}</td><td><code>{escape(str(command))}</code></td></tr>"
        for key, command in sorted(commands.items())
    )
    gap_rows = "\n".join(
        "<tr>"
        f"<td>{escape(str(item.get('gap_id', '')))}</td>"
        f"<td>{escape(str(item.get('status', '')))}</td>"
        f"<td>{escape(str(item.get('question', '')))}</td>"
        f"<td><code>{escape(str(item.get('evidence_ref', '')))}</code></td>"
        "</tr>"
        for item in gaps
        if isinstance(item, Mapping)
    )
    json_blob = escape(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(value('title'))}</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #1f261f;
      --muted: #5f6d61;
      --line: #d9e2d2;
      --paper: #fbf8ef;
      --wash: #eef5e7;
      --accent: #245f3b;
      --accent-2: #a6542b;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(166, 84, 43, 0.14), transparent 30rem),
        linear-gradient(135deg, var(--paper), var(--wash));
      font-family: Georgia, 'Times New Roman', serif;
      line-height: 1.5;
    }}
    main {{ width: min(980px, calc(100% - 32px)); margin: 0 auto; padding: 56px 0; }}
    header {{ margin-bottom: 40px; }}
    .brand {{ font-size: clamp(42px, 7vw, 82px); line-height: 0.96; letter-spacing: 0; margin: 0 0 18px; }}
    .summary {{ max-width: 760px; font-size: 20px; color: var(--muted); margin: 0; }}
    section {{ border-top: 1px solid var(--line); padding: 28px 0; }}
    h2 {{ font-size: 24px; margin: 0 0 14px; }}
    .status {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 16px; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 14px; }}
    .status div {{ border-left: 3px solid var(--accent); padding-left: 12px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 15px; }}
    th, td {{ text-align: left; border-bottom: 1px solid var(--line); padding: 10px 8px; vertical-align: top; }}
    code, pre {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 13px; }}
    pre {{ overflow: auto; max-height: 420px; padding: 16px; background: rgba(255,255,255,0.55); border: 1px solid var(--line); }}
    .risk {{ color: var(--accent-2); font-weight: 700; }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1 class="brand">Cognitive Loop Study Adapter</h1>
      <p class="summary">{escape(value('objective'))}</p>
    </header>
    <section>
      <h2>Learning Status</h2>
      <div class="status">
        <div>Status<br><strong>{escape(value('status'))}</strong></div>
        <div>Stage<br><strong>{escape(str(learning.get('stage', '')))}</strong></div>
        <div>Track<br><strong>{escape(str(learning.get('track', '')))}</strong></div>
        <div>Generated<br><strong>{escape(value('generated_at'))}</strong></div>
      </div>
    </section>
    <section>
      <h2>Study Card</h2>
      <p><strong>{escape(str(study_card.get('title', '')))}</strong></p>
      <p>{escape(str(study_card.get('subject', '')))}</p>
      <div class="status">
        <div>Mastery<br><strong>{escape(str(study_card.get('mastery_level', '')))}</strong></div>
        <div>Bloom<br><strong>{escape(str(study_card.get('bloom', '')))}</strong></div>
        <div>Source Hash<br><strong>{escape(str(study_card.get('source_excerpt_hash', '')))}</strong></div>
        <div>Content Included<br><strong>{escape(str(study_card.get('content_included', '')))}</strong></div>
      </div>
      <ul>{_items(study_card.get('practice_questions', []) if isinstance(study_card.get('practice_questions'), list) else [])}</ul>
    </section>
    <section>
      <h2>Understanding Gaps</h2>
      <table>
        <thead><tr><th>Gap</th><th>Status</th><th>Question</th><th>Evidence</th></tr></thead>
        <tbody>{gap_rows}</tbody>
      </table>
    </section>
    <section>
      <h2>Scribe Summary</h2>
      <div class="status">
        <div>Entries<br><strong>{escape(str(scribe.get('entry_count', 0)))}</strong></div>
        <div>Captured<br><strong>{escape(str(scribe.get('captured', '')))}</strong></div>
        <div>Answers Included<br><strong>{escape(str(scribe.get('answers_included', '')))}</strong></div>
        <div>Feedback Included<br><strong>{escape(str(scribe.get('feedback_included', '')))}</strong></div>
      </div>
    </section>
    <section>
      <h2>Agent Task Coverage</h2>
      <div class="status">
        <div>Audit<br><strong>{escape(str(agent.get('audit_status', '')))}</strong></div>
        <div>Eval<br><strong>{escape(str(agent.get('eval_status', '')))}</strong></div>
        <div>Fake Agent<br><strong>{escape(str(agent.get('used_fake_agent', '')))}</strong></div>
        <div>External Agent<br><strong>{escape(str(agent.get('used_external_agent', '')))}</strong></div>
      </div>
      <ul>{_items(tasks)}</ul>
    </section>
    <section>
      <h2>Cognitive Loop Projection</h2>
      <div class="status">
        <div>MasteryRecord<br><strong>{escape(value('mastery_record.record_id'))}</strong></div>
        <div>LoopRun<br><strong>{escape(value('loop_run.run_id'))}</strong></div>
        <div>Loop Status<br><strong>{escape(value('loop_run.status'))}</strong></div>
        <div>Standalone Frontend<br><strong>{escape(value('privacy.standalone_frontend_required'))}</strong></div>
      </div>
    </section>
    <section>
      <h2>Next Commands</h2>
      <table>
        <thead><tr><th>Action</th><th>Command</th></tr></thead>
        <tbody>{command_rows}</tbody>
      </table>
    </section>
    <section>
      <h2>Redacted JSON</h2>
      <pre>{json_blob}</pre>
    </section>
  </main>
</body>
</html>
"""


def write_cli_outputs(
    *,
    root: Path,
    report: dict[str, Any],
    html: bool,
    json_output: Path,
    html_output: Path,
    print_json: bool,
) -> list[str]:
    wrote: list[str] = []
    json_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(dump_json(report), encoding="utf-8")
    wrote.append(str(json_output))
    if html:
        html_output.parent.mkdir(parents=True, exist_ok=True)
        html_output.write_text(render_study_adapter_cli_html(report), encoding="utf-8")
        wrote.append(str(html_output))
    if html and not print_json:
        for path in wrote:
            print(f"wrote: {path}")
    else:
        print(dump_json(report), end="")
    return wrote


def run_from_namespace(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    event_path = resolve_path(root, args.event)
    decision_path = resolve_path(root, args.decision)
    json_ref = args.json_output or ".cognitive-loop/events/cognitive-loop-study-adapter.json"
    html_ref = args.output or ".cognitive-loop/artifacts/cognitive-loop-study-adapter.html"
    report = build_study_adapter_cli_report(
        root=root,
        event_path=event_path,
        decision_path=decision_path,
        generated_at=args.generated_at or contracts._utc_now(),  # type: ignore[attr-defined]
        objective=args.objective,
        json_ref=str(json_ref),
        html_ref=str(html_ref),
    )
    write_cli_outputs(
        root=root,
        report=report,
        html=args.html,
        json_output=resolve_output(root, json_ref),
        html_output=resolve_output(root, html_ref),
        print_json=args.json,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository or project root.")
    parser.add_argument("--event", required=True, help="ProjectEvent JSON file.")
    parser.add_argument("--decision", required=True, help="DecisionCard JSON file.")
    parser.add_argument("--html", action="store_true", help="Write a static HTML learning status artifact.")
    parser.add_argument(
        "--output",
        default=".cognitive-loop/artifacts/cognitive-loop-study-adapter.html",
        help="HTML output path. Defaults under .cognitive-loop/artifacts.",
    )
    parser.add_argument(
        "--json-output",
        default=".cognitive-loop/events/cognitive-loop-study-adapter.json",
        help="JSON output path. Defaults under .cognitive-loop/events.",
    )
    parser.add_argument(
        "--objective",
        default="Run a Study Anything learning gate from Cognitive Loop ProjectEvent and DecisionCard metadata.",
    )
    parser.add_argument("--generated-at", help="Deterministic timestamp for verifiers.")
    parser.add_argument("--json", action="store_true", help="Print JSON even when --html is used.")
    return parser


def main() -> int:
    return run_from_namespace(build_parser().parse_args())


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"cognitive_loop_study_adapter_cli failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
