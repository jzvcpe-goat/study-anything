#!/usr/bin/env python3
"""Generate the distributable platform adoption pack archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "platform" / "generated"
MANIFEST_PATH = OUTPUT_DIR / "study-anything-platform-adoption-pack.json"
ARCHIVE_PATH = OUTPUT_DIR / "study-anything-platform-adoption-pack.zip"
ARCHIVE_ROOT = "study-anything-platform-adoption-pack"


PACK_FILES: list[tuple[str, str, str]] = [
    ("README.md", "root_doc", "Repository overview and local-first launch entrypoint."),
    ("docs/adoption.md", "operator_doc", "Clean-clone and published-image adoption guide."),
    ("docs/platform-agent-integrations.md", "operator_doc", "General external platform Agent integration guide."),
    ("docs/learning-enrichment.md", "operator_doc", "Learning Enrichment Layer context contract and micro-lesson export guide."),
    ("docs/second-brain-handoff.md", "operator_doc", "Strict Obsidian, NotebookLM-style, and local archive handoff guide."),
    ("docs/obsidian-export.md", "operator_doc", "Obsidian export privacy and second-brain note guide."),
    ("docs/notebooklm-bridge.md", "operator_doc", "NotebookLM-style manual bridge contract."),
    ("docs/kimi-agent-gateway.md", "operator_doc", "Kimi-compatible HTTP Agent gateway guide."),
    ("docs/use-with-kimi.md", "operator_doc", "Kimi usage modes for copy-only, HTTP tools, and local Agent gateway."),
    ("docs/operator-drill.md", "operator_doc", "External platform operator drill and transcript guide."),
    ("docs/self-hosting.md", "operator_doc", "Docker/Skill Mode self-hosting guide."),
    ("docs/agent-eval.md", "operator_doc", "Agent and retrieval eval guide."),
    ("docs/api.md", "operator_doc", "HTTP API reference for platform workspaces."),
    ("docs/release-notes/v0.2.26-alpha.md", "release_doc", "Release notes for this adoption pack."),
    ("platform/study-anything-platform-tools.json", "tool_manifest", "Source platform tool contract."),
    ("platform/generated/study-anything-platform-openapi.json", "tool_import", "OpenAPI 3.1 import asset."),
    ("platform/generated/study-anything-openai-tools.json", "tool_import", "OpenAI-compatible function tools."),
    ("platform/generated/study-anything-tool-catalog.md", "tool_catalog", "Human-readable platform tool catalog."),
    ("platform/generated/study-anything-platform-bundle.json", "bundle_manifest", "Source file manifest for platform assets."),
    ("platform/packs/README.md", "platform_pack", "Platform pack index."),
    ("platform/packs/kimi/README.md", "platform_pack", "Kimi Work and Kimi-compatible setup."),
    ("platform/packs/kimi/pack.json", "platform_pack", "Machine-readable Kimi pack."),
    ("platform/packs/codex/README.md", "platform_pack", "Codex setup and command flow."),
    ("platform/packs/codex/pack.json", "platform_pack", "Machine-readable Codex pack."),
    ("platform/packs/workbuddy/README.md", "platform_pack", "WorkBuddy-style HTTP workspace setup."),
    ("platform/packs/workbuddy/pack.json", "platform_pack", "Machine-readable WorkBuddy pack."),
    ("skills/study-anything/SKILL.md", "skill", "Codex Skill entrypoint."),
    ("skills/study-anything/agents/openai.yaml", "skill", "OpenAI-compatible Skill agent metadata."),
    ("scripts/openai_compatible_agent_gateway.py", "gateway", "User-owned local HTTP Agent gateway."),
    ("scripts/mock_http_agent.py", "gateway", "Deterministic mock HTTP Agent for smoke tests."),
    ("scripts/launch_skill_mode.sh", "runtime", "Local Skill Mode API launcher."),
    ("scripts/stop_skill_mode.sh", "runtime", "Local Skill Mode API stop helper."),
    ("scripts/run_skill_mode_demo.sh", "verification", "One-command Skill Mode demo and eval gate."),
    ("scripts/study_anything_cli.py", "cli", "CLI for learning loop and evidence commands."),
    ("scripts/verify_external_adoption.py", "verification", "Adoption-proof-v1 verifier for external operators."),
    ("scripts/verify_platform_operator_drill.py", "verification", "External platform pack consumption verifier."),
    ("scripts/verify_platform_agent_tools.py", "verification", "Platform tool manifest runtime verifier."),
    ("scripts/verify_platform_ecosystem_eval_flow.py", "verification", "Full platform ecosystem learning/eval/export verifier."),
    ("scripts/verify_importer_lesson_flow.py", "verification", "NotebookLM-style importer lesson verifier."),
    ("scripts/verify_importer_runtime_retrieval_flow.py", "verification", "Importer runtime plus retrieval verifier."),
    ("scripts/verify_platform_lesson_flow.py", "verification", "Enriched platform lesson verifier."),
    ("scripts/verify_agent_eval_flow.py", "verification", "Agent eval artifact verifier."),
    ("scripts/verify_agent_eval_baseline.py", "verification", "Agent eval baseline and regression gate verifier."),
    ("scripts/run_external_agent_evals.py", "verification", "Promptfoo/DeepEval/retrieval eval runner."),
    ("scripts/verify_openai_compatible_gateway.py", "verification", "OpenAI-compatible gateway dry-run verifier."),
    ("scripts/diagnose_adoption.py", "diagnostics", "Adoption diagnostics and remediation hints."),
    ("evals/promptfoo/agent-eval-artifact.yaml", "eval", "Promptfoo eval config."),
    ("evals/deepeval/study_anything_quality_eval.py", "eval", "DeepEval-compatible native quality adapter."),
    ("evals/baselines/study-anything-agent-eval-baseline.json", "eval", "Deterministic Agent eval regression baseline."),
    ("fixtures/notebooklm/README.md", "fixture", "NotebookLM fixture notes."),
    ("fixtures/notebooklm/notebooklm-style-context-package.json", "fixture", "NotebookLM-style context package fixture."),
]

REQUIRED_PLATFORM_TOOLS = [
    "study_anything_health",
    "study_anything_create_session",
    "study_anything_add_reading",
    "study_anything_validate_context_package",
    "study_anything_create_session_from_context_package",
    "study_anything_append_context_package",
    "study_anything_run_importer",
    "study_anything_add_enrichment",
    "study_anything_run",
    "study_anything_answer",
    "study_anything_mastery",
    "study_anything_retrieval_search",
    "study_anything_retrieval_quality_eval",
    "study_anything_teaching_layers",
    "study_anything_agent_audit",
    "study_anything_agent_eval_artifact",
    "study_anything_agent_quality_eval",
    "study_anything_obsidian_export",
    "study_anything_enrichment_artifact_export",
    "study_anything_learning_package_export",
    "study_anything_second_brain_handoff_export",
]


class AdoptionPackError(RuntimeError):
    """Readable adoption-pack generation failure."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise AdoptionPackError(f"Cannot read JSON {path.relative_to(ROOT)}: {exc}") from exc


