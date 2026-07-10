#!/usr/bin/env python3
"""Verify the protocol-first CBB positioning and compatibility boundary."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "cbb-positioning-verification-v1"

REQUIRED_TEXT: dict[str, tuple[str, ...]] = {
    "README.md": (
        "# Cognitive Black Box Protocol / 认知黑箱协议",
        "open, local-first receipt protocol",
        "CBB Reference Harness",
        "Study Anything is the Human",
        "Reconstruction / Learning Adapter. Cognitive Loop is an internal evidence",
        "Cognitive Loop is an internal evidence",
        "The repository and Python distribution retain the historical `study-anything` name",
        "scripts/verify_cbb_positioning.py --check",
    ),
    "docs/product-positioning.md": (
        "Cognitive Black Box Protocol is an open protocol",
        "Controlled Release, Not Permanent Restraint",
        "Study Anything Adapter",
        "Cognitive Loop | Internal evidence/evolution workflow",
    ),
    "docs/protocol.md": (
        "# Cognitive Black Box Protocol",
        "No receipt, no release.",
        "Stable Trust Kernel",
        "Adaptive Evolution Layer",
    ),
    "docs/trust-model.md": (
        "Trust is scoped, stateful, time-bound, evidence-backed, and reversible.",
        "Equal-Weight Dual Loop",
        "The protocol must distrust itself.",
        "Trust Growth And Degradation",
    ),
    "docs/architecture.md": (
        "Cognitive Black Box is protocol-first.",
        "Deterministic Trust Kernel",
        "Physical Isolation",
        "Current Reference Implementation Map",
    ),
    "docs/roadmap.md": (
        "M0: Positioning And Compatibility Boundary",
        "M1: Canonical Protocol v1 Core",
        "M4: Outcome Receipts And Trust Degradation",
        "M6: Conformance And Open Governance",
    ),
    "docs/naming-and-compatibility.md": (
        "Compatibility-Only Identifiers",
        "Banned Current Framing",
        "Technical Rename Criteria",
    ),
    "docs/cbb-protocol-v1-development-plan.md": (
        "Target V1 Schema Set",
        "PR 1: Canonical Models And Compatibility Map",
        "Quality Audit After Every PR",
        "Next Codex Goal",
    ),
    "docs/adapters/study-anything.md": (
        "Human Reconstruction / Learning Adapter",
        "not the protocol, the Trust Kernel, or the top-level product identity.",
        "The mapping may narrow or expire a claim. It may never increase delivery scope.",
    ),
    "scripts/release_check.sh": (
        "scripts/verify_cbb_positioning.py --check",
        "scripts/verify_cbb_protocol_contracts.py --check",
    ),
}

BANNED_CURRENT_FRAMING = (
    "Cognitive Loop System",
    "Neural Sync",
    "Neural Publish",
    "Neural Teams",
    "Study Anything started as a learning system",
    "Study Anything is currently a public self-host Alpha",
    "Study Anything can be used as an API/Skill-first learning system",
    "Study Anything is the local learning workflow kernel",
)

SCAN_ROOTS = (
    "README.md",
    "docs",
    "apps/api/study_anything",
    "scripts",
    "platform/generated",
    "platform/mastra-runtime",
    "plugins/study-anything",
    "pyproject.toml",
)

EXCLUDED_PREFIXES = (
    "docs/release-notes/",
    "docs/quality-audits/",
)

ALLOWED_BANNED_TERM_FILES = {
    "docs/naming-and-compatibility.md",
    "scripts/verify_cbb_positioning.py",
}
TEXT_SUFFIXES = {".md", ".py", ".sh", ".toml", ".json", ".yaml", ".yml", ".ts"}


class PositioningError(RuntimeError):
    """Raised when the current repository framing violates the CBB contract."""


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def read_text(relative_path: str) -> str:
    path = ROOT / relative_path
    if not path.is_file():
        raise PositioningError(f"Required positioning file is missing: {relative_path}")
    return path.read_text(encoding="utf-8")


def iter_current_text_files() -> list[Path]:
    files: set[Path] = set()
    for entry in SCAN_ROOTS:
        path = ROOT / entry
        if path.is_file():
            files.add(path)
            continue
        if not path.is_dir():
            raise PositioningError(f"Positioning scan root is missing: {entry}")
        for candidate in path.rglob("*"):
            if not candidate.is_file() or candidate.suffix not in TEXT_SUFFIXES:
                continue
            rel = relative(candidate)
            if any(rel.startswith(prefix) for prefix in EXCLUDED_PREFIXES):
                continue
            files.add(candidate)
    return sorted(files)


def verify_required_text() -> dict[str, list[str]]:
    verified: dict[str, list[str]] = {}
    for path, needles in REQUIRED_TEXT.items():
        text = read_text(path)
        missing = [needle for needle in needles if needle not in text]
        if missing:
            raise PositioningError(f"{path} is missing canonical positioning text: {missing}")
        verified[path] = list(needles)
    return verified


def verify_banned_framing() -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    scanned = iter_current_text_files()
    for path in scanned:
        rel = relative(path)
        if rel in ALLOWED_BANNED_TERM_FILES:
            continue
        text = path.read_text(encoding="utf-8")
        for term in BANNED_CURRENT_FRAMING:
            if term in text:
                findings.append({"path": rel, "term": term})
    if findings:
        raise PositioningError(f"Obsolete current positioning remains: {findings}")
    return {
        "scanned_file_count": len(scanned),
        "banned_terms": list(BANNED_CURRENT_FRAMING),
        "allowed_definition_files": sorted(ALLOWED_BANNED_TERM_FILES),
        "findings": [],
    }


def verify_package_metadata() -> dict[str, Any]:
    pyproject = read_text("pyproject.toml")
    if "[project]" not in pyproject:
        raise PositioningError("pyproject.toml is missing [project].")
    if 'name = "study-anything"' not in pyproject:
        raise PositioningError("Historical Python distribution name must remain study-anything.")
    expected_description = (
        "Open, local-first protocol and reference harness for scoped AI delivery trust."
    )
    if f'description = "{expected_description}"' not in pyproject:
        raise PositioningError("pyproject description does not match the canonical CBB position.")
    if 'authors = [{ name = "Cognitive Black Box Protocol contributors" }]' not in pyproject:
        raise PositioningError("pyproject authors still use the obsolete product identity.")

    api_source = read_text("apps/api/study_anything/api/main.py")
    api_title = "Cognitive Black Box Protocol: Study Anything Adapter"
    if api_title not in api_source:
        raise PositioningError("FastAPI title does not expose CBB Protocol plus adapter boundary.")

    artifact_source = read_text("apps/api/study_anything/core/cognitive_loop_contracts.py")
    if "<h1 class=\"brand\">Cognitive Black Box Protocol</h1>" not in artifact_source:
        raise PositioningError("Generated Cognitive Loop artifact branding is not CBB Protocol.")

    return {
        "distribution_name": "study-anything",
        "distribution_name_is_compatibility_only": True,
        "description": expected_description,
        "api_title": api_title,
        "generated_artifact_brand": "Cognitive Black Box Protocol",
    }


def build_report() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "canonical_name": "Cognitive Black Box Protocol",
        "reference_implementation": "CBB Reference Harness",
        "study_anything_role": "Human Reconstruction / Learning Adapter",
        "cognitive_loop_role": "internal evidence and evolution workflow",
        "required_text": verify_required_text(),
        "legacy_leakage": verify_banned_framing(),
        "package_metadata": verify_package_metadata(),
        "claim_boundary": {
            "does_not_rename_compatibility_identifiers": True,
            "does_not_claim_production_trust": True,
            "does_not_claim_independent_audit_completion": True,
            "does_not_make_ai_review_a_trust_root": True,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify current repository state.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.check:
        print("Run with --check.", file=sys.stderr)
        return 2
    try:
        report = build_report()
    except (OSError, PositioningError) as exc:
        print(f"verify_cbb_positioning failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
