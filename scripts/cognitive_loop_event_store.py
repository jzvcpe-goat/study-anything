#!/usr/bin/env python3
"""Local SQLite Event Store for Cognitive Loop metadata artifacts."""

from __future__ import annotations

import argparse
import hashlib
from html import escape
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_MODULE_PATH = (
    ROOT / "apps" / "api" / "study_anything" / "core" / "cognitive_loop_contracts.py"
)
STORE_SCHEMA_VERSION = "cognitive-loop-event-store-v1"
EXPORT_SCHEMA_VERSION = "cognitive-loop-event-store-export-v1"
LIST_SCHEMA_VERSION = "cognitive-loop-event-store-list-v1"


class EventStoreError(RuntimeError):
    """Readable Event Store CLI failure."""


def _load_contract_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "study_anything_cognitive_loop_contracts", CONTRACT_MODULE_PATH
    )
    if spec is None or spec.loader is None:
        raise EventStoreError(f"Cannot load Cognitive Loop module: {CONTRACT_MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


contracts = _load_contract_module()


FORBIDDEN_TEXT = (
    "sk-proj-",
    "bearer ",
    "raw private source text",
    "learner answer:",
    "diff --git",
    "api_key",
    "agent endpoint:",
    "http://127.0.0.1:8787",
)


def _root(args: argparse.Namespace) -> Path:
    return Path(args.root).resolve()


def _db_path(root: Path, raw_path: str | None) -> Path:
    value = raw_path or ".cognitive-loop/cognitive-loop-events.sqlite"
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def _relative_to_root(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def _dump(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _assert_no_forbidden_text(value: Any, *, label: str) -> None:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True) if not isinstance(value, str) else value
    lowered = text.lower()
    leaked = [needle for needle in FORBIDDEN_TEXT if needle.lower() in lowered]
    if leaked:
        raise EventStoreError(f"{label} contains private-looking text: {leaked}")


def _safe_event_path(root: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    try:
        relative = path.relative_to(root.resolve())
    except ValueError as exc:
        raise EventStoreError(f"Event path must stay under the project root: {raw_path}") from exc
    if ".." in relative.parts:
        raise EventStoreError(f"Event path cannot traverse outside the project root: {raw_path}")
    if path.suffix != ".json":
        raise EventStoreError(f"Event Store only ingests JSON event artifacts: {raw_path}")
    if not path.is_file():
        raise EventStoreError(f"Event artifact is missing: {raw_path}")
    return path


def _default_event_paths(root: Path) -> list[Path]:
    directory = root / ".cognitive-loop" / "events"
    if not directory.is_dir():
        return []
    ignored = {
        "cognitive-loop-event-store-export.json",
    }
    return [
        path
        for path in sorted(directory.glob("*.json"))
        if path.name not in ignored and path.suffix == ".json"
    ]


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path))
    connection.row_factory = sqlite3.Row
    return connection


def initialize(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS meta (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS events (
          event_id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL,
          actor TEXT NOT NULL,
          event_type TEXT NOT NULL,
          summary TEXT NOT NULL,
          timestamp TEXT NOT NULL,
          target TEXT,
          refs_json TEXT NOT NULL,
          sensitivity TEXT NOT NULL,
          source_path TEXT NOT NULL,
          artifact_kind TEXT NOT NULL,
          artifact_schema_version TEXT NOT NULL,
          artifact_status TEXT NOT NULL,
          artifact_sha256 TEXT NOT NULL,
          metadata_json TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS artifacts (
          source_path TEXT PRIMARY KEY,
          artifact_kind TEXT NOT NULL,
          schema_version TEXT NOT NULL,
          status TEXT NOT NULL,
          size_bytes INTEGER NOT NULL,
          sha256 TEXT NOT NULL,
          content_included INTEGER NOT NULL DEFAULT 0,
          ingested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    connection.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)",
        ("schema_version", STORE_SCHEMA_VERSION),
    )
    connection.commit()


def _artifact_kind(schema_version: str) -> str:
    if schema_version.startswith("cognitive-loop-run-once"):
        return "run_once"
    if schema_version.startswith("cognitive-loop-project-snapshot"):
        return "project_snapshot"
    if schema_version.startswith("cognitive-loop-watcher-ingest"):
        return "watcher_ingest"
    if schema_version.startswith("cognitive-loop-human-gate"):
        return "human_gate"
    if schema_version.startswith("cognitive-loop-evidence-bundle"):
        return "evidence_bundle"
    if schema_version.startswith("cognitive-loop-event-index"):
        return "event_index"
    if schema_version.startswith("cognitive-loop-artifact"):
        return "artifact"
    return "cognitive_loop_artifact"


def _load_event_artifact(root: Path, path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    try:
        artifact = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EventStoreError(f"Event artifact is not valid JSON: {_relative_to_root(root, path)}") from exc
    if not isinstance(artifact, Mapping):
        raise EventStoreError(f"Event artifact must be a JSON object: {_relative_to_root(root, path)}")
    _assert_no_forbidden_text(artifact, label=_relative_to_root(root, path))
    if "project_event" not in artifact or not isinstance(artifact["project_event"], Mapping):
        raise EventStoreError(f"Event artifact lacks project_event metadata: {_relative_to_root(root, path)}")
    project_event = contracts.validate_project_event(artifact["project_event"]).public_dict()
    schema_version = str(artifact.get("schema_version", "unknown"))
    status = str(artifact.get("status", "unknown"))
    relative_path = _relative_to_root(root, path)
    digest = hashlib.sha256(data).hexdigest()
    metadata = {
        "schema_version": schema_version,
        "status": status,
        "source_path": relative_path,
        "artifact_kind": _artifact_kind(schema_version),
        "artifact_sha256": digest,
        "content_included": False,
    }
    if isinstance(artifact.get("decision_card"), Mapping):
        decision = artifact["decision_card"]
        metadata["decision_id"] = str(decision.get("decision_id", ""))
        metadata["decision_status"] = str(decision.get("status", ""))
    if isinstance(artifact.get("loop_run"), Mapping):
        loop = artifact["loop_run"]
        metadata["loop_run_id"] = str(loop.get("run_id", ""))
        metadata["loop_status"] = str(loop.get("status", ""))
    _assert_no_forbidden_text(metadata, label=f"metadata:{relative_path}")
    return {
        "project_event": project_event,
        "metadata": metadata,
        "schema_version": schema_version,
        "status": status,
        "relative_path": relative_path,
        "sha256": digest,
        "size_bytes": len(data),
        "artifact_kind": metadata["artifact_kind"],
    }


def ingest_artifacts(
    connection: sqlite3.Connection,
    root: Path,
    paths: Iterable[Path],
    *,
    clear_first: bool = False,
) -> dict[str, Any]:
    initialize(connection)
    if clear_first:
        connection.execute("DELETE FROM events")
        connection.execute("DELETE FROM artifacts")
    inserted_paths: list[str] = []
    try:
        for path in paths:
            payload = _load_event_artifact(root, path)
            event = payload["project_event"]
            metadata = payload["metadata"]
            existing = connection.execute(
                "SELECT source_path, artifact_sha256 FROM events WHERE event_id = ?",
                (event["event_id"],),
            ).fetchone()
            if existing is not None and (
                existing["source_path"] != payload["relative_path"]
                or existing["artifact_sha256"] != payload["sha256"]
            ):
                raise EventStoreError(
                    f"Conflicting event_id '{event['event_id']}' is already bound to "
                    f"{existing['source_path']}."
                )
            connection.execute(
                """
                INSERT OR REPLACE INTO artifacts(
                  source_path, artifact_kind, schema_version, status, size_bytes, sha256,
                  content_included
                )
                VALUES(?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    payload["relative_path"],
                    payload["artifact_kind"],
                    payload["schema_version"],
                    payload["status"],
                    payload["size_bytes"],
                    payload["sha256"],
                ),
            )
            connection.execute(
                """
                INSERT OR REPLACE INTO events(
                  event_id, project_id, actor, event_type, summary, timestamp, target, refs_json,
                  sensitivity, source_path, artifact_kind, artifact_schema_version, artifact_status,
                  artifact_sha256, metadata_json
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event["event_id"],
                    event["project_id"],
                    event["actor"],
                    event["event_type"],
                    event["summary"],
                    event["timestamp"],
                    event.get("target"),
                    json.dumps(event.get("refs", []), ensure_ascii=False, sort_keys=True),
                    event["sensitivity"],
                    payload["relative_path"],
                    payload["artifact_kind"],
                    payload["schema_version"],
                    payload["status"],
                    payload["sha256"],
                    json.dumps(metadata, ensure_ascii=False, sort_keys=True),
                ),
            )
            inserted_paths.append(payload["relative_path"])
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return {
        "ingested_paths": inserted_paths,
        "event_count": count_rows(connection, "events"),
        "artifact_count": count_rows(connection, "artifacts"),
    }


def count_rows(connection: sqlite3.Connection, table: str) -> int:
    row = connection.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()
    return int(row["count"])


def list_events(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT event_id, project_id, actor, event_type, summary, timestamp, target, refs_json,
               sensitivity, source_path, artifact_kind, artifact_schema_version,
               artifact_status, artifact_sha256, metadata_json
        FROM events
        ORDER BY timestamp ASC, source_path ASC
        """
    ).fetchall()
    events: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["refs"] = json.loads(str(item.pop("refs_json")))
        item["metadata"] = json.loads(str(item.pop("metadata_json")))
        events.append(item)
    return events


def build_export_report(root: Path, db_path: Path, connection: sqlite3.Connection) -> dict[str, Any]:
    initialize(connection)
    events = list_events(connection)
    report = {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "status": "ready",
        "title": "Cognitive Loop SQLite Event Store",
        "project_root": "local",
        "event_store": {
            "schema_version": STORE_SCHEMA_VERSION,
            "engine": "sqlite",
            "db_path": _relative_to_root(root, db_path),
            "event_count": len(events),
            "artifact_count": count_rows(connection, "artifacts"),
            "content_included": False,
            "events": events,
        },
        "privacy": {
            "metadata_only": True,
            "artifact_contents_included": False,
            "event_contents_included": False,
            "diff_body_included": False,
            "file_contents_included": False,
            "raw_source_text_included": False,
            "learner_answers_included": False,
            "agent_endpoints_included": False,
            "agent_metadata_included": False,
            "real_model_keys_stored": False,
            "watcher_daemon_started": False,
            "mastra_runtime_started": False,
        },
        "current_limits": [
            "This is a local SQLite metadata store, not a watcher daemon.",
            "It ingests validated Cognitive Loop event artifacts and stores event metadata only.",
            "It rejects private-looking text before committing rows.",
        ],
        "commands": {
            "init": "python3 scripts/cognitive_loop_event_store.py init",
            "rebuild": "python3 scripts/cognitive_loop_event_store.py rebuild",
            "export": "python3 scripts/cognitive_loop_event_store.py export --html",
            "check": "python3 scripts/verify_cognitive_loop_event_store.py --check",
        },
    }
    contracts._assert_public_value("event_store_export", report)  # type: ignore[attr-defined]
    return report


def render_event_store_html(report: Mapping[str, Any]) -> str:
    event_store = report.get("event_store")
    if not isinstance(event_store, Mapping):
        event_store = {}
    events = event_store.get("events")
    if not isinstance(events, list):
        events = []
    rows = "\n".join(
        "<tr>"
        f"<td>{escape(str(item.get('timestamp', '')))}</td>"
        f"<td>{escape(str(item.get('event_type', '')))}</td>"
        f"<td>{escape(str(item.get('source_path', '')))}</td>"
        f"<td>{escape(str(item.get('artifact_kind', '')))}</td>"
        f"<td><code>{escape(str(item.get('artifact_sha256', ''))[:16])}</code></td>"
        "</tr>"
        for item in events
        if isinstance(item, Mapping)
    )
    json_blob = escape(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Cognitive Loop SQLite Event Store</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #182019;
      --muted: #5f6d61;
      --line: #dbe3d5;
      --paper: #faf8f1;
      --wash: #eef5e7;
      --accent: #245f3b;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Georgia, 'Times New Roman', serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(36, 95, 59, 0.14), transparent 32rem),
        linear-gradient(135deg, var(--paper), var(--wash));
      line-height: 1.5;
    }}
    main {{
      width: min(980px, calc(100% - 32px));
      margin: 0 auto;
      padding: 56px 0;
    }}
    h1 {{
      font-size: clamp(42px, 7vw, 82px);
      line-height: 0.95;
      letter-spacing: 0;
      margin: 0 0 18px;
    }}
    .summary {{
      max-width: 760px;
      font-size: 20px;
      color: var(--muted);
      margin: 0;
    }}
    section {{
      border-top: 1px solid var(--line);
      padding: 28px 0;
    }}
    .status {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 16px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 14px;
    }}
    .status div {{
      border-left: 3px solid var(--accent);
      padding-left: 12px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 15px;
    }}
    th, td {{
      text-align: left;
      border-bottom: 1px solid var(--line);
      padding: 10px 8px;
      vertical-align: top;
    }}
    code, pre {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 13px;
    }}
    pre {{
      overflow: auto;
      max-height: 420px;
      padding: 16px;
      background: rgba(255, 255, 255, 0.52);
      border: 1px solid var(--line);
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Cognitive Loop System</h1>
      <p class="summary">SQLite Event Store: local metadata memory for validated Cognitive Loop artifacts.</p>
    </header>
    <section>
      <h2>SQLite Event Store</h2>
      <div class="status">
        <div>Status<br><strong>{escape(str(report.get('status', '')))}</strong></div>
        <div>Schema<br><strong>{escape(str(event_store.get('schema_version', '')))}</strong></div>
        <div>Events<br><strong>{escape(str(event_store.get('event_count', 0)))}</strong></div>
        <div>Artifacts<br><strong>{escape(str(event_store.get('artifact_count', 0)))}</strong></div>
      </div>
    </section>
    <section>
      <h2>Event Metadata</h2>
      <table>
        <thead><tr><th>Time</th><th>Type</th><th>Source</th><th>Kind</th><th>SHA-256</th></tr></thead>
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


def _event_paths_from_args(root: Path, raw_paths: list[str] | None) -> list[Path]:
    if raw_paths:
        return [_safe_event_path(root, raw_path) for raw_path in raw_paths]
    return _default_event_paths(root)


def cmd_init(args: argparse.Namespace) -> int:
    root = _root(args)
    path = _db_path(root, args.db)
    with connect(path) as connection:
        initialize(connection)
        payload = {
            "schema_version": STORE_SCHEMA_VERSION,
            "status": "ready",
            "event_store": {
                "engine": "sqlite",
                "db_path": _relative_to_root(root, path),
                "event_count": count_rows(connection, "events"),
                "artifact_count": count_rows(connection, "artifacts"),
                "content_included": False,
            },
        }
    print(_dump(payload), end="")
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    root = _root(args)
    path = _db_path(root, args.db)
    event_paths = _event_paths_from_args(root, args.event)
    with connect(path) as connection:
        result = ingest_artifacts(connection, root, event_paths, clear_first=False)
    payload = {
        "schema_version": STORE_SCHEMA_VERSION,
        "status": "ready",
        "mode": "ingest",
        "event_store": {
            "engine": "sqlite",
            "db_path": _relative_to_root(root, path),
            "event_count": result["event_count"],
            "artifact_count": result["artifact_count"],
            "ingested_paths": result["ingested_paths"],
            "content_included": False,
        },
    }
    print(_dump(payload), end="")
    return 0


def cmd_rebuild(args: argparse.Namespace) -> int:
    root = _root(args)
    path = _db_path(root, args.db)
    event_paths = _event_paths_from_args(root, args.event)
    with connect(path) as connection:
        result = ingest_artifacts(connection, root, event_paths, clear_first=True)
    payload = {
        "schema_version": STORE_SCHEMA_VERSION,
        "status": "ready",
        "mode": "rebuild",
        "event_store": {
            "engine": "sqlite",
            "db_path": _relative_to_root(root, path),
            "event_count": result["event_count"],
            "artifact_count": result["artifact_count"],
            "ingested_paths": result["ingested_paths"],
            "content_included": False,
        },
    }
    print(_dump(payload), end="")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    root = _root(args)
    path = _db_path(root, args.db)
    with connect(path) as connection:
        initialize(connection)
        payload = {
            "schema_version": LIST_SCHEMA_VERSION,
            "status": "ready",
            "event_store": {
                "engine": "sqlite",
                "db_path": _relative_to_root(root, path),
                "event_count": count_rows(connection, "events"),
                "artifact_count": count_rows(connection, "artifacts"),
                "content_included": False,
                "events": list_events(connection),
            },
        }
    print(_dump(payload), end="")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    root = _root(args)
    path = _db_path(root, args.db)
    with connect(path) as connection:
        report = build_export_report(root, path, connection)

    wrote: list[str] = []
    if args.html:
        output = Path(args.output)
        if not output.is_absolute():
            output = root / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(render_event_store_html(report), encoding="utf-8")
        wrote.append(str(output))
    if args.json_output:
        json_output = Path(args.json_output)
        if not json_output.is_absolute():
            json_output = root / json_output
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(_dump(report), encoding="utf-8")
        wrote.append(str(json_output))
    if args.html and not args.json:
        for path_item in wrote:
            print(f"wrote: {path_item}")
        return 0
    print(_dump(report), end="")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository or project root.")
    parser.add_argument("--db", help="SQLite database path. Defaults under .cognitive-loop.")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Create the local SQLite Event Store schema.")
    init.set_defaults(func=cmd_init)

    ingest = sub.add_parser("ingest", help="Ingest validated Cognitive Loop JSON event artifacts.")
    ingest.add_argument("--event", action="append", help="Repo-relative event JSON path. May be repeated.")
    ingest.set_defaults(func=cmd_ingest)

    rebuild = sub.add_parser("rebuild", help="Clear and rebuild the Event Store from JSON event artifacts.")
    rebuild.add_argument("--event", action="append", help="Repo-relative event JSON path. May be repeated.")
    rebuild.set_defaults(func=cmd_rebuild)

    list_cmd = sub.add_parser("list", help="List metadata rows from the Event Store.")
    list_cmd.set_defaults(func=cmd_list)

    export = sub.add_parser("export", help="Export a metadata-only HTML/JSON Event Store report.")
    export.add_argument("--html", action="store_true", help="Write a static HTML report.")
    export.add_argument(
        "--output",
        default=".cognitive-loop/artifacts/cognitive-loop-event-store.html",
        help="HTML output path. Defaults under .cognitive-loop/artifacts.",
    )
    export.add_argument(
        "--json-output",
        default=".cognitive-loop/events/cognitive-loop-event-store-export.json",
        help="JSON output path. Defaults under .cognitive-loop/events.",
    )
    export.add_argument("--json", action="store_true", help="Print JSON even when --html is used.")
    export.set_defaults(func=cmd_export)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except contracts.CognitiveLoopContractError as exc:
        raise SystemExit(f"cognitive-loop-event-store: {exc}") from exc
    except EventStoreError as exc:
        raise SystemExit(f"cognitive-loop-event-store: {exc}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
