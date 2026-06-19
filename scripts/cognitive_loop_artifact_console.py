#!/usr/bin/env python3
"""Build a static metadata-only Cognitive Loop HTML Artifact Console."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
from html import escape
import json
from pathlib import Path
import sqlite3
import sys
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import cognitive_loop_event_store as event_store  # noqa: E402


CONSOLE_SCHEMA_VERSION = "cognitive-loop-artifact-console-v1"

FORBIDDEN_TEXT = (
    "sk-proj-",
    "bearer ",
    "raw private source text",
    "private source text",
    "learner answer:",
    "diff --git",
    "api_key",
    "agent endpoint:",
    "http://127.0.0.1:8787",
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "raw test output",
)


class ArtifactConsoleError(RuntimeError):
    """Readable Artifact Console CLI failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _assert_no_forbidden_text(value: Any, *, label: str) -> None:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)
    lowered = text.lower()
    leaked = [needle for needle in FORBIDDEN_TEXT if needle.lower() in lowered]
    if leaked:
        raise ArtifactConsoleError(f"{label} contains private-looking text: {leaked}")


def _root(args: argparse.Namespace) -> Path:
    return Path(args.root).resolve()


def _resolve_under_root(root: Path, value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ArtifactConsoleError(f"Path must stay under project root: {value}") from exc
    return path


def _relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_json_summary(root: Path, path: Path) -> dict[str, Any]:
    relative = _relative(root, path)
    data = path.read_bytes()
    text = data.decode("utf-8", errors="replace")
    _assert_no_forbidden_text(text, label=relative)
    schema_version = "unknown"
    status = "unknown"
    event_id = ""
    decision_id = ""
    loop_run_id = ""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, Mapping):
        schema_version = str(payload.get("schema_version") or "unknown")
        status = str(payload.get("status") or "unknown")
        event = payload.get("project_event")
        if isinstance(event, Mapping):
            event_id = str(event.get("event_id") or "")
        decision = payload.get("decision_card")
        if isinstance(decision, Mapping):
            decision_id = str(decision.get("decision_id") or "")
        loop = payload.get("loop_run")
        if isinstance(loop, Mapping):
            loop_run_id = str(loop.get("run_id") or "")
    return {
        "path": relative,
        "kind": "json",
        "schema_version": schema_version,
        "status": status,
        "event_id": event_id,
        "decision_id": decision_id,
        "loop_run_id": loop_run_id,
        "size_bytes": len(data),
        "sha256": _sha256_bytes(data),
        "content_included": False,
    }


