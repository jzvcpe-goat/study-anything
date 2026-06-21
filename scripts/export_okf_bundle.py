#!/usr/bin/env python3
"""Export a learning session as an OKF-style Markdown knowledge bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SESSION = ROOT / "platform" / "okf" / "examples" / "demo-session.json"
DEFAULT_OUTPUT = ROOT / "platform" / "okf" / "examples" / "demo-okf-bundle"
BUNDLE_SCHEMA = "cognitive-black-box-okf-bundle-v1"
NOTE_SCHEMA = "cognitive-black-box-okf-note-v1"
GENERATED_AT = "2026-01-01T00:00:00Z"
CONSUMERS = ["kimi", "codex", "obsidian", "notebooklm", "generic-platform-agent"]
SAFE_AGENT_KEYS = {"provider_id", "task_type", "status", "latency_ms", "confidence"}


class OkfExportError(RuntimeError):
    """Readable OKF export failure."""


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise OkfExportError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise OkfExportError(f"JSON payload must be an object: {path}")
    return payload


def load_session(args: argparse.Namespace) -> dict[str, Any]:
    if args.api_base or args.session_id:
        if not args.api_base or not args.session_id:
            raise OkfExportError("--api-base and --session-id must be provided together.")
        url = f"{args.api_base.rstrip('/')}/v1/sessions/{args.session_id}"
        try:
            with urllib.request.urlopen(url, timeout=args.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise OkfExportError(f"Cannot fetch session from {url}: {exc}") from exc
        if not isinstance(payload, dict):
            raise OkfExportError("Session API response must be a JSON object.")
        return payload

    source = args.session_json or DEFAULT_SESSION
    payload = load_json(source)
    if isinstance(payload.get("session"), dict):
        return payload["session"]
    return payload


def yaml_scalar(value: Any) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def yaml_lines(payload: Mapping[str, Any], indent: int = 0) -> list[str]:
    lines: list[str] = []
    prefix = " " * indent
    for key in sorted(payload):
        value = payload[key]
        if isinstance(value, Mapping):
            lines.append(f"{prefix}{key}:")
            lines.extend(yaml_lines(value, indent + 2))
        elif isinstance(value, list):
            lines.append(f"{prefix}{key}:")
            if not value:
                lines.append(f"{prefix}  []")
            for item in value:
                if isinstance(item, Mapping):
                    lines.append(f"{prefix}  -")
                    lines.extend(yaml_lines(item, indent + 4))
                else:
                    lines.append(f"{prefix}  - {yaml_scalar(item)}")
        else:
            lines.append(f"{prefix}{key}: {yaml_scalar(value)}")
    return lines


def write_markdown(path: Path, frontmatter: Mapping[str, Any], body_lines: Iterable[str]) -> None:
    text = "\n".join(["---", *yaml_lines(frontmatter), "---", "", *body_lines]).rstrip() + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def stringify(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(f"- {stringify(item)}" for item in value)
    if isinstance(value, dict):
        return "\n".join(f"- **{key}**: {stringify(item)}" for key, item in value.items())
    return str(value or "").strip()


def collect_sensitive_values(value: Any, *, inside_agent: bool = False) -> list[str]:
    hits: list[str] = []
    if isinstance(value, Mapping):
        for key, candidate in value.items():
            key_text = str(key).lower()
            next_inside_agent = inside_agent or key_text == "agent"
            sensitive_key = any(
                needle in key_text for needle in ("secret", "token", "password", "api_key", "apikey", "endpoint")
            ) or (inside_agent and "prompt" in key_text)
            if sensitive_key:
                hits.extend(flatten_strings(candidate))
            elif next_inside_agent and key_text not in SAFE_AGENT_KEYS:
                hits.extend(flatten_strings(candidate))
            hits.extend(collect_sensitive_values(candidate, inside_agent=next_inside_agent))
    elif isinstance(value, list):
        for item in value:
            hits.extend(collect_sensitive_values(item, inside_agent=inside_agent))
    return hits


def flatten_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        strings: list[str] = []
        for item in value.values():
            strings.extend(flatten_strings(item))
        return strings
    if isinstance(value, list):
        strings: list[str] = []
        for item in value:
            strings.extend(flatten_strings(item))
        return strings
    return []


def forbidden_values(session: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    source = session.get("source")
    if isinstance(source, Mapping):
        values.extend(flatten_strings(source.get("text")))
    for item in session.get("enrichment_items") or []:
        if isinstance(item, Mapping):
            values.extend(flatten_strings(item.get("text")))
    for answer in session.get("answers") or []:
        if isinstance(answer, Mapping):
            values.extend(flatten_strings(answer.get("text")))
    for grade in session.get("grading_results") or []:
        if isinstance(grade, Mapping):
            values.extend(flatten_strings(grade.get("feedback")))
    values.extend(collect_sensitive_values(session))
    return sorted({value.strip() for value in values if isinstance(value, str) and len(value.strip()) >= 8})


def redact(text: str, forbidden: Iterable[str]) -> str:
    redacted = text
    for value in sorted(forbidden, key=len, reverse=True):
        redacted = redacted.replace(value, "[redacted-private-session-value]")
    redacted = re.sub(r"sk-(?:proj-)?[A-Za-z0-9_-]{12,}", "[redacted-secret]", redacted)
    redacted = re.sub(r"github_pat_[A-Za-z0-9_]+", "[redacted-secret]", redacted)
    redacted = re.sub(r"gh[pousr]_[A-Za-z0-9_]+", "[redacted-secret]", redacted)
    return redacted


def note_frontmatter(
    session: Mapping[str, Any],
    *,
    kind: str,
    title: str,
    source: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": NOTE_SCHEMA,
        "bundle_schema_version": BUNDLE_SCHEMA,
        "brand": "认知黑箱 / Cognitive Black Box",
        "title": title,
        "kind": kind,
        "session_id": session.get("session_id", "unknown-session"),
        "track": session.get("track", "unknown"),
        "stage": session.get("stage", "unknown"),
        "source_reference": source.get("reference", ""),
        "source_excerpt_hash": source.get("excerpt_hash", ""),
        "consumers": CONSUMERS,
        "privacy": {
            "raw_source_text_included": False,
            "learner_answers_included": False,
            "grading_feedback_included": False,
            "agent_sensitive_metadata_included": False,
            "real_model_keys_included": False,
        },
    }


def layer_content(session: Mapping[str, Any], layer_name: str, forbidden: Iterable[str]) -> str:
    for layer in session.get("teaching_layers") or []:
        if isinstance(layer, Mapping) and str(layer.get("layer")) == layer_name:
            return redact(stringify(layer.get("content")), forbidden) or "_No content._"
    return "_Not generated for this session._"


def source_references(session: Mapping[str, Any]) -> list[dict[str, Any]]:
    references: list[dict[str, Any]] = []
    source = session.get("source")
    if isinstance(source, Mapping):
        references.append(
            {
                "kind": "primary",
                "source_type": source.get("source_type", ""),
                "reference": source.get("reference", ""),
                "title": source.get("title", ""),
                "excerpt_hash": source.get("excerpt_hash", ""),
                "verified": bool(source.get("verified")),
            }
        )
    for item in session.get("enrichment_items") or []:
        if not isinstance(item, Mapping):
            continue
        references.append(
            {
                "kind": "enrichment",
                "source_type": item.get("source_type", ""),
                "reference": item.get("reference", ""),
                "title": item.get("title", ""),
                "excerpt_hash": item.get("excerpt_hash", ""),
                "locator": item.get("locator", ""),
            }
        )
    return references


def build_notes(session: Mapping[str, Any], output_dir: Path) -> list[Path]:
    source = session.get("source")
    if not isinstance(source, Mapping):
        raise OkfExportError("Session must include a source object.")
    forbidden = forbidden_values(session)
    mastery = session.get("mastery") if isinstance(session.get("mastery"), Mapping) else {}
    files: list[Path] = []

    note_specs = [
        (
            "overview.md",
            "overview",
            "Session Overview",
            [
                "# Session Overview",
                "",
                "认知黑箱把这次学习会话导出为可读、可版本管理、可交给平台 Agent 的知识包。",
                "",
                f"- Track: `{session.get('track', 'unknown')}`",
                f"- Stage: `{session.get('stage', 'unknown')}`",
                f"- Source: {source.get('title', 'Untitled source')}",
                f"- Source reference: {source.get('reference', '')}",
                f"- Mastery: `{mastery.get('level', 0)}` / `{mastery.get('bloom', 'unknown')}`",
                "",
                "This bundle is an alignment layer, not a raw transcript archive.",
            ],
        ),
        (
            "concepts/overview.md",
            "concept_overview",
            "Concept Overview",
            ["# Concept Overview", "", layer_content(session, "overview", forbidden)],
        ),
        (
            "concepts/glossary.md",
            "concept_glossary",
            "Glossary",
            ["# Glossary", "", layer_content(session, "glossary", forbidden)],
        ),
        (
            "mastery.md",
            "mastery",
            "Mastery Record",
            [
                "# Mastery Record",
                "",
                f"- Level: `{mastery.get('level', 0)}`",
                f"- Bloom: `{mastery.get('bloom', 'unknown')}`",
                "- Review cue: re-answer the quiz without opening the source.",
                "",
                "## Insights",
                "",
                *[
                    f"- {redact(str(insight), forbidden)}"
                    for insight in (session.get("insights") or ["No synthesis generated yet."])
                ],
            ],
        ),
        (
            "sources.md",
            "sources",
            "Source References",
            [
                "# Source References",
                "",
                *[
                    (
                        f"- `{item['kind']}` `{item['source_type']}`: {item['title']} | "
                        f"{item['reference']} | `{item['excerpt_hash']}`"
                    )
                    for item in source_references(session)
                ],
                "",
                "Raw source text is intentionally not included.",
            ],
        ),
        (
            "questions/review.md",
            "question_review",
            "Question Review",
            question_review_lines(session),
        ),
        (
            "decisions.md",
            "decisions",
            "Handoff Decisions",
            [
                "# Handoff Decisions",
                "",
                "- Kimi/Codex/WorkBuddy should use this bundle as context, then call their own tools for fresh external data.",
                "- Obsidian can store the Markdown notes directly as a second-brain folder.",
                "- NotebookLM can ingest the Markdown notes plus user-selected original sources.",
                "- Study Anything does not store real model keys or raw platform browsing/video context.",
            ],
        ),
    ]

    for relative_path, kind, title, body_lines in note_specs:
        path = output_dir / relative_path
        write_markdown(
            path,
            note_frontmatter(session, kind=kind, title=title, source=source),
            body_lines,
        )
        files.append(path)
    return files


def question_review_lines(session: Mapping[str, Any]) -> list[str]:
    grades = {
        str(grade.get("item_id")): grade
        for grade in session.get("grading_results") or []
        if isinstance(grade, Mapping)
    }
    lines = ["# Question Review", ""]
    quiz_items = [item for item in session.get("quiz_items") or [] if isinstance(item, Mapping)]
    if not quiz_items:
        return [*lines, "_No quiz items generated._"]
    for index, item in enumerate(quiz_items, start=1):
        grade = grades.get(str(item.get("item_id")))
        lines.extend(
            [
                f"## Question {index}",
                "",
                f"- Prompt: {item.get('prompt', '')}",
                f"- Source ref: `{item.get('source_ref', '')}`",
                f"- Excerpt hash: `{item.get('excerpt_hash', '')}`",
                f"- Rubric: {item.get('rubric', '')}",
                "- Answer: _omitted from OKF bundle_",
            ]
        )
        if isinstance(grade, Mapping):
            lines.append(f"- Score: `{grade.get('score', 0)}`")
            lines.append("- Feedback: _omitted from OKF bundle_")
        lines.append("")
    return lines


def write_manifest(session: Mapping[str, Any], output_dir: Path, files: list[Path]) -> None:
    source = session.get("source") if isinstance(session.get("source"), Mapping) else {}
    manifest = {
        "schema_version": BUNDLE_SCHEMA,
        "generated_at": GENERATED_AT,
        "brand": "认知黑箱 / Cognitive Black Box",
        "purpose": "Convert a Study Anything learning session into a portable cognitive asset bundle.",
        "session": {
            "session_id": session.get("session_id", "unknown-session"),
            "track": session.get("track", "unknown"),
            "stage": session.get("stage", "unknown"),
            "source_title": source.get("title", ""),
            "source_reference": source.get("reference", ""),
            "source_excerpt_hash": source.get("excerpt_hash", ""),
        },
        "consumers": CONSUMERS,
        "files": [
            {
                "path": str(path.relative_to(output_dir)),
                "kind": "markdown_note",
                "sha256": sha256_text(path.read_text(encoding="utf-8")),
                "bytes": path.stat().st_size,
            }
            for path in sorted(files)
        ],
        "privacy": {
            "raw_source_text_included": False,
            "raw_enrichment_text_included": False,
            "learner_answers_included": False,
            "grading_feedback_included": False,
            "agent_sensitive_metadata_included": False,
            "real_model_keys_included": False,
            "secrets_included": False,
        },
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def export_bundle(session: Mapping[str, Any], output_dir: Path, *, clean: bool) -> None:
    if clean and output_dir.exists():
        resolved = output_dir.resolve()
        if resolved in {ROOT.resolve(), ROOT.parent.resolve()}:
            raise OkfExportError(f"Refusing to clean unsafe output directory: {output_dir}")
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    files = build_notes(session, output_dir)
    write_manifest(session, output_dir, files)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-json", type=Path, default=DEFAULT_SESSION)
    parser.add_argument("--api-base")
    parser.add_argument("--session-id")
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--clean", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    session = load_session(args)
    export_bundle(session, args.output_dir, clean=args.clean)
    print(f"wrote {args.output_dir.relative_to(ROOT) if args.output_dir.is_relative_to(ROOT) else args.output_dir}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"export_okf_bundle failed: {exc}", file=sys.stderr)
        sys.exit(1)