def assert_safe_path(relative_path: str) -> Path:
    path = ROOT / relative_path
    if not path.exists():
        raise AdoptionPackError(f"Adoption pack file is missing: {relative_path}")
    if path.is_dir():
        raise AdoptionPackError(f"Adoption pack file must not be a directory: {relative_path}")
    if any(part in {".git", ".env", ".venv", "data", "__pycache__"} for part in path.parts):
        raise AdoptionPackError(f"Unsafe adoption pack path: {relative_path}")
    return path


def file_record(relative_path: str, kind: str, purpose: str) -> dict[str, object]:
    path = assert_safe_path(relative_path)
    return {
        "path": relative_path,
        "archive_path": f"{ARCHIVE_ROOT}/{relative_path}",
        "kind": kind,
        "purpose": purpose,
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def validate_source_contract() -> None:
    tools = read_json(ROOT / "platform" / "study-anything-platform-tools.json")
    if tools.get("schema_version") != "study-anything-platform-tools-v1":
        raise AdoptionPackError("Platform tool manifest schema drifted.")
    names = {tool.get("name") for tool in tools.get("tools", [])}
    missing = [name for name in REQUIRED_PLATFORM_TOOLS if name not in names]
    if missing:
        raise AdoptionPackError(f"Platform tool manifest is missing adoption tools: {missing}")


def pack_readme() -> str:
    return """# Study Anything Platform Adoption Pack

This archive is the copy-ready integration bundle for Kimi Work, Codex,
WorkBuddy-style HTTP tool workspaces, and other platform Agents.

Use it when the platform Agent owns browsing, files, video slicing, outside
tools, real model credentials, and conversation. Study Anything owns the
source-bound learning workflow, state, audit, eval evidence, retrieval quality,
and Obsidian/NotebookLM handoff.

## Quick Start

1. Start Study Anything locally with Skill Mode or the published Docker image.
2. Import `platform/generated/study-anything-platform-openapi.json` or
   `platform/generated/study-anything-openai-tools.json` into your platform.
3. Follow the operator guide for your platform under `platform/packs/`.
4. Run:

```bash
python3 scripts/verify_external_adoption.py --pack platform/generated/study-anything-platform-adoption-pack.zip --copy-worktree
```

The verifier emits `adoption-proof-v1` JSON. Treat that JSON as the minimum
acceptance evidence before claiming an external platform integration works.

## Privacy

Do not put real model API keys in Study Anything. Keep real model credentials
inside the user's own Agent or platform runtime. The adoption evidence is
designed to be redacted and must not include raw source text, long answers,
agent endpoints with secrets, or platform-private browsing/video context.
"""


def manifest_payload() -> dict[str, object]:
    validate_source_contract()
    file_paths = [path for path, _kind, _purpose in PACK_FILES]
    if len(file_paths) != len(set(file_paths)):
        raise AdoptionPackError("Adoption pack file list contains duplicates.")
    return {
        "schema_version": "study-anything-platform-adoption-pack-v1",
        "name": "study-anything-platform-adoption-pack",
        "version": "v0.2.26-alpha",
        "archive_name": ARCHIVE_PATH.name,
        "archive_root": ARCHIVE_ROOT,
        "description": (
            "Copy-ready platform adoption pack for Kimi Work, Codex, WorkBuddy-style "
            "HTTP workspaces, NotebookLM/Obsidian handoff, and external Agent eval proof."
        ),
        "supported_platforms": ["kimi-work", "codex", "workbuddy-style-http", "generic-http-tools"],
        "runtime_modes": ["skill-mode", "published-image"],
        "no_frontend_required": True,
        "real_model_keys_stored_by_study_anything": False,
        "required_tool_names": REQUIRED_PLATFORM_TOOLS,
        "acceptance": {
            "proof_schema": "adoption-proof-v1",
            "command": (
                "python3 scripts/verify_external_adoption.py --pack "
                "platform/generated/study-anything-platform-adoption-pack.zip --copy-worktree"
            ),
            "target_minutes": 15,
            "must_verify": [
                "archive sha256 manifest",
                "OpenAPI/OpenAI tool import assets",
                "Kimi/Codex/WorkBuddy operator packs",
                "Skill Mode or published-image runtime",
                "external platform Agent learning flow",
                "external platform pack consumption drill",
                "retrieval-quality-eval-v1",
                "agent-quality-eval-v1",
                "study-anything-agent-eval-regression-report-v1",
                "obsidian-markdown-export-v1",
                "learning-package-v1",
                "second-brain-handoff-v1",
            ],
        },
        "privacy_contract": {
            "must_not_store": [
                "real model API keys",
                "platform private browser traces",
                "raw long source text in eval evidence",
                "raw answer text in eval evidence",
                "agent endpoint secrets",
            ],
            "user_owned_exports_may_include": [
                "learner answers",
                "review history",
                "Obsidian markdown selected by the learner",
            ],
        },
        "files": [file_record(*item) for item in PACK_FILES],
    }


def dump_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def archive_bytes(manifest: dict[str, object]) -> bytes:
    import io

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, content in [
            (f"{ARCHIVE_ROOT}/ADOPTION_PACK_README.md", pack_readme().encode("utf-8")),
            (f"{ARCHIVE_ROOT}/manifest.json", dump_json(manifest).encode("utf-8")),
        ]:
            info = zipfile.ZipInfo(name)
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, content)
        for record in sorted(manifest["files"], key=lambda item: str(item["path"])):  # type: ignore[index]
            relative_path = str(record["path"])
            source = ROOT / relative_path
            info = zipfile.ZipInfo(str(record["archive_path"]))
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, source.read_bytes())
    return buffer.getvalue()


