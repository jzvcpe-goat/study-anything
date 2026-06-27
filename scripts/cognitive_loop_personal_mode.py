#!/usr/bin/env python3
"""Build read-only Personal Plugin Mode Lite learning artifacts."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
from html import escape
import json
from pathlib import Path
import re
from typing import Any, Iterable
from urllib.parse import urlparse


SCHEMA_VERSION = "cognitive-loop-personal-plugin-mode-v1"

SECRET_PATTERNS = [
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"(?i)\bdiff --git\b"),
    re.compile(r"http://127\.0\.0\.1:8787[^\s\"']*"),
    re.compile(r"/Users/[^\s\"']+"),
]
FORBIDDEN_LITERALS = [
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "learner answer:",
    "raw source text",
    "raw diff",
    "private source text",
    "agent endpoint:",
]


class PersonalModeError(RuntimeError):
    """Readable Personal Plugin Mode CLI failure."""


@dataclass(frozen=True)
class TargetSpec:
    kind: str
    reference: str
    title: str
    content_for_scan: str
    metadata: dict[str, Any]


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def resolve_under_root(root: Path, value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise PersonalModeError(f"Path must stay under project root: {value}") from exc
    return path


def relative_path(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def assert_no_private_text(text: str, *, label: str) -> None:
    lowered = text.lower()
    literal_hits = [literal for literal in FORBIDDEN_LITERALS if literal.lower() in lowered]
    pattern_hits = [pattern.pattern for pattern in SECRET_PATTERNS if pattern.search(text)]
    if literal_hits or pattern_hits:
        raise PersonalModeError(f"{label} contains private-looking text: literals={literal_hits} patterns={pattern_hits}")


def assert_public_payload(payload: Any, *, label: str) -> None:
    assert_no_private_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), label=label)


def count_lines(data: bytes) -> int:
    if not data:
        return 0
    return data.count(b"\n") + (0 if data.endswith(b"\n") else 1)


def file_target(root: Path, value: str, *, kind: str) -> TargetSpec:
    path = resolve_under_root(root, value)
    if not path.is_file():
        raise PersonalModeError(f"{kind} target does not exist: {value}")
    data = path.read_bytes()
    text = data.decode("utf-8", errors="replace")
    assert_no_private_text(text, label=f"{kind}:{relative_path(root, path)}")
    relative = relative_path(root, path)
    metadata = {
        "path": relative,
        "extension": path.suffix or "(none)",
        "size_bytes": len(data),
        "line_count": count_lines(data),
        "sha256": sha256_bytes(data),
        "content_included": False,
    }
    title = "README" if kind == "readme" else path.name
    return TargetSpec(kind=kind, reference=relative, title=title, content_for_scan=text, metadata=metadata)


def webpage_target(url: str, title: str, summary: str) -> TargetSpec:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise PersonalModeError("Webpage target requires an http(s) URL.")
    assert_no_private_text(title, label="webpage title")
    assert_no_private_text(summary, label="webpage summary")
    metadata = {
        "url_host": parsed.netloc,
        "url_scheme": parsed.scheme,
        "title_sha256": sha256_text(title),
        "summary_sha256": sha256_text(summary),
        "summary_length": len(summary),
        "content_included": False,
    }
    return TargetSpec(
        kind="webpage",
        reference=f"{parsed.scheme}://{parsed.netloc}{parsed.path or '/'}",
        title=title or parsed.netloc,
        content_for_scan=summary,
        metadata=metadata,
    )


def diff_target(summary: str, paths: Iterable[str]) -> TargetSpec:
    path_list = [path for path in paths if path]
    if not summary:
        raise PersonalModeError("Diff target requires --diff-summary.")
    assert_no_private_text(summary, label="diff summary")
    for path in path_list:
        assert_no_private_text(path, label="diff path")
    metadata = {
        "changed_path_count": len(path_list),
        "changed_paths": sorted(path_list)[:12],
        "summary_sha256": sha256_text(summary),
        "content_included": False,
        "raw_diff_included": False,
    }
    return TargetSpec(
        kind="diff_summary",
        reference="git://diff-summary",
        title="Git diff summary",
        content_for_scan=summary,
        metadata=metadata,
    )


def infer_target(root: Path, args: argparse.Namespace) -> TargetSpec:
    provided = [bool(args.file), bool(args.readme), bool(args.web_url), bool(args.diff_summary)]
    if sum(provided) != 1:
        raise PersonalModeError("Provide exactly one of --file, --readme, --web-url, or --diff-summary.")
    if args.file:
        return file_target(root, args.file, kind="file")
    if args.readme:
        return file_target(root, args.readme, kind="readme")
    if args.web_url:
        return webpage_target(args.web_url, args.web_title or "", args.web_summary or "")
    return diff_target(args.diff_summary or "", args.changed_path)


def target_guidance(kind: str) -> dict[str, str]:
    guidance = {
        "file": {
            "overview": "Use the file metadata to ask what role this file plays before reading implementation details.",
            "term": "File boundary: the responsibilities and risks attached to a single repo path.",
            "practice": "Explain why this file matters, then name one verification command before editing it.",
        },
        "readme": {
            "overview": "Use the README as the public contract for how a new adopter understands the project.",
            "term": "Onboarding contract: the claims a project makes to a first-time reader.",
            "practice": "Summarize the launch path, then identify one claim that needs machine-checkable evidence.",
        },
        "webpage": {
            "overview": "Use webpage metadata as a bounded external context pointer owned by the platform Agent.",
            "term": "External context handoff: a source reference and hash that Study Anything can learn from later.",
            "practice": "State what the page is supposed to teach, then decide what excerpt would be safe to import.",
        },
        "diff_summary": {
            "overview": "Use the diff summary as a risk lens before reviewing raw changes in the platform Agent.",
            "term": "Diff summary: a metadata-only description of changed paths and expected behavioral impact.",
            "practice": "Name the risk, verification proof, rollback path, and whether a Human Mastery Gate is needed.",
        },
    }
    return guidance[kind]


def build_report(target: TargetSpec, *, generated_at: str, root: Path, output_dir: Path) -> dict[str, Any]:
    guide = target_guidance(target.kind)
    artifact_id = f"personal-{target.kind}-{sha256_text(target.reference)[:12]}"
    study_cards = [
        {
            "card_id": f"{artifact_id}-overview",
            "title": "Whole Target",
            "prompt": guide["overview"],
            "evidence_ref": target.reference,
        },
        {
            "card_id": f"{artifact_id}-term",
            "title": "Key Term",
            "prompt": guide["term"],
            "evidence_ref": target.reference,
        },
        {
            "card_id": f"{artifact_id}-practice",
            "title": "Practice",
            "prompt": guide["practice"],
            "evidence_ref": target.reference,
        },
    ]
    quiz_items = [
        {
            "item_id": f"{artifact_id}-q1",
            "question": "What is the target's role, stated without copying source text?",
            "rubric": "Answer should cite the reference and avoid private content.",
        },
        {
            "item_id": f"{artifact_id}-q2",
            "question": "What proof or command should run before trusting this target?",
            "rubric": "Answer should name a local verifier, test, or human gate.",
        },
    ]
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "generated_at": generated_at,
        "mode": "personal_plugin_mode_lite",
        "artifact_id": artifact_id,
        "title": "Cognitive Loop Personal Plugin Mode Lite",
        "target": {
            "kind": target.kind,
            "reference": target.reference,
            "title": target.title,
            "metadata": target.metadata,
        },
        "outputs": {
            "study_cards": study_cards,
            "quiz_items": quiz_items,
            "markdown_ref": relative_path(root, output_dir / f"{artifact_id}.md"),
            "html_ref": relative_path(root, output_dir / f"{artifact_id}.html"),
            "json_ref": relative_path(root, output_dir / f"{artifact_id}.json"),
        },
        "privacy": {
            "read_only": True,
            "source_text_included": False,
            "raw_diff_included": False,
            "learner_answers_included": False,
            "agent_endpoint_included": False,
            "agent_metadata_included": False,
            "prompt_text_included": False,
            "real_model_keys_stored": False,
            "standalone_frontend_required": False,
            "daemon_started": False,
            "model_called": False,
        },
        "plugin_boundary": {
            "owner_of_external_context": "platform_agent_or_personal_plugin",
            "study_anything_role": "read_only_learning_adapter",
            "default_action": "explain_only",
            "auto_apply": False,
        },
    }
    assert_public_payload(report, label="personal mode report")
    return report


def render_markdown(report: dict[str, Any]) -> str:
    target = report["target"]
    lines = [
        "# Cognitive Loop Personal Plugin Mode Lite",
        "",
        f"- Mode: `{report['mode']}`",
        f"- Target kind: `{target['kind']}`",
        f"- Reference: `{target['reference']}`",
        f"- Status: `{report['status']}`",
        "",
        "## Study Cards",
    ]
    for card in report["outputs"]["study_cards"]:
        lines.append(f"- **{card['title']}**: {card['prompt']}")
    lines.extend(["", "## Quiz"])
    for item in report["outputs"]["quiz_items"]:
        lines.append(f"- {item['question']}")
    lines.extend(
        [
            "",
            "## Privacy",
            "- Read-only: true",
            "- Source text included: false",
            "- Diff body included: false",
            "- Real model keys stored: false",
        ]
    )
    markdown = "\n".join(lines) + "\n"
    assert_no_private_text(markdown, label="personal mode markdown")
    return markdown


def render_html(report: dict[str, Any]) -> str:
    target = report["target"]
    cards = "\n".join(
        f"<li><strong>{escape(card['title'])}</strong>: {escape(card['prompt'])}</li>"
        for card in report["outputs"]["study_cards"]
    )
    quiz = "\n".join(f"<li>{escape(item['question'])}</li>" for item in report["outputs"]["quiz_items"])
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Cognitive Loop Personal Plugin Mode Lite</title>
  <style>
    body {{ margin: 0; font-family: ui-sans-serif, system-ui, sans-serif; background: #f7f4ed; color: #1f2528; }}
    main {{ max-width: 920px; margin: 0 auto; padding: 32px 20px; }}
    section {{ border-top: 1px solid #d8d0c4; padding: 18px 0; }}
    code {{ background: #eee6d8; padding: 2px 5px; border-radius: 4px; }}
    @media (max-width: 720px) {{ main {{ padding: 22px 14px; }} }}
  </style>
</head>
<body>
<main>
  <h1>Cognitive Loop Personal Plugin Mode Lite</h1>
  <section>
    <h2>Target</h2>
    <p><strong>Kind:</strong> <code>{escape(target['kind'])}</code></p>
    <p><strong>Reference:</strong> <code>{escape(target['reference'])}</code></p>
  </section>
  <section>
    <h2>Study Cards</h2>
    <ul>{cards}</ul>
  </section>
  <section>
    <h2>Quiz</h2>
    <ol>{quiz}</ol>
  </section>
  <section>
    <h2>Privacy</h2>
    <p>Read-only, metadata-only, no source text, diff body, learner answers, Agent endpoints, Agent metadata, prompts, or model keys.</p>
  </section>
</main>
</body>
</html>
"""
    assert_no_private_text(html, label="personal mode html")
    return html


