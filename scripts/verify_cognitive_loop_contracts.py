#!/usr/bin/env python3
"""Verify Cognitive Loop contract bootstrap assets."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_MODULE_PATH = (
    ROOT / "apps" / "api" / "study_anything" / "core" / "cognitive_loop_contracts.py"
)


def _load_contract_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "study_anything_cognitive_loop_contracts", CONTRACT_MODULE_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load Cognitive Loop contract module: {CONTRACT_MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


contracts = _load_contract_module()
BOOTSTRAP_SCHEMA_VERSION = contracts.BOOTSTRAP_SCHEMA_VERSION
CognitiveLoopContractError = contracts.CognitiveLoopContractError
validate_all_public_objects = contracts.validate_all_public_objects
validate_contract_files = contracts.validate_contract_files
validate_decision_card = contracts.validate_decision_card
validate_project_event = contracts.validate_project_event


DEFAULT_REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-contracts.json"
RELEASE_VERSION = "v0.3.30-alpha"


def sample_objects() -> dict[str, dict[str, Any]]:
    return {
        "project_event": {
            "event_id": "evt-contract-bootstrap",
            "project_id": "study-anything",
            "actor": "agent",
            "event_type": "schema_changed",
            "summary": "Cognitive Loop public contracts were bootstrapped with local validation.",
            "timestamp": "2026-06-17T00:00:00Z",
            "target": "apps/api/study_anything/core/cognitive_loop_contracts.py",
            "refs": ["git:working-tree", "doc:docs/cognitive-loop-contracts.md"],
            "sensitivity": "internal",
        },
        "decision_card": {
            "decision_id": "dec-contract-bootstrap",
            "project_id": "study-anything",
            "title": "Bootstrap Cognitive Loop contracts before runtime migration",
            "status": "approved",
            "summary": "Add framework-independent contracts without claiming Mastra or watcher runtime is shipped.",
            "event_ids": ["evt-contract-bootstrap"],
            "evidence_refs": [
                "doc:README.md#public-conceptual-contracts",
                "doc:docs/architecture.md#planned-cognitive-loop-core",
                "script:scripts/verify_cognitive_loop_contracts.py",
            ],
            "risk": {
                "level": "medium",
                "score": 0.42,
                "reasons": ["public vocabulary change", "release asset inclusion"],
            },
            "human_mastery_gate": {
                "required": False,
                "status": "not_required",
                "questions": [
                    "Can an operator explain what is shipped versus planned?",
                    "Can an operator run the contract verifier locally?",
                ],
            },
            "verification": {
                "status": "passed",
                "commands": ["python3 scripts/verify_cognitive_loop_contracts.py --check"],
            },
            "rollback": {
                "strategy": "patch_reverse",
                "checkpoint_ref": "git:pre-cognitive-loop-contract-bootstrap",
            },
        },
        "loop_run": {
            "run_id": "loop-contract-bootstrap",
            "project_id": "study-anything",
            "objective": "Turn Cognitive Loop public contracts into local validated files.",
            "status": "succeeded",
            "started_at": "2026-06-17T00:00:00Z",
            "completed_at": "2026-06-17T00:10:00Z",
            "project_event_ids": ["evt-contract-bootstrap"],
            "decision_card_ids": ["dec-contract-bootstrap"],
            "trace_refs": ["local:contract-verifier"],
            "artifact_refs": ["platform/generated/study-anything-cognitive-loop-contracts.json"],
        },
        "mastery_record": {
            "record_id": "mastery-contract-bootstrap",
            "project_id": "study-anything",
            "subject": "Cognitive Loop contracts",
            "level": 0.72,
            "bloom": "understand",
            "evidence_refs": ["dec-contract-bootstrap", "loop-contract-bootstrap"],
            "updated_at": "2026-06-17T00:10:00Z",
        },
        "evolution_report": {
            "report_id": "evo-contract-bootstrap",
            "project_id": "study-anything",
            "status": "approved",
            "proposed_changes": [
                "Add contract validators",
                "Add repo-local .cognitive-loop YAML files",
                "Add release-pack verifier evidence",
            ],
            "decision_card_ids": ["dec-contract-bootstrap"],
            "verification_refs": ["python3 scripts/verify_cognitive_loop_contracts.py --check"],
            "risk_summary": "No runtime daemon, model key custody, or source upload is introduced.",
            "created_at": "2026-06-17T00:10:00Z",
        },
    }


def exercise_failure_modes() -> dict[str, Any]:
    failures: dict[str, Any] = {}
    try:
        validate_project_event(
            {
                "event_id": "evt-secret",
                "project_id": "study-anything",
                "actor": "agent",
                "event_type": "schema_changed",
                "summary": "OPENAI_API_KEY=sk-proj-secretsecretsecretsecret",
                "timestamp": "2026-06-17T00:00:00Z",
            }
        )
    except CognitiveLoopContractError as exc:
        failures["secret_like_event_rejected"] = str(exc)

    try:
        validate_decision_card(
            {
                "decision_id": "dec-unsafe",
                "project_id": "study-anything",
                "title": "Unsafe change",
                "status": "approved",
                "summary": "High risk without a human gate.",
                "event_ids": ["evt-contract-bootstrap"],
                "evidence_refs": ["doc:docs/architecture.md"],
                "risk": {"level": "high", "score": 0.9, "reasons": ["security"]},
                "human_mastery_gate": {"required": False, "status": "not_required"},
                "verification": {"status": "not_run", "commands": []},
                "rollback": {"strategy": "patch_reverse"},
            }
        )
    except CognitiveLoopContractError as exc:
        failures["high_risk_without_gate_rejected"] = str(exc)

    try:
        validate_decision_card(
            {
                "decision_id": "dec-raw",
                "project_id": "study-anything",
                "title": "Raw evidence",
                "status": "proposed",
                "summary": "Should fail because excerpt is private.",
                "event_ids": ["evt-contract-bootstrap"],
                "evidence_refs": ["doc:docs/architecture.md"],
                "risk": {"level": "medium", "score": 0.4, "reasons": ["public contract"]},
                "human_mastery_gate": {"required": False, "status": "not_required"},
                "verification": {"status": "not_run", "commands": []},
                "rollback": {"strategy": "patch_reverse"},
                "excerpt": "raw source text should not appear",
            }
        )
    except CognitiveLoopContractError as exc:
        failures["raw_excerpt_field_rejected"] = str(exc)

    required = {
        "secret_like_event_rejected",
        "high_risk_without_gate_rejected",
        "raw_excerpt_field_rejected",
    }
    missing = sorted(required - set(failures))
    if missing:
        raise RuntimeError(f"Expected Cognitive Loop failure modes were not covered: {missing}")
    return failures


def build_report(root: Path) -> dict[str, Any]:
    contract_files = [report.public_dict() for report in validate_contract_files(root)]
    objects = validate_all_public_objects(sample_objects())
    failure_modes = exercise_failure_modes()
    return {
        "schema_version": BOOTSTRAP_SCHEMA_VERSION,
        "status": "pass",
        "version": RELEASE_VERSION,
        "contract_files": contract_files,
        "object_contracts": {
            name: payload["schema_version"] for name, payload in objects.items()
        },
        "privacy": {
            "raw_source_text_included": False,
            "learner_answers_included": False,
            "agent_endpoints_included": False,
            "real_model_keys_included": False,
            "secret_like_values_rejected": True,
        },
        "risk": {
            "high_risk_requires_human_mastery_gate": True,
            "default_mode": "read_only",
            "runtime_daemon_started": False,
            "mastra_runtime_claimed": False,
        },
        "failure_modes": failure_modes,
        "acceptance": {
            "minimum_command": "python3 scripts/verify_cognitive_loop_contracts.py --check",
            "pack_asset": "platform/generated/study-anything-cognitive-loop-contracts.json",
            "contract_directory": ".cognitive-loop",
        },
    }


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", default=str(DEFAULT_REPORT))
    args = parser.parse_args()

    output = Path(args.output)
    report = build_report(ROOT)
    serialized = dump_json(report)
    if args.write:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
    if args.check:
        if not output.is_file():
            raise SystemExit(f"Cognitive Loop contract report is missing: {output}")
        current = output.read_text(encoding="utf-8")
        if current != serialized:
            raise SystemExit(
                "Cognitive Loop contract report is out of date. "
                "Run: python3 scripts/verify_cognitive_loop_contracts.py --write"
            )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
