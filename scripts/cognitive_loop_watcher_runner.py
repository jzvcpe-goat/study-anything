#!/usr/bin/env python3
"""One-shot Cognitive Loop watcher runner for metadata-only project events."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
from html import escape
import json
from pathlib import Path
import sys
import time
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "apps" / "api"))

import cognitive_loop_event_store as event_store  # noqa: E402
import cognitive_loop_study_adapter_cli as study_adapter_cli  # noqa: E402
import cognitive_loop_watcher_ingest as watcher_ingest  # noqa: E402


contracts = watcher_ingest.contracts

RUNNER_SCHEMA_VERSION = "cognitive-loop-watcher-runner-v1"

FORBIDDEN_TEXT = (
    "sk-proj-",
    "bearer ",
    "raw private source text",
    "learner answer:",
    "diff --git",
    "api_key",
    "agent endpoint:",
    "http://127.0.0.1:8787",
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
)


class WatcherRunnerError(RuntimeError):
    """Readable watcher runner failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _assert_no_forbidden_text(value: Any, *, label: str) -> None:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)
    lowered = text.lower()
    leaked = [needle for needle in FORBIDDEN_TEXT if needle.lower() in lowered]
    if leaked:
        raise WatcherRunnerError(f"{label} contains private-looking text: {leaked}")


def _root(args: argparse.Namespace) -> Path:
    return Path(args.root).resolve()


def _short_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _safe_target(raw: str) -> str:
    target = raw.strip().replace("\\", "/")
    if not target:
        raise WatcherRunnerError("watcher runner target is required.")
    if target.startswith("/") or target.startswith("../") or "/../" in target:
        raise WatcherRunnerError(f"watcher runner target must be repo-relative or symbolic: {raw}")
    contracts._assert_public_value("watcher_runner_target", target)  # type: ignore[attr-defined]
    _assert_no_forbidden_text(target, label="watcher runner target")
    return target


def _safe_summary(raw: str, *, label: str) -> str:
    summary = " ".join(raw.strip().split())
    if not summary:
        raise WatcherRunnerError(f"{label} summary is required.")
    if len(summary) > 180:
        summary = summary[:177] + "..."
    contracts._assert_public_value(label, summary)  # type: ignore[attr-defined]
    _assert_no_forbidden_text(summary, label=label)
    return summary


def _match_any(patterns: list[str], target: str) -> bool:
    if not patterns:
        return True
    return any(fnmatch.fnmatchcase(target, pattern) for pattern in patterns)


