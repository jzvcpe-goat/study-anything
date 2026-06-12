#!/usr/bin/env python3
"""Generate a deterministic manifest for distributing platform integration assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
SOURCE_MANIFEST = ROOT / "platform" / "study-anything-platform-tools.json"
BUNDLE_MANIFEST = ROOT / "platform" / "generated" / "study-anything-platform-bundle.json"

FILES: list[tuple[str, str, str]] = [
    (
        "platform/study-anything-platform-tools.json",
        "source_manifest",
        "Source contract for all platform learning tools.",
    ),
    (
        "platform/generated/study-anything-platform-openapi.json",
        "generated_asset",
        "OpenAPI 3.1 import asset for HTTP tool platforms.",
    ),
    (
        "platform/generated/study-anything-openai-tools.json",
        "generated_asset",
        "OpenAI-compatible function tools for Kimi-compatible and other tool-calling agents.",
    ),
    (
        "platform/generated/study-anything-tool-catalog.md",
        "generated_asset",
        "Human-readable tool catalog for platform operators.",
    ),
    (
        "platform/packs/README.md",
        "platform_pack",
        "Index for copy-ready platform packs.",
    ),
    (
        "platform/packs/codex/README.md",
        "platform_pack",
        "Codex and terminal-capable Agent setup guide.",
    ),
    (
        "platform/packs/codex/pack.json",
        "platform_pack",
        "Machine-readable Codex pack metadata.",
    ),
    (
        "platform/packs/kimi/README.md",
        "platform_pack",
        "Kimi tool import and gateway setup guide.",
    ),
    (
        "platform/packs/kimi/pack.json",
        "platform_pack",
        "Machine-readable Kimi pack metadata.",
    ),
    (
        "platform/packs/workbuddy/README.md",
        "platform_pack",
        "WorkBuddy-style HTTP tool workspace setup guide.",
    ),
    (
        "platform/packs/workbuddy/pack.json",
        "platform_pack",
        "Machine-readable WorkBuddy pack metadata.",
    ),
    (
        "scripts/openai_compatible_agent_gateway.py",
        "gateway",
        "User-owned OpenAI-compatible HTTP Agent gateway for Kimi and similar providers.",
    ),
    (
        "scripts/run_skill_mode_demo.sh",
        "verification",
        "One-command Skill Mode learning-loop smoke for terminal-capable agents.",
    ),
    (
        "scripts/launch_skill_mode.sh",
        "runtime",
        "Local API launcher for Skill Mode and adoption verification.",
    ),
    (
        "scripts/study_anything_cli.py",
        "cli",
        "Command-line learning loop and Agent evidence entrypoint.",
    ),
    (
        "scripts/verify_clean_clone_adoption.py",
        "verification",
        "Disposable clean-clone adoption verifier for external-user smoke testing.",
    ),
    (
        "scripts/verify_openai_compatible_gateway.py",
        "verification",
        "Dry-run verifier for the OpenAI-compatible Agent gateway and API registration flow.",
    ),
    (
        "scripts/verify_platform_lesson_flow.py",
        "verification",
        "End-to-end enriched lesson verifier for platform agents and learning-package export.",
    ),
    (
        "scripts/verify_importer_lesson_flow.py",
        "verification",
        "Importer-to-lesson verifier for Learning Context Package, NotebookLM-style, and Obsidian bridge flows.",
    ),
    (
        "scripts/verify_importer_runtime_retrieval_flow.py",
        "verification",
        "Importer-runtime and retrieval verifier for local Agent platform flows.",
    ),
    (
        "scripts/run_external_agent_evals.py",
        "verification",
        "Wrapper for mature external Agent eval runners such as Promptfoo and DeepEval.",
    ),
    (
        "scripts/diagnose_adoption.py",
        "diagnostics",
        "Actionable diagnostics for common external-user adoption blockers.",
    ),
    (
        "evals/promptfoo/agent-eval-artifact.yaml",
        "eval",
        "Promptfoo config for the redacted Agent eval artifact contract.",
    ),
    (
        "evals/deepeval/study_anything_quality_eval.py",
        "eval",
        "DeepEval custom metric adapter for redacted Study Anything quality reports.",
    ),
    (
        "docs/adoption.md",
        "docs",
        "Clean-clone adoption, diagnostics, platform pack, and published-image fallback guide.",
    ),
    (
        "docs/platform-agent-integrations.md",
        "docs",
        "General platform Agent integration guide.",
    ),
    (
        "docs/kimi-agent-gateway.md",
        "docs",
        "Kimi-compatible user-owned HTTP Agent gateway guide.",
    ),
    (
        "docs/agent-eval.md",
        "docs",
        "Agent eval and external evaluation guide.",
    ),
    (
        "docs/plugins.md",
        "docs",
        "Plugin and importer manifest guide.",
    ),
    (
        "fixtures/notebooklm/README.md",
        "fixture",
        "NotebookLM-style import/export fixture notes.",
    ),
    (
        "fixtures/notebooklm/notebooklm-style-context-package.json",
        "fixture",
        "Learning Context Package import fixture covering web, document, video, app, Markdown, and Obsidian sources.",
    ),
    (
        "skills/study-anything/SKILL.md",
        "skill",
        "Repo-local Codex Skill entrypoint for terminal-capable agents.",
    ),
]


class BundleManifestError(RuntimeError):
    """Readable bundle manifest failure."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise BundleManifestError(f"Cannot read {path.relative_to(ROOT)}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise BundleManifestError(f"{path.relative_to(ROOT)} is not valid JSON: {exc}") from exc


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_record(relative_path: str, kind: str, purpose: str) -> dict[str, object]:
    path = ROOT / relative_path
    if not path.exists():
        raise BundleManifestError(f"Bundle file is missing: {relative_path}")
    if any(part in {".env", "data", "__pycache__"} for part in path.parts):
        raise BundleManifestError(f"Bundle file is not safe to distribute: {relative_path}")
    return {
        "path": relative_path,
        "kind": kind,
        "purpose": purpose,
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def build_manifest() -> dict[str, object]:
    source = load_json(SOURCE_MANIFEST)
    if source.get("schema_version") != "study-anything-platform-tools-v1":
        raise BundleManifestError("Source platform manifest schema drifted.")
    file_paths = [path for path, _kind, _purpose in FILES]
    if len(file_paths) != len(set(file_paths)):
        raise BundleManifestError("Bundle file list contains duplicates.")
    return {
        "schema_version": "study-anything-platform-bundle-v1",
        "name": "study-anything-platform-bundle",
        "description": (
            "Deterministic file manifest for distributing Study Anything platform packs, "
            "tool import assets, Skill instructions, and acceptance evidence."
        ),
        "source_manifest": "platform/study-anything-platform-tools.json",
        "source_manifest_sha256": sha256(SOURCE_MANIFEST),
        "platforms": ["codex", "kimi", "workbuddy"],
        "privacy_contract": source.get("privacy_contract", {}),
        "acceptance_commands": [
            "python3 scripts/generate_platform_agent_assets.py --check",
            "python3 scripts/verify_clean_clone_adoption.py --repo .",
            "python3 scripts/verify_platform_ecosystem_packs.py",
            "python3 scripts/generate_platform_bundle_manifest.py --check",
            "python3 scripts/verify_openai_compatible_gateway.py --gateway-only",
            "API_BASE=http://127.0.0.1:8000 python3 scripts/verify_openai_compatible_gateway.py",
            "API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_agent_tools.py",
            "API_BASE=http://127.0.0.1:8000 python3 scripts/verify_importer_lesson_flow.py",
            (
                "STUDY_ANYTHING_RETRIEVAL_BACKEND=memory API_BASE=http://127.0.0.1:8000 "
                "python3 scripts/verify_importer_runtime_retrieval_flow.py"
            ),
            "API_BASE=http://127.0.0.1:8000 python3 scripts/verify_agent_eval_flow.py",
            (
            "API_BASE=http://127.0.0.1:8000 python3 scripts/run_external_agent_evals.py "
            "--tool deepeval --create-session --allow-native-quality-fallback"
        ),
        "API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_lesson_flow.py",
        "python3 scripts/diagnose_adoption.py",
        ],
        "files": [file_record(*item) for item in FILES],
    }


def dump_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_manifest() -> None:
    BUNDLE_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    BUNDLE_MANIFEST.write_text(dump_json(build_manifest()), encoding="utf-8")
    print(f"wrote {BUNDLE_MANIFEST.relative_to(ROOT)}")


def check_manifest() -> None:
    expected = dump_json(build_manifest())
    if not BUNDLE_MANIFEST.exists():
        raise BundleManifestError(
            "Platform bundle manifest is missing. Run "
            "`python3 scripts/generate_platform_bundle_manifest.py`."
        )
    actual = BUNDLE_MANIFEST.read_text(encoding="utf-8")
    if actual != expected:
        raise BundleManifestError(
            "Platform bundle manifest is stale. Run "
            "`python3 scripts/generate_platform_bundle_manifest.py`."
        )
    print("ok    generated platform bundle manifest is up to date")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if the bundle manifest is stale")
    args = parser.parse_args()
    if args.check:
        check_manifest()
    else:
        write_manifest()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"generate_platform_bundle_manifest failed: {exc}", file=sys.stderr)
        sys.exit(1)