def write_outputs(root: Path, output_dir: Path, report: dict[str, Any], *, write_html: bool, write_markdown: bool) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_id = report["artifact_id"]
    (output_dir / f"{artifact_id}.json").write_text(dump_json(report), encoding="utf-8")
    if write_markdown:
        (output_dir / f"{artifact_id}.md").write_text(render_markdown(report), encoding="utf-8")
    if write_html:
        (output_dir / f"{artifact_id}.html").write_text(render_html(report), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Project root.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    explain = subparsers.add_parser("explain", help="Build a read-only personal learning artifact.")
    explain.add_argument("--file", help="Repo-relative file target.")
    explain.add_argument("--readme", help="Repo-relative README target.")
    explain.add_argument("--web-url", help="External webpage URL reference.")
    explain.add_argument("--web-title", default="", help="External webpage title metadata.")
    explain.add_argument("--web-summary", default="", help="Bounded webpage summary metadata.")
    explain.add_argument("--diff-summary", help="Metadata-only git diff summary.")
    explain.add_argument("--changed-path", action="append", default=[], help="Repo-relative changed path for diff summary.")
    explain.add_argument("--generated-at", default="2026-01-01T00:00:00Z")
    explain.add_argument("--output-dir", default=".cognitive-loop/artifacts/personal-mode")
    explain.add_argument("--html", action="store_true")
    explain.add_argument("--markdown", action="store_true")
    explain.add_argument("--json", action="store_true")
    return parser


def command_explain(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    target = infer_target(root, args)
    output_dir = resolve_under_root(root, args.output_dir)
    report = build_report(target, generated_at=args.generated_at, root=root, output_dir=output_dir)
    write_outputs(root, output_dir, report, write_html=args.html, write_markdown=args.markdown)
    if args.json or not args.html and not args.markdown:
        print(dump_json(report), end="")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "explain":
            return command_explain(args)
    except PersonalModeError as exc:
        print(f"cognitive_loop_personal_mode failed: {exc}", flush=True)
        return 1
    parser.error(f"Unhandled command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