def _scan_artifacts(root: Path, *, console_outputs: set[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for directory in (root / ".cognitive-loop" / "events", root / ".cognitive-loop" / "artifacts"):
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*")):
            if not path.is_file() or path.suffix not in {".json", ".html", ".md"}:
                continue
            relative = _relative(root, path)
            if relative in console_outputs:
                continue
            if path.suffix == ".json":
                records.append(_safe_json_summary(root, path))
                continue
            data = path.read_bytes()
            _assert_no_forbidden_text(relative, label=f"artifact path:{relative}")
            records.append(
                {
                    "path": relative,
                    "kind": path.suffix.lstrip("."),
                    "schema_version": "not_applicable",
                    "status": "present",
                    "event_id": "",
                    "decision_id": "",
                    "loop_run_id": "",
                    "size_bytes": len(data),
                    "sha256": _sha256_bytes(data),
                    "content_included": False,
                }
            )
    return records


def _db_path(root: Path, raw_path: str | None) -> Path:
    value = raw_path or ".cognitive-loop/cognitive-loop-events.sqlite"
    return _resolve_under_root(root, value)


def _load_event_store(root: Path, db_path: Path) -> dict[str, Any]:
    with event_store.connect(db_path) as connection:
        event_store.initialize(connection)
        events = event_store.list_events(connection)
        artifact_count = event_store.count_rows(connection, "artifacts")
    _assert_no_forbidden_text(events, label="event_store_events")
    missing_sources = [
        item["source_path"]
        for item in events
        if isinstance(item, Mapping) and not (root / str(item.get("source_path", ""))).is_file()
    ]
    event_types = Counter(str(item.get("event_type", "unknown")) for item in events)
    artifact_kinds = Counter(str(item.get("artifact_kind", "unknown")) for item in events)
    sensitivities = Counter(str(item.get("sensitivity", "unknown")) for item in events)
    return {
        "db_path": _relative(root, db_path),
        "event_count": len(events),
        "artifact_count": artifact_count,
        "missing_source_count": len(missing_sources),
        "missing_sources": sorted(missing_sources),
        "event_types": dict(sorted(event_types.items())),
        "artifact_kinds": dict(sorted(artifact_kinds.items())),
        "sensitivities": dict(sorted(sensitivities.items())),
        "latest_events": events[-12:],
        "content_included": False,
    }


def _load_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _watcher_runner_section(root: Path, artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    runner_paths = [
        item["path"]
        for item in artifacts
        if str(item.get("schema_version")) == "cognitive-loop-watcher-runner-v1"
    ]
    accepted = 0
    skipped = 0
    duplicate_count = 0
    high_risk = 0
    study_adapter_triggered = False
    for relative in runner_paths:
        payload = _load_optional_json(root / relative)
        if not payload:
            continue
        observations = payload.get("observations", {})
        events_written = payload.get("events_written", [])
        if isinstance(observations, Mapping):
            accepted += int(observations.get("deduped_count") or 0)
            skipped += int(observations.get("skipped_count") or 0)
            duplicate_count += int(observations.get("duplicate_count") or 0)
        if isinstance(events_written, list):
            high_risk += sum(
                1 for item in events_written if isinstance(item, Mapping) and item.get("high_risk") is True
            )
        study = payload.get("study_adapter_gate")
        if isinstance(study, Mapping) and study.get("triggered") is True:
            study_adapter_triggered = True
    return {
        "status": "ready" if runner_paths else "no_runner_artifacts",
        "runner_report_count": len(runner_paths),
        "accepted_observation_count": accepted,
        "skipped_observation_count": skipped,
        "duplicate_observation_count": duplicate_count,
        "high_risk_event_count": high_risk,
        "study_adapter_triggered": study_adapter_triggered,
        "source_paths": runner_paths,
        "content_included": False,
    }


def _study_adapter_section(root: Path, artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    study_paths = [
        item["path"]
        for item in artifacts
        if str(item.get("schema_version")) == "cognitive-loop-study-anything-adapter-cli-v1"
    ]
    cards: list[dict[str, Any]] = []
    for relative in study_paths:
        payload = _load_optional_json(root / relative)
        if not payload:
            continue
        mastery = payload.get("mastery_record", {})
        study_card = payload.get("study_card", {})
        artifact_refs = payload.get("artifact_refs", {})
        cards.append(
            {
                "path": relative,
                "status": str(payload.get("status", "unknown")),
                "subject": str(mastery.get("subject", "")) if isinstance(mastery, Mapping) else "",
                "mastery_level": mastery.get("level") if isinstance(mastery, Mapping) else None,
                "bloom": str(mastery.get("bloom", "")) if isinstance(mastery, Mapping) else "",
                "card_id": str(study_card.get("card_id", "")) if isinstance(study_card, Mapping) else "",
                "html_ref": str(artifact_refs.get("html", "")) if isinstance(artifact_refs, Mapping) else "",
                "content_included": False,
            }
        )
    return {
        "status": "ready" if cards else "no_study_adapter_artifacts",
        "study_adapter_artifact_count": len(cards),
        "cards": cards,
        "content_included": False,
    }


def _gate_section(event_store_summary: Mapping[str, Any], artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    latest_events = event_store_summary.get("latest_events")
    decisions: list[dict[str, str]] = []
    loop_runs: list[dict[str, str]] = []
    if isinstance(latest_events, list):
        for item in latest_events:
            if not isinstance(item, Mapping):
                continue
            metadata = item.get("metadata", {})
            if not isinstance(metadata, Mapping):
                continue
            decision_id = str(metadata.get("decision_id") or "")
            if decision_id:
                decisions.append(
                    {
                        "decision_id": decision_id,
                        "status": str(metadata.get("decision_status") or ""),
                        "source_path": str(item.get("source_path") or ""),
                    }
                )
            loop_run_id = str(metadata.get("loop_run_id") or "")
            if loop_run_id:
                loop_runs.append(
                    {
                        "loop_run_id": loop_run_id,
                        "status": str(metadata.get("loop_status") or ""),
                        "source_path": str(item.get("source_path") or ""),
                    }
                )
    human_gate_count = sum(
        1 for item in artifacts if str(item.get("schema_version")).startswith("cognitive-loop-human-gate")
    )
    return {
        "status": "ready" if decisions or loop_runs or human_gate_count else "no_gate_artifacts",
        "decision_count": len(decisions),
        "loop_run_count": len(loop_runs),
        "human_gate_artifact_count": human_gate_count,
        "decisions": decisions[-12:],
        "loop_runs": loop_runs[-12:],
        "content_included": False,
    }


def _artifact_health_section(
    root: Path,
    artifacts: list[dict[str, Any]],
    event_store_summary: Mapping[str, Any],
) -> dict[str, Any]:
    kinds = Counter(str(item.get("kind", "unknown")) for item in artifacts)
    schema_versions = Counter(str(item.get("schema_version", "unknown")) for item in artifacts)
    missing_sources = list(event_store_summary.get("missing_sources", []))
    return {
        "status": "ready" if not missing_sources else "degraded_missing_sources",
        "artifact_count": len(artifacts),
        "json_count": kinds.get("json", 0),
        "html_count": kinds.get("html", 0),
        "markdown_count": kinds.get("md", 0),
        "schema_versions": dict(sorted(schema_versions.items())),
        "missing_event_source_count": len(missing_sources),
        "missing_event_sources": missing_sources,
        "content_included": False,
    }


def _provenance(path: str, *, command: str, inputs: Iterable[str]) -> dict[str, Any]:
    return {
        "output_path": path,
        "command": command,
        "input_refs": sorted(set(inputs)),
        "content_included": False,
        "redaction_evidence": {
            "source_text_included": False,
            "raw_diff_included": False,
            "test_output_included": False,
            "learner_answers_included": False,
            "agent_endpoints_included": False,
            "agent_metadata_included": False,
            "prompt_text_included": False,
            "model_keys_included": False,
        },
    }


def build_console_report(
    *,
    root: Path,
    db_path: Path,
    html_ref: str,
    manifest_ref: str,
    generated_at: str,
) -> dict[str, Any]:
    console_outputs = {html_ref, manifest_ref}
    event_summary = _load_event_store(root, db_path)
    artifacts = _scan_artifacts(root, console_outputs=console_outputs)
    watcher = _watcher_runner_section(root, artifacts)
    study = _study_adapter_section(root, artifacts)
    gates = _gate_section(event_summary, artifacts)
    artifact_health = _artifact_health_section(root, artifacts, event_summary)
    status = "ready"
    if artifact_health["status"] != "ready":
        status = "partial"
    report = {
        "schema_version": CONSOLE_SCHEMA_VERSION,
        "status": status,
        "generated_at": generated_at,
        "title": "Cognitive Loop HTML Artifact Console Lite",
        "mode": "static_metadata_only",
        "standalone_frontend_required": False,
        "watcher_daemon_started": False,
        "realtime_transport": "none",
        "sections": {
            "event_store": event_summary,
            "watcher_runner": watcher,
            "study_adapter": study,
            "decision_gate_loop": gates,
            "artifact_health": artifact_health,
        },
        "artifact_refs": {
            "html": html_ref,
            "manifest": manifest_ref,
        },
        "provenance": {
            "event_store": _provenance(
                html_ref,
                command="python3 scripts/cognitive_loop_artifact_console.py build --html",
                inputs=[event_summary["db_path"]],
            ),
            "watcher_runner": _provenance(
                html_ref,
                command=".venv/bin/python scripts/cognitive_loop_watcher_runner.py run --html --study-adapter",
                inputs=watcher["source_paths"],
            ),
            "study_adapter": _provenance(
                html_ref,
                command=".venv/bin/python scripts/cognitive_loop_cli.py study-adapter --html",
                inputs=[card["path"] for card in study["cards"]],
            ),
            "decision_gate_loop": _provenance(
                html_ref,
                command="python3 scripts/cognitive_loop_cli.py gate --html",
                inputs=[
                    item["source_path"]
                    for item in gates["decisions"] + gates["loop_runs"]
                    if item.get("source_path")
                ],
            ),
            "artifact_health": _provenance(
                html_ref,
                command="python3 scripts/cognitive_loop_cli.py doctor --html",
                inputs=[item["path"] for item in artifacts],
            ),
        },
        "privacy": {
            "metadata_only": True,
            "event_json_contents_included": False,
            "html_contents_included": False,
            "markdown_contents_included": False,
            "source_text_included": False,
            "raw_diff_included": False,
            "test_output_included": False,
            "learner_answers_included": False,
            "agent_endpoints_included": False,
            "agent_metadata_included": False,
            "prompt_text_included": False,
            "model_keys_included": False,
            "standalone_frontend_required": False,
        },
        "commands": {
            "build_console": "python3 scripts/cognitive_loop_artifact_console.py build --html",
            "verify_console": "python3 scripts/verify_cognitive_loop_artifact_console.py --check",
            "runner_lite": ".venv/bin/python scripts/cognitive_loop_watcher_runner.py run --html --study-adapter",
            "event_store_export": "python3 scripts/cognitive_loop_event_store.py export --html",
        },
    }
    _assert_no_forbidden_text(report, label="artifact_console_report")
    return report


def _rows(items: Mapping[str, Any]) -> str:
    return "\n".join(
        f"<tr><th>{escape(str(key))}</th><td>{escape(str(value))}</td></tr>"
        for key, value in items.items()
    )


def _latest_event_rows(events: list[Any]) -> str:
    if not events:
        return '<tr><td colspan="5">No Event Store rows yet.</td></tr>'
    rows: list[str] = []
    for item in events[-8:]:
        if not isinstance(item, Mapping):
            continue
        rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('timestamp', '')))}</td>"
            f"<td>{escape(str(item.get('event_type', '')))}</td>"
            f"<td>{escape(str(item.get('artifact_kind', '')))}</td>"
            f"<td>{escape(str(item.get('source_path', '')))}</td>"
            f"<td><code>{escape(str(item.get('artifact_sha256', ''))[:16])}</code></td>"
            "</tr>"
        )
    return "\n".join(rows)


def _study_rows(cards: list[Any]) -> str:
    if not cards:
        return '<tr><td colspan="5">No Study Adapter artifacts yet.</td></tr>'
    rows: list[str] = []
    for card in cards:
        if not isinstance(card, Mapping):
            continue
        html_ref = str(card.get("html_ref") or "")
        link = escape(html_ref)
        html_link = f'<a href="{link}">HTML</a>' if html_ref else "none"
        rows.append(
            "<tr>"
            f"<td>{escape(str(card.get('subject', '')))}</td>"
            f"<td>{escape(str(card.get('mastery_level', '')))}</td>"
            f"<td>{escape(str(card.get('bloom', '')))}</td>"
            f"<td>{escape(str(card.get('path', '')))}</td>"
            f"<td>{html_link}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def render_console_html(report: Mapping[str, Any]) -> str:
    sections = report.get("sections")
    if not isinstance(sections, Mapping):
        sections = {}
    event_summary = sections.get("event_store") if isinstance(sections.get("event_store"), Mapping) else {}
    watcher = sections.get("watcher_runner") if isinstance(sections.get("watcher_runner"), Mapping) else {}
    study = sections.get("study_adapter") if isinstance(sections.get("study_adapter"), Mapping) else {}
    gates = sections.get("decision_gate_loop") if isinstance(sections.get("decision_gate_loop"), Mapping) else {}
    health = sections.get("artifact_health") if isinstance(sections.get("artifact_health"), Mapping) else {}
    json_blob = escape(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Cognitive Loop Artifact Console Lite</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #17211b;
      --muted: #5e6a61;
      --paper: #fbfaf4;
      --wash: #edf4ea;
      --line: #d9e2d3;
      --accent: #1f6a49;
      --amber: #8b5d12;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Charter, 'Iowan Old Style', Georgia, serif;
      color: var(--ink);
      background:
        linear-gradient(135deg, rgba(31, 106, 73, 0.16), transparent 38rem),
        radial-gradient(circle at top right, rgba(139, 93, 18, 0.13), transparent 34rem),
        linear-gradient(180deg, var(--paper), var(--wash));
      line-height: 1.5;
    }}
    main {{ width: min(1120px, calc(100% - 32px)); margin: 0 auto; padding: 48px 0 72px; }}
    header {{ min-height: 42vh; display: grid; align-content: center; border-bottom: 1px solid var(--line); }}
    h1 {{ font-size: clamp(40px, 8vw, 92px); line-height: 0.95; letter-spacing: 0; margin: 0 0 18px; }}
    .lede {{ max-width: 780px; font-size: clamp(18px, 2vw, 24px); color: var(--muted); margin: 0; }}
    .grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin-top: 28px; }}
    .metric {{ border-left: 3px solid var(--accent); padding: 6px 0 6px 12px; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
    .metric strong {{ display: block; font-size: 24px; font-family: Charter, 'Iowan Old Style', Georgia, serif; }}
    section {{ border-bottom: 1px solid var(--line); padding: 28px 0; }}
    h2 {{ font-size: 26px; margin: 0 0 12px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ text-align: left; border-top: 1px solid var(--line); padding: 10px 8px; vertical-align: top; overflow-wrap: anywhere; }}
    a {{ color: var(--accent); }}
    code, pre {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; }}
    pre {{ overflow: auto; max-height: 440px; padding: 16px; background: rgba(255,255,255,0.54); border: 1px solid var(--line); }}
    .note {{ color: var(--muted); max-width: 760px; }}
    @media (max-width: 760px) {{
      main {{ width: min(100% - 20px, 1120px); padding-top: 28px; }}
      header {{ min-height: 36vh; }}
      .grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      table {{ display: block; overflow-x: auto; white-space: nowrap; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Cognitive Loop Artifact Console</h1>
      <p class="lede">A local, static, metadata-only console for Event Store rows, watcher runner outputs, Study Adapter artifacts, gates, and artifact health. No daemon, no standalone frontend, no private content.</p>
      <div class="grid">
        <div class="metric">Status<strong>{escape(str(report.get('status', '')))}</strong></div>
        <div class="metric">Events<strong>{escape(str(event_summary.get('event_count', 0)))}</strong></div>
        <div class="metric">Artifacts<strong>{escape(str(health.get('artifact_count', 0)))}</strong></div>
        <div class="metric">Runner Reports<strong>{escape(str(watcher.get('runner_report_count', 0)))}</strong></div>
      </div>
    </header>

    <section>
      <h2>Event Store</h2>
      <p class="note">Rows are loaded from SQLite metadata only. Source event bodies are not embedded.</p>
      <table>{_rows({
        'db_path': event_summary.get('db_path', ''),
        'event_count': event_summary.get('event_count', 0),
        'artifact_count': event_summary.get('artifact_count', 0),
        'missing_source_count': event_summary.get('missing_source_count', 0),
      })}</table>
    </section>

    <section>
      <h2>Watcher Runner</h2>
      <table>{_rows({
        'status': watcher.get('status', ''),
        'accepted_observation_count': watcher.get('accepted_observation_count', 0),
        'skipped_observation_count': watcher.get('skipped_observation_count', 0),
        'duplicate_observation_count': watcher.get('duplicate_observation_count', 0),
        'high_risk_event_count': watcher.get('high_risk_event_count', 0),
        'study_adapter_triggered': watcher.get('study_adapter_triggered', False),
      })}</table>
    </section>

    <section>
      <h2>Study Adapter</h2>
      <table>
        <thead><tr><th>Subject</th><th>Mastery</th><th>Bloom</th><th>Manifest</th><th>HTML</th></tr></thead>
        <tbody>{_study_rows(list(study.get('cards', [])) if isinstance(study.get('cards'), list) else [])}</tbody>
      </table>
    </section>

    <section>
      <h2>Decision, Gate, Loop</h2>
      <table>{_rows({
        'status': gates.get('status', ''),
        'decision_count': gates.get('decision_count', 0),
        'loop_run_count': gates.get('loop_run_count', 0),
        'human_gate_artifact_count': gates.get('human_gate_artifact_count', 0),
      })}</table>
    </section>

    <section>
      <h2>Latest Events</h2>
      <table>
        <thead><tr><th>Time</th><th>Type</th><th>Kind</th><th>Source</th><th>SHA-256</th></tr></thead>
        <tbody>{_latest_event_rows(list(event_summary.get('latest_events', [])) if isinstance(event_summary.get('latest_events'), list) else [])}</tbody>
      </table>
    </section>

    <section>
      <h2>Artifact Health</h2>
      <table>{_rows({
        'status': health.get('status', ''),
        'json_count': health.get('json_count', 0),
        'html_count': health.get('html_count', 0),
        'markdown_count': health.get('markdown_count', 0),
        'missing_event_source_count': health.get('missing_event_source_count', 0),
      })}</table>
    </section>

    <section>
      <h2>Redacted Manifest</h2>
      <pre>{json_blob}</pre>
    </section>
  </main>
</body>
</html>
"""


def cmd_build(args: argparse.Namespace) -> int:
    root = _root(args)
    html_ref = args.output or ".cognitive-loop/artifacts/console/index.html"
    manifest_ref = args.json_output or ".cognitive-loop/artifacts/console/manifest.json"
    html_path = _resolve_under_root(root, html_ref)
    manifest_path = _resolve_under_root(root, manifest_ref)
    db_path = _db_path(root, args.db)
    if args.rebuild_event_store:
        event_paths = [Path(path) for path in event_store._default_event_paths(root)]  # type: ignore[attr-defined]
        with event_store.connect(db_path) as connection:
            event_store.ingest_artifacts(connection, root, event_paths, clear_first=True)
    report = build_console_report(
        root=root,
        db_path=db_path,
        html_ref=_relative(root, html_path),
        manifest_ref=_relative(root, manifest_path),
        generated_at=args.generated_at,
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(dump_json(report), encoding="utf-8")
    wrote = [str(manifest_path)]
    if args.html:
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(render_console_html(report), encoding="utf-8")
        wrote.insert(0, str(html_path))
    if args.html and not args.json:
        for path in wrote:
            print(f"wrote: {path}")
        return 0
    print(dump_json(report), end="")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="Build the static HTML Artifact Console Lite.")
    build.add_argument("--root", default=".", help="Project root.")
    build.add_argument("--db", help="SQLite Event Store path.")
    build.add_argument("--html", action="store_true", help="Write the static HTML console.")
    build.add_argument("--json", action="store_true", help="Print JSON even when --html is used.")
    build.add_argument(
        "--output",
        default=".cognitive-loop/artifacts/console/index.html",
        help="HTML console output path.",
    )
    build.add_argument(
        "--json-output",
        default=".cognitive-loop/artifacts/console/manifest.json",
        help="JSON console manifest output path.",
    )
    build.add_argument(
        "--generated-at",
        default="2026-01-01T00:00:00Z",
        help="Deterministic timestamp for generated evidence.",
    )
    build.add_argument(
        "--rebuild-event-store",
        action="store_true",
        help="Rebuild the Event Store from .cognitive-loop/events before building.",
    )
    build.set_defaults(func=cmd_build)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except ArtifactConsoleError as exc:
        print(f"cognitive_loop_artifact_console failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