def _watchers_by_kind(config: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    watchers: dict[str, dict[str, Any]] = {}
    for item in config.get("watchers", []):
        if isinstance(item, Mapping) and item.get("enabled") is True:
            watchers[str(item.get("kind"))] = dict(item)
    return watchers


def _is_allowed(watcher: Mapping[str, Any], target: str) -> bool:
    include = [str(item) for item in watcher.get("include", []) if isinstance(item, str)]
    exclude = [str(item) for item in watcher.get("exclude", []) if isinstance(item, str)]
    return _match_any(include, target) and not _match_any(exclude, target)


def _observation_key(observation: Mapping[str, Any]) -> str:
    refs = observation.get("refs", [])
    ref_text = "|".join(str(item) for item in refs if isinstance(item, str))
    return "|".join(
        [
            str(observation.get("watcher_id", "")),
            str(observation.get("event_type", "")),
            str(observation.get("target", "")),
            ref_text,
        ]
    )


def _build_observations(
    config: Mapping[str, Any],
    *,
    changed_paths: list[str],
    git_diff_summary: str | None,
    test_failure_summary: str | None,
) -> tuple[list[dict[str, Any]], list[dict[str, str]], int]:
    watchers = _watchers_by_kind(config)
    observations: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    raw_count = 0

    def add(kind: str, target: str, summary: str, refs: list[str]) -> None:
        nonlocal raw_count
        raw_count += 1
        watcher = watchers.get(kind)
        if watcher is None:
            skipped.append({"target": target, "reason": f"no enabled watcher for {kind}"})
            return
        if not _is_allowed(watcher, target):
            skipped.append({"target": target, "reason": f"excluded by watcher {watcher['id']}"})
            return
        observations.append(
            {
                "watcher_id": watcher["id"],
                "kind": kind,
                "event_type": watcher["eventType"],
                "target": target,
                "summary": summary,
                "refs": refs,
                "high_risk": kind in {"git_diff", "test"} or target.startswith(("apps/", "scripts/")),
            }
        )

    for raw_path in changed_paths:
        target = _safe_target(raw_path)
        add(
            "file",
            target,
            f"Saved file path changed: {target}",
            [f"path:{target}", "watcher-runner:file-save"],
        )

    if git_diff_summary:
        summary = _safe_summary(git_diff_summary, label="git_diff_summary")
        add(
            "git_diff",
            "git/working-tree",
            f"Git diff summary observed: {summary}",
            ["git:working-tree", f"git-diff-summary:{_short_hash(summary)}"],
        )

    if test_failure_summary:
        summary = _safe_summary(test_failure_summary, label="test_failure_summary")
        add(
            "test",
            "tests/result",
            f"Test failure summary observed: {summary}",
            ["test:failure-summary", f"test-summary:{_short_hash(summary)}"],
        )

    deduped: dict[str, dict[str, Any]] = {}
    for observation in observations:
        deduped.setdefault(_observation_key(observation), observation)
    return list(deduped.values()), skipped, raw_count


def _write_text(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


def _relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def _study_decision_for_event(event: Mapping[str, Any], *, generated_at: str) -> dict[str, Any]:
    event_id = str(event["event_id"])
    project_id = str(event["project_id"])
    target = str(event.get("target") or "project")
    return contracts.validate_decision_card(
        {
            "decision_id": f"decision-watcher-runner-{_short_hash(event_id)}",
            "project_id": project_id,
            "title": "Route high-risk watcher event through Study Anything",
            "status": "approved",
            "summary": (
                "Use the Study Anything adapter CLI as a learning gate for this high-risk "
                "watcher event before accepting the project change."
            ),
            "event_ids": [event_id],
            "evidence_refs": [
                f"event:{event_id}",
                f"path:{target}",
                "check:.venv/bin/python scripts/cognitive_loop_watcher_runner.py run --study-adapter",
                "check:.venv/bin/python scripts/verify_cognitive_loop_watcher_runner.py --check",
            ],
            "risk": {
                "level": "high",
                "score": 0.82,
                "reasons": [
                    "Watcher event touches a project boundary that should be explained before acceptance.",
                    "Learning gate must prove the operator understands risk, verification, and rollback.",
                ],
            },
            "human_mastery_gate": {
                "required": True,
                "status": "approved",
                "reason": "High-risk watcher events require source-bound operator understanding.",
            },
            "verification": {
                "status": "passed",
                "commands": [
                    ".venv/bin/python scripts/cognitive_loop_watcher_runner.py run --study-adapter",
                    ".venv/bin/python scripts/verify_cognitive_loop_watcher_runner.py --check",
                ],
            },
            "rollback": {"strategy": "disable_watcher_runner_study_gate", "checkpoint_ref": "git"},
        }
    ).public_dict()


def _run_study_adapter_gate(
    root: Path,
    *,
    artifact: Mapping[str, Any],
    generated_at: str,
    html: bool,
) -> dict[str, Any]:
    event = artifact.get("project_event")
    if not isinstance(event, Mapping):
        raise WatcherRunnerError("high-risk watcher artifact lacks project_event metadata.")
    base = f"watcher-runner-study-{_short_hash(str(event['event_id']))}"
    event_path = root / ".cognitive-loop" / "events" / f"{base}-project-event.json"
    decision_path = root / ".cognitive-loop" / "events" / f"{base}-decision-card.json"
    json_path = root / ".cognitive-loop" / "events" / f"{base}.json"
    html_path = root / ".cognitive-loop" / "artifacts" / f"{base}.html"
    _write_text(event_path, dump_json(dict(event)))
    decision = _study_decision_for_event(event, generated_at=generated_at)
    _write_text(decision_path, dump_json(decision))
    report = study_adapter_cli.build_study_adapter_cli_report(
        root=root,
        event_path=event_path,
        decision_path=decision_path,
        generated_at=generated_at,
        objective="Run a Study Anything learning gate for a high-risk watcher runner event.",
        json_ref=_relative(root, json_path),
        html_ref=_relative(root, html_path),
    )
    _write_text(json_path, dump_json(report))
    wrote = [_relative(root, event_path), _relative(root, decision_path), _relative(root, json_path)]
    if html:
        _write_text(html_path, study_adapter_cli.render_study_adapter_cli_html(report))
        wrote.append(_relative(root, html_path))
    return {
        "triggered": True,
        "event_id": str(event["event_id"]),
        "decision_id": decision["decision_id"],
        "schema_version": report["schema_version"],
        "status": report["status"],
        "wrote": wrote,
        "uses_fake_agent": True,
        "external_agent_called": False,
        "content_included": False,
    }


def build_watcher_runner_report(
    root: Path,
    *,
    changed_paths: list[str],
    git_diff_summary: str | None,
    test_failure_summary: str | None,
    generated_at: str,
    html: bool,
    study_adapter: bool,
    poll_cycles: int,
) -> dict[str, Any]:
    if poll_cycles < 1 or poll_cycles > 3:
        raise WatcherRunnerError("poll-cycles must be between 1 and 3 for runner-lite.")
    config = watcher_ingest._load_config(root)  # type: ignore[attr-defined]
    observations: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    raw_count = 0
    for _ in range(poll_cycles):
        cycle_observations, cycle_skipped, cycle_count = _build_observations(
            config,
            changed_paths=changed_paths,
            git_diff_summary=git_diff_summary,
            test_failure_summary=test_failure_summary,
        )
        observations.extend(cycle_observations)
        skipped.extend(cycle_skipped)
        raw_count += cycle_count
    deduped: dict[str, dict[str, Any]] = {}
    for observation in observations:
        deduped.setdefault(_observation_key(observation), observation)
    final_observations = list(deduped.values())

    event_paths: list[Path] = []
    events_written: list[dict[str, Any]] = []
    high_risk_artifact: dict[str, Any] | None = None
    for observation in final_observations:
        artifact_ref = (
            ".cognitive-loop/artifacts/"
            f"watcher-runner-{_short_hash(_observation_key(observation))}.html"
        )
        artifact = watcher_ingest.build_watcher_ingest_artifact(
            root,
            watcher_id=str(observation["watcher_id"]),
            target=str(observation["target"]),
            summary=str(observation["summary"]),
            refs=list(observation["refs"]),
            artifact_ref=artifact_ref,
            generated_at=generated_at,
        )
        event = artifact["project_event"]
        json_path = root / ".cognitive-loop" / "events" / f"watcher-runner-{event['event_id']}.json"
        _write_text(json_path, dump_json(artifact))
        if html:
            html_path = root / artifact_ref
            _write_text(html_path, contracts.render_cli_artifact_html(artifact))
        event_paths.append(json_path)
        events_written.append(
            {
                "event_id": event["event_id"],
                "event_type": event["event_type"],
                "target": event.get("target"),
                "artifact_path": _relative(root, json_path),
                "artifact_sha256": hashlib.sha256(json_path.read_bytes()).hexdigest(),
                "high_risk": bool(observation["high_risk"]),
            }
        )
        if observation["high_risk"] and high_risk_artifact is None:
            high_risk_artifact = artifact

    db_path = root / ".cognitive-loop" / "cognitive-loop-events.sqlite"
    with event_store.connect(db_path) as connection:
        ingest_result = event_store.ingest_artifacts(connection, root, event_paths, clear_first=False)
        stored_events = event_store.list_events(connection)

    study_adapter_gate = {"triggered": False, "reason": "no high-risk event or disabled"}
    if study_adapter and high_risk_artifact is not None:
        study_adapter_gate = _run_study_adapter_gate(
            root,
            artifact=high_risk_artifact,
            generated_at=generated_at,
            html=html,
        )

    report = {
        "schema_version": RUNNER_SCHEMA_VERSION,
        "status": "pass",
        "generated_at": generated_at,
        "title": "Cognitive Loop Watcher Runner Lite",
        "objective": "Batch local watcher signals into metadata-only ProjectEvents and Event Store rows.",
        "mode": {
            "runner": "one_shot_polling_lite",
            "poll_cycles": poll_cycles,
            "daemon_started": False,
            "background_service": False,
        },
        "watcher_config": {
            "schema_version": config["schemaVersion"],
            "mode": config["mode"],
            "watcher_count": len(config["watchers"]),
            "debounce_ms": config["defaults"]["debounceMs"],
            "content_mode": config["defaults"]["contentMode"],
            "daemon": config["daemon"],
        },
        "observations": {
            "raw_count": raw_count,
            "deduped_count": len(final_observations),
            "duplicate_count": max(raw_count - len(final_observations) - len(skipped), 0),
            "skipped_count": len(skipped),
            "skipped": skipped,
        },
        "events_written": events_written,
        "event_store": {
            "schema_version": event_store.STORE_SCHEMA_VERSION,
            "db_path": _relative(root, db_path),
            "event_count": ingest_result["event_count"],
            "artifact_count": ingest_result["artifact_count"],
            "ingested_paths": ingest_result["ingested_paths"],
            "idempotent_by_event_id": True,
            "stored_event_ids": [item["event_id"] for item in stored_events],
        },
        "study_adapter_gate": study_adapter_gate,
        "privacy": {
            "metadata_only": True,
            "raw_source_text_included": False,
            "raw_diff_included": False,
            "diff_body_included": False,
            "file_contents_included": False,
            "test_output_included": False,
            "learner_answers_included": False,
            "agent_endpoints_included": False,
            "agent_metadata_included": False,
            "model_keys_included": False,
            "watcher_daemon_started": False,
            "background_service_started": False,
        },
        "current_limits": [
            "Runner Lite processes explicit local signals only; it is not a filesystem daemon.",
            "Polling is bounded to at most three cycles and is intended for local operator use.",
            "Realtime HTML console and platform-driven watcher service remain later layers.",
        ],
        "commands": {
            "run": ".venv/bin/python scripts/cognitive_loop_watcher_runner.py run --html",
            "verify": ".venv/bin/python scripts/verify_cognitive_loop_watcher_runner.py --check",
            "event_store": ".venv/bin/python scripts/cognitive_loop_event_store.py rebuild",
            "study_adapter_gate": ".venv/bin/python scripts/cognitive_loop_cli.py study-adapter --html",
            "release_check": "./scripts/release_check.sh",
        },
    }
    contracts._assert_public_value("watcher_runner_report", report)  # type: ignore[attr-defined]
    _assert_no_forbidden_text(report, label="watcher runner report")
    return report


def render_runner_html(report: Mapping[str, Any]) -> str:
    _assert_no_forbidden_text(report, label="watcher runner HTML")
    events = report.get("events_written") if isinstance(report.get("events_written"), list) else []
    rows = "\n".join(
        "<tr>"
        f"<td>{escape(str(item.get('event_type', '')))}</td>"
        f"<td>{escape(str(item.get('target', '')))}</td>"
        f"<td>{escape(str(item.get('artifact_path', '')))}</td>"
        f"<td>{escape(str(item.get('high_risk', False)))}</td>"
        "</tr>"
        for item in events
        if isinstance(item, Mapping)
    )
    observations = report.get("observations") if isinstance(report.get("observations"), Mapping) else {}
    event_store_report = report.get("event_store") if isinstance(report.get("event_store"), Mapping) else {}
    study_gate = report.get("study_adapter_gate") if isinstance(report.get("study_adapter_gate"), Mapping) else {}
    json_blob = escape(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Cognitive Loop Watcher Runner Lite</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #182019;
      --muted: #5e6c5f;
      --paper: #faf8f1;
      --wash: #edf5e8;
      --line: #d9e1d4;
      --accent: #245f3b;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Georgia, 'Times New Roman', serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(36, 95, 59, 0.16), transparent 32rem),
        linear-gradient(135deg, var(--paper), var(--wash));
      line-height: 1.5;
    }}
    main {{ width: min(1040px, calc(100% - 32px)); margin: 0 auto; padding: 56px 0; }}
    h1 {{ font-size: clamp(40px, 7vw, 80px); line-height: 0.95; margin: 0 0 16px; letter-spacing: 0; }}
    .summary {{ max-width: 760px; color: var(--muted); font-size: 20px; }}
    section {{ border-top: 1px solid var(--line); padding: 28px 0; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 16px; }}
    .metric {{ border-left: 3px solid var(--accent); padding-left: 12px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 10px 8px; text-align: left; vertical-align: top; }}
    code, pre {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 13px; }}
    pre {{ overflow: auto; max-height: 420px; padding: 16px; background: rgba(255,255,255,.55); border: 1px solid var(--line); }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Cognitive Loop System</h1>
      <p class="summary">Watcher Runner Lite: bounded local polling that writes metadata-only project events.</p>
    </header>
    <section>
      <h2>Run Status</h2>
      <div class="grid">
        <div class="metric">Status<br><strong>{escape(str(report.get('status', '')))}</strong></div>
        <div class="metric">Deduped observations<br><strong>{escape(str(observations.get('deduped_count', 0)))}</strong></div>
        <div class="metric">Skipped<br><strong>{escape(str(observations.get('skipped_count', 0)))}</strong></div>
        <div class="metric">Event Store rows<br><strong>{escape(str(event_store_report.get('event_count', 0)))}</strong></div>
        <div class="metric">Study gate<br><strong>{escape(str(study_gate.get('triggered', False)))}</strong></div>
      </div>
    </section>
    <section>
      <h2>Events Written</h2>
      <table>
        <thead><tr><th>Type</th><th>Target</th><th>Artifact</th><th>High risk</th></tr></thead>
        <tbody>{rows}</tbody>
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


def cmd_run(args: argparse.Namespace) -> int:
    root = _root(args)
    generated_at = args.generated_at or contracts._utc_now()  # type: ignore[attr-defined]
    if args.poll_interval_ms:
        interval = max(0, min(int(args.poll_interval_ms), 2000)) / 1000
        if interval:
            time.sleep(interval)
    report = build_watcher_runner_report(
        root,
        changed_paths=list(args.changed_path or []),
        git_diff_summary=args.git_diff_summary,
        test_failure_summary=args.test_failure_summary,
        generated_at=generated_at,
        html=args.html,
        study_adapter=args.study_adapter,
        poll_cycles=int(args.poll_cycles),
    )
    if not report["events_written"]:
        raise WatcherRunnerError("No watcher observations were accepted by config.")

    json_path = Path(args.json_output or ".cognitive-loop/events/cognitive-loop-watcher-runner.json")
    if not json_path.is_absolute():
        json_path = root / json_path
    _write_text(json_path, dump_json(report))
    wrote = [str(json_path)]
    if args.html:
        html_path = Path(args.output or ".cognitive-loop/artifacts/cognitive-loop-watcher-runner.html")
        if not html_path.is_absolute():
            html_path = root / html_path
        _write_text(html_path, render_runner_html(report))
        wrote.append(str(html_path))
    if args.html and not args.json:
        for path in wrote:
            print(f"wrote: {path}")
        return 0
    print(dump_json(report), end="")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository or project root.")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run one bounded watcher polling pass.")
    run.add_argument("--html", action="store_true", help="Write a static HTML artifact.")
    run.add_argument("--json", action="store_true", help="Print JSON even when --html is used.")
    run.add_argument("--output", default=".cognitive-loop/artifacts/cognitive-loop-watcher-runner.html")
    run.add_argument("--json-output", default=".cognitive-loop/events/cognitive-loop-watcher-runner.json")
    run.add_argument("--changed-path", action="append", help="Repo-relative changed path. May repeat.")
    run.add_argument("--git-diff-summary", help="Public metadata summary, never a raw diff body.")
    run.add_argument("--test-failure-summary", help="Public metadata summary, never raw test output.")
    run.add_argument("--study-adapter", action="store_true", help="Trigger Study Anything for high-risk events.")
    run.add_argument("--generated-at", help="Deterministic timestamp for verifiers.")
    run.add_argument("--poll-cycles", type=int, default=1, help="Bounded polling cycles, 1..3.")
    run.add_argument("--poll-interval-ms", type=int, default=0, help="Optional bounded local wait before running.")
    run.set_defaults(func=cmd_run)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except contracts.CognitiveLoopContractError as exc:
        raise SystemExit(f"cognitive-loop-watcher-runner: {exc}") from exc
    except WatcherRunnerError as exc:
        raise SystemExit(f"cognitive-loop-watcher-runner: {exc}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
