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
PUBLIC_DEFINITION = (
    "Delivery Clearance does not prove that AI is always correct. It proves why this\n"
    "delivery may move forward, to whom, for what purpose, within what limits, and under\n"
    "whose responsibility."
)
PUBLIC_SLOGAN = "未经放行，不得交付。"
PUBLIC_DEFINITION_ZH = (
    "AI 交付放行协议不证明 AI 永远正确；它证明这次交付为什么可以继续向前、可以交给谁、\n"
    "可以用于什么、受到哪些限制，以及由谁承担责任。"
)

REQUIRED_TEXT: dict[str, tuple[str, ...]] = {
    "README.md": (
        "# Delivery Clearance",
        "## AI Delivery Clearance Protocol / AI 交付放行协议",
        PUBLIC_SLOGAN,
        PUBLIC_DEFINITION,
        PUBLIC_DEFINITION_ZH,
        "Delivery Clearance Reference Harness",
        "Study Anything is the Human",
        "Reconstruction / Learning Adapter. Cognitive Loop is an internal evidence",
        "Cognitive Loop is an internal evidence",
        "The repository and Python distribution retain the historical `study-anything` name,",
        "scripts/verify_cbb_positioning.py --check",
    ),
    "docs/product-positioning.md": (
        "Delivery Clearance is the public product identity",
        PUBLIC_DEFINITION,
        PUBLIC_DEFINITION_ZH,
        PUBLIC_SLOGAN,
        "Cognitive Load Contract",
        "Controlled Release, Not Permanent Restraint",
        "Study Anything Adapter",
        "Cognitive Loop | Internal evidence/evolution workflow",
    ),
    "docs/protocol.md": (
        "# AI Delivery Clearance Protocol",
        PUBLIC_DEFINITION,
        PUBLIC_DEFINITION_ZH,
        PUBLIC_SLOGAN,
        "No receipt, no release.",
        "Stable Trust Kernel",
        "Adaptive Evolution Layer",
    ),
    "docs/trust-model.md": (
        "Last Protocol Before Responsibility Transfer",
        "Trust is scoped, stateful, time-bound, evidence-backed, and reversible.",
        "Equal-Weight Dual Loop",
        "The protocol must distrust itself.",
        "Trust Growth And Degradation",
    ),
    "docs/architecture.md": (
        "Delivery Clearance is protocol-first.",
        "AI Delivery Clearance Protocol is the final protocol before an AI delivery",
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
        "Delivery Clearance | Public product identity",
        "AI Delivery Clearance Protocol | Open protocol",
        "CBB / `cbb.*` | Existing Protocol v1 schema and implementation namespace | Compatibility only",
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
    "docs/cbb-protocol-v1-scenarios-and-qualification.md": (
        "AI Delivery Clearance Protocol is the final open protocol before an AI delivery",
        "Minimum Reconstructable Unit",
        "Capability Profiles",
        "production-candidate-blocked",
        "regulated-or-irreversible-blocked",
    ),
    "docs/cbb-protocol-v1-outcomes.md": (
        "cbb.delivery-outcome-receipt.v1",
        "maintain_current_ceiling",
        "narrow_scope",
        "freeze_recipe",
        "revoke_clearance",
        "never increases scope",
    ),
    "docs/cbb-protocol-v1-agentic-evolution.md": (
        "cbb.evolution-gate-receipt.v1",
        "supporting evidence only",
        "Memory is evidence, not policy or truth.",
        "approved_for_local_candidate",
        "automatic_apply_allowed = false",
    ),
    "docs/adapters/study-anything.md": (
        "Human Reconstruction / Learning Adapter",
        "not the protocol, the Trust Kernel, or the top-level product identity.",
        "The mapping may narrow or expire a claim. It may never increase delivery scope.",
    ),
    "scripts/release_check.sh": (
        "Delivery Clearance protocol release check",
        "scripts/verify_cbb_positioning.py --check",
        "scripts/verify_cbb_protocol_contracts.py --check",
        "scripts/verify_cbb_v1_scenarios.py --check",
        "scripts/verify_cbb_v1_qualification.py --check",
        "scripts/verify_cbb_v1_outcomes.py --check",
        "scripts/verify_cbb_agentic_tool_boundary.py --check",
        "scripts/verify_cbb_memory_quarantine.py --check",
        "scripts/verify_cbb_evolution_gate.py --check",
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


def verify_public_first_view() -> dict[str, Any]:
    lines = read_text("README.md").splitlines()
    first_view = "\n".join(lines[:27])
    if PUBLIC_DEFINITION not in first_view or PUBLIC_SLOGAN not in first_view:
        raise PositioningError(
            "README first view does not lead with the Delivery Clearance contract."
        )
    obsolete_first_view = (
        "learning system",
        "learning product",
        "plugin ecosystem",
        "Cognitive Loop System",
        "Cognitive Black Box",
        "CBB Protocol",
        "CBB is",
        "CBB ",
    )
    findings = [term for term in obsolete_first_view if term in first_view]
    if findings:
        raise PositioningError(
            f"README first view leaks obsolete product framing: {findings}"
        )
    return {
        "line_window": 27,
        "delivery_clearance_definition_present": True,
        "no_clearance_no_delivery_present": True,
        "obsolete_product_terms": [],
        "human_review_contract": "bounded boundary decisions, not exhaustive rereading",
    }


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
        "Delivery Clearance: open, local-first AI Delivery Clearance Protocol and "
        "reference harness."
    )
    if f'description = "{expected_description}"' not in pyproject:
        raise PositioningError("pyproject description does not match the canonical CBB position.")
    if 'authors = [{ name = "Delivery Clearance contributors" }]' not in pyproject:
        raise PositioningError("pyproject authors still use the obsolete product identity.")

    api_source = read_text("apps/api/study_anything/api/main.py")
    api_title = "Delivery Clearance: Study Anything Adapter"
    if api_title not in api_source:
        raise PositioningError("FastAPI title does not expose Delivery Clearance plus adapter boundary.")

    artifact_source = read_text("apps/api/study_anything/core/cognitive_loop_contracts.py")
    if "<h1 class=\"brand\">Delivery Clearance</h1>" not in artifact_source:
        raise PositioningError("Generated artifact branding is not Delivery Clearance.")

    return {
        "distribution_name": "study-anything",
        "distribution_name_is_compatibility_only": True,
        "description": expected_description,
        "api_title": api_title,
        "generated_artifact_brand": "Delivery Clearance",
    }


def build_report() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "canonical_name": "Delivery Clearance",
        "canonical_protocol_name": "AI Delivery Clearance Protocol",
        "reference_implementation": "Delivery Clearance Reference Harness",
        "study_anything_role": "Human Reconstruction / Learning Adapter",
        "cognitive_loop_role": "internal evidence and evolution workflow",
        "required_text": verify_required_text(),
        "public_first_view": verify_public_first_view(),
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