def build_outputs() -> tuple[str, bytes]:
    archive_manifest = manifest_payload()
    archive = archive_bytes(archive_manifest)
    enriched = dict(archive_manifest)
    enriched["archive_sha256"] = sha256_bytes(archive)
    enriched["archive_bytes"] = len(archive)
    return dump_json(enriched), archive


def write_outputs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest_text, archive = build_outputs()
    MANIFEST_PATH.write_text(manifest_text, encoding="utf-8")
    ARCHIVE_PATH.write_bytes(archive)
    print(f"wrote {MANIFEST_PATH.relative_to(ROOT)}")
    print(f"wrote {ARCHIVE_PATH.relative_to(ROOT)}")


def check_outputs() -> None:
    expected_manifest, expected_archive = build_outputs()
    missing = [
        str(path.relative_to(ROOT))
        for path in [MANIFEST_PATH, ARCHIVE_PATH]
        if not path.exists()
    ]
    stale = []
    if MANIFEST_PATH.exists() and MANIFEST_PATH.read_text(encoding="utf-8") != expected_manifest:
        stale.append(str(MANIFEST_PATH.relative_to(ROOT)))
    if ARCHIVE_PATH.exists() and ARCHIVE_PATH.read_bytes() != expected_archive:
        stale.append(str(ARCHIVE_PATH.relative_to(ROOT)))
    if missing or stale:
        raise AdoptionPackError(
            "Platform adoption pack is stale. Run "
            "`python3 scripts/generate_platform_adoption_pack.py`. "
            f"missing={missing} stale={stale}"
        )
    print("ok    generated platform adoption pack is up to date")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        check_outputs()
    else:
        write_outputs()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"generate_platform_adoption_pack failed: {exc}", file=sys.stderr)
        sys.exit(1)
