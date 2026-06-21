#!/usr/bin/env python3
"""Verify an OKF-style Cognitive Black Box learning bundle."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

import export_okf_bundle


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE = ROOT / "platform" / "okf" / "examples" / "demo-okf-bundle"
DEFAULT_SESSION = ROOT / "platform" / "okf" / "examples" / "demo-session.json"
REPORT = ROOT / "platform" / "generated" / "study-anything-okf-alignment.json"
REPORT_SCHEMA = "cognitive-black-box-okf-alignment-verification-v1"
REQUIRED_MARKDOWN = {
    "overview.md",
    "concepts/overview.md",
    "concepts/glossary.md",
    "questions/review.md",
    "mastery.md",
    "sources.md",
    "decisions.md",
}
SECRET_PATTERNS = [
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-proj-[A-Za-z0-9_-]{12,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*[\"']?[A-Za-z0-9_./+=-]{8,}"),
]


class OkfVerificationError(RuntimeError):
    """Readable OKF verification failure."""


def dump_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def load_session(path: Path) -> dict[str, Any]:
    payload = export_okf_bundle.load_json(path)
    if isinstance(payload.get("session"), dict):
        return payload["session"]
    return payload


def load_manifest(bundle_dir: Path) -> dict[str, Any]:
    manifest_path = bundle_dir / "manifest.json"
    if not manifest_path.exists():
        raise OkfVerificationError(f"OKF manifest missing: {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise OkfVerificationError(f"Cannot read OKF manifest: {exc}") from exc
    if not isinstance(manifest, dict):
        raise OkfVerificationError("OKF manifest must be a JSON object.")
    return manifest


def markdown_files(bundle_dir: Path) -> dict[str, Path]:
    files = {
        str(path.relative_to(bundle_dir)): path
        for path in bundle_dir.rglob("*.md")
        if path.is_file()
    }
    missing = sorted(REQUIRED_MARKDOWN - set(files))
    if missing:
        raise OkfVerificationError(f"OKF bundle is missing Markdown files: {missing}")
    return files


def assert_frontmatter(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise OkfVerificationError(f"{path} is missing YAML frontmatter.")
    try:
        _prefix, frontmatter, _body = text.split("---", 2)
    except ValueError as exc:
        raise OkfVerificationError(f"{path} has malformed YAML frontmatter.") from exc
    for required in (
        "schema_version: \"cognitive-black-box-okf-note-v1\"",
        "bundle_schema_version: \"cognitive-black-box-okf-bundle-v1\"",
        "brand: \"认知黑箱 / Cognitive Black Box\"",
    ):
        if required not in frontmatter:
            raise OkfVerificationError(f"{path} frontmatter missing {required!r}.")


def bundle_text(bundle_dir: Path) -> str:
    chunks: list[str] = []
    for path in sorted(bundle_dir.rglob("*")):
        if path.is_file() and path.suffix in {".md", ".json"}:
            chunks.append(path.read_text(encoding="utf-8"))
    return "\n".join(chunks)


def assert_no_forbidden_text(text: str, forbidden: Iterable[str]) -> list[str]:
    hits = [value for value in forbidden if value and value in text]
    if hits:
        raise OkfVerificationError(f"OKF bundle leaked forbidden session values: {hits[:5]}")
    regex_hits = [pattern.pattern for pattern in SECRET_PATTERNS if pattern.search(text)]
    if regex_hits:
        raise OkfVerificationError(f"OKF bundle contains secret-like patterns: {regex_hits}")
    return regex_hits


def verify_bundle(bundle_dir: Path, session_path: Path) -> dict[str, Any]:
    session = load_session(session_path)
    manifest = load_manifest(bundle_dir)
    if manifest.get("schema_version") != export_okf_bundle.BUNDLE_SCHEMA:
        raise OkfVerificationError("OKF manifest schema_version drifted.")
    if manifest.get("brand") != "认知黑箱 / Cognitive Black Box":
        raise OkfVerificationError("OKF manifest brand must be Cognitive Black Box.")
    if manifest.get("session", {}).get("session_id") != session.get("session_id"):
        raise OkfVerificationError("OKF manifest session_id does not match source session.")
    consumers = set(manifest.get("consumers") or [])
    for consumer in ("kimi", "codex", "obsidian", "notebooklm"):
        if consumer not in consumers:
            raise OkfVerificationError(f"OKF manifest missing consumer: {consumer}")
    privacy = manifest.get("privacy")
    if not isinstance(privacy, Mapping):
        raise OkfVerificationError("OKF manifest privacy must be an object.")
    for key in (
        "raw_source_text_included",
        "raw_enrichment_text_included",
        "learner_answers_included",
        "grading_feedback_included",
        "agent_sensitive_metadata_included",
        "real_model_keys_included",
        "secrets_included",
    ):
        if privacy.get(key) is not False:
            raise OkfVerificationError(f"OKF privacy.{key} must be false.")

    files = markdown_files(bundle_dir)
    for path in files.values():
        assert_frontmatter(path)
    text = bundle_text(bundle_dir)
    forbidden = export_okf_bundle.forbidden_values(session)
    assert_no_forbidden_text(text, forbidden)
    if "Answer: _omitted from OKF bundle_" not in text:
        raise OkfVerificationError("OKF question review must explicitly omit learner answers.")
    if "Feedback: _omitted from OKF bundle_" not in text:
        raise OkfVerificationError("OKF question review must explicitly omit grading feedback.")

    return {
        "schema_version": REPORT_SCHEMA,
        "status": "pass",
        "bundle_schema": manifest["schema_version"],
        "note_schema": export_okf_bundle.NOTE_SCHEMA,
        "bundle_dir": str(bundle_dir.relative_to(ROOT) if bundle_dir.is_relative_to(ROOT) else bundle_dir),
        "source_session": str(session_path.relative_to(ROOT) if session_path.is_relative_to(ROOT) else session_path),
        "file_count": len(files) + 1,
        "markdown_files": sorted(files),
        "consumers": sorted(consumers),
        "privacy": {
            "raw_source_text_included": False,
            "raw_enrichment_text_included": False,
            "learner_answers_included": False,
            "grading_feedback_included": False,
            "agent_sensitive_metadata_included": False,
            "real_model_keys_included": False,
            "secrets_included": False,
        },
        "platform_alignment": {
            "kimi_context_bundle": True,
            "codex_skill_context_bundle": True,
            "obsidian_second_brain_folder": True,
            "notebooklm_manual_source_bundle": True,
            "standalone_frontend_required": False,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-dir", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--source-session-json", type=Path, default=DEFAULT_SESSION)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = verify_bundle(args.bundle_dir, args.source_session_json)
    text = dump_json(report)
    if args.write:
        REPORT.write_text(text, encoding="utf-8")
        print(f"wrote {REPORT.relative_to(ROOT)}")
        return
    if args.check:
        if not REPORT.exists():
            raise OkfVerificationError(f"OKF report missing: {REPORT.relative_to(ROOT)}")
        if REPORT.read_text(encoding="utf-8") != text:
            raise OkfVerificationError(
                "OKF alignment report is stale. Run: python3 scripts/verify_okf_bundle.py --write"
            )
        print("ok    OKF alignment report is up to date")
        return
    print(text, end="")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"verify_okf_bundle failed: {exc}", file=sys.stderr)
        sys.exit(1)
