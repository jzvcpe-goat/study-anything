#!/usr/bin/env python3
"""Verify the metadata-only Review Agent policy gate."""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT_FIXTURE_DIR = ROOT / "fixtures" / "review-agent"
BAD_BUNDLE_DIR = ROOT / "fixtures" / "review-agent-acceptance-bundles" / "raw-diff-leak"
BUNDLE_CLI_PATH = ROOT / "scripts" / "cognitive_loop_review_agent_acceptance_bundle.py"
POLICY_GATE_CLI_PATH = ROOT / "scripts" / "cognitive_loop_review_agent_policy_gate.py"
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-review-agent-policy-gate.json"

SCHEMA_VERSION = "cognitive-loop-review-agent-policy-gate-verification-v1"
GATE_SCHEMA_VERSION = "cognitive-loop-review-agent-policy-gate-v1"
REPORT_FIXTURES = ("approved.json", "needs-review.json", "needs-fix.json")
POLICIES = ("advisory", "soft", "strict")
FIXED_GENERATED_AT = "2026-06-18T00:00:00+00:00"
EXPECTED_EXIT_CODES = {
    "advisory": {
        "approved": 0,
        "needs-review": 0,
        "needs-fix": 0,
    },
    "soft": {
        "approved": 0,
        "needs-review": 0,
        "needs-fix": 2,
    },
    "strict": {
        "approved": 0,
        "needs-review": 2,
        "needs-fix": 2,
    },
}
PRIVATE_NEEDLES = (
    "diff --git",
    "@@ ",
    "OPENAI_API_KEY=",
    "MOONSHOT_API_KEY=",
    "sk-proj-",
    "bearer ",
    "http://private-agent.local",
    "subprocess.run(user_command",
    "hidden chain-of-thought",
)


class ReviewAgentPolicyGateVerificationError(RuntimeError):
    """Readable Review Agent policy gate verification failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReviewAgentPolicyGateVerificationError(message)


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ReviewAgentPolicyGateVerificationError(f"Cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def reject_private_text(value: Any, *, label: str) -> None:
    serialized = value if isinstance(value, str) else dump_json(value)
    lowered = serialized.lower()
    leaked = [needle for needle in PRIVATE_NEEDLES if needle.lower() in lowered]
    if leaked:
        raise ReviewAgentPolicyGateVerificationError(f"{label} leaked private Review Agent text: {leaked}")


def build_bundle_for_fixture(bundle_cli: Any, fixture_name: str, output_root: Path) -> Path:
    fixture_id = fixture_name.removesuffix(".json")
    output_dir = output_root / fixture_id / "review-agent-acceptance"
    args = argparse.Namespace(
        report=str(REPORT_FIXTURE_DIR / fixture_name),
        output_dir=str(output_dir),
        provider_id=f"policy-gate-{fixture_id}-review-agent",
        provider_label=f"Policy gate fixture {fixture_id} Review Agent",
        execution_surface="ci",
        pr_ref=f"PR-fixture-{fixture_id}",
        commit_sha=f"sha-fixture-{fixture_id}",
        base_ref="main",
        head_ref=f"codex/fixture-{fixture_id}",
        generated_at=FIXED_GENERATED_AT,
        validation_command="python3 scripts/cognitive_loop_review_agent_handoff.py validate --report REVIEW_AGENT_REPORT.json",
    )
    bundle_cli.build_bundle(args)
    bundle_cli.validate_bundle_dir(output_dir)
    return output_dir


def evaluate_bundle(policy_cli: Any, bundle_dir: Path, *, policy: str) -> dict[str, Any]:
    args = argparse.Namespace(
        bundle_dir=str(bundle_dir),
        receipt=None,
        policy=policy,
        output=None,
        generated_at=FIXED_GENERATED_AT,
    )
    payload = policy_cli.evaluate(args)
    summary = policy_cli.validate_gate_payload(payload)
    reject_private_text(payload, label=f"{bundle_dir.name} {policy} policy gate")
    return {
        "decision": summary["decision"],
        "status": summary["status"],
        "exit_code": summary["exit_code"],
    }


def evaluate_receipt(policy_cli: Any, receipt_path: Path, *, policy: str) -> dict[str, Any]:
    args = argparse.Namespace(
        bundle_dir=None,
        receipt=str(receipt_path),
        policy=policy,
        output=None,
        generated_at=FIXED_GENERATED_AT,
    )
    payload = policy_cli.evaluate(args)
    summary = policy_cli.validate_gate_payload(payload)
    reject_private_text(payload, label=f"{receipt_path.name} {policy} policy gate")
    return {
        "decision": summary["decision"],
        "status": summary["status"],
        "exit_code": summary["exit_code"],
    }


def validate_cli_exit_codes(bundle_dir: Path) -> dict[str, Any]:
    output_path = bundle_dir / "policy-gate-soft.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(POLICY_GATE_CLI_PATH),
            "--bundle-dir",
            str(bundle_dir),
            "--policy",
            "soft",
            "--output",
            str(output_path),
            "--generated-at",
            FIXED_GENERATED_AT,
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    require(completed.returncode == 2, f"needs-fix soft policy should exit 2, got {completed.returncode}")
    require(payload["schema_version"] == GATE_SCHEMA_VERSION, "CLI output schema drifted.")
    require(payload["policy"] == "soft", "CLI output policy drifted.")
    require(payload["decision_summary"]["decision"] == "needs-fix", "CLI output decision drifted.")
    require(payload["exit_code"] == 2, "CLI payload exit_code drifted.")
    reject_private_text(completed.stdout + dump_json(payload), label="policy gate CLI needs-fix output")
    return {
        "policy": payload["policy"],
        "decision": payload["decision_summary"]["decision"],
        "returncode": completed.returncode,
        "output_written": output_path.name,
    }


def validate_negative_bundle(policy_cli: Any) -> str:
    try:
        args = argparse.Namespace(
            bundle_dir=str(BAD_BUNDLE_DIR),
            receipt=None,
            policy="strict",
            output=None,
            generated_at=FIXED_GENERATED_AT,
        )
        policy_cli.evaluate(args)
    except Exception as exc:
        return str(exc)
    raise ReviewAgentPolicyGateVerificationError("Raw-diff leak bundle unexpectedly passed policy gate.")


def validate_docs() -> dict[str, str]:
    docs = {
        "docs/cognitive-loop-code-review.md": [
            "cognitive_loop_review_agent_policy_gate.py",
            "verify_cognitive_loop_review_agent_policy_gate.py --check",
        ],
        "docs/eval-frameworks.md": [
            "cognitive-loop-review-agent-policy-gate-v1",
            "verify_cognitive_loop_review_agent_policy_gate.py --check",
        ],
        "evals/README.md": [
            "verify_cognitive_loop_review_agent_policy_gate.py --check",
        ],
        ".cognitive-loop/evals.yaml": [
            "cognitive-loop.review-agent-policy-gate",
            "python3 scripts/verify_cognitive_loop_review_agent_policy_gate.py --check",
        ],
        "scripts/release_check.sh": [
            "scripts/verify_cognitive_loop_review_agent_policy_gate.py --check",
        ],
        "platform/packs/kimi/README.md": [
            "cognitive_loop_review_agent_policy_gate.py",
            "verify_cognitive_loop_review_agent_policy_gate.py --check",
        ],
        "platform/packs/codex/README.md": [
            "cognitive_loop_review_agent_policy_gate.py",
            "verify_cognitive_loop_review_agent_policy_gate.py --check",
        ],
        "platform/packs/workbuddy/README.md": [
            "cognitive_loop_review_agent_policy_gate.py",
            "verify_cognitive_loop_review_agent_policy_gate.py --check",
        ],
        "scripts/generate_platform_bundle_manifest.py": [
            "platform/generated/study-anything-cognitive-loop-review-agent-policy-gate.json",
        ],
        "scripts/generate_platform_adoption_pack.py": [
            "scripts/cognitive_loop_review_agent_policy_gate.py",
            "scripts/verify_cognitive_loop_review_agent_policy_gate.py",
        ],
    }
    checked: dict[str, str] = {}
    for relative, needles in docs.items():
        text = (ROOT / relative).read_text(encoding="utf-8")
        missing = [needle for needle in needles if needle not in text]
        require(not missing, f"{relative} missing Review Agent policy gate references: {missing}")
        checked[relative] = "pass"
    return checked


def validate_platform_packs() -> dict[str, str]:
    required_assets = {
        "scripts/cognitive_loop_review_agent_policy_gate.py",
        "scripts/verify_cognitive_loop_review_agent_policy_gate.py",
        "platform/generated/study-anything-cognitive-loop-review-agent-policy-gate.json",
    }
    required_command = "python3 scripts/verify_cognitive_loop_review_agent_policy_gate.py --check"
    required_evidence = (
        "cognitive_loop_review_agent_policy_gate.schema_version == "
        "cognitive-loop-review-agent-policy-gate-verification-v1"
    )
    checked: dict[str, str] = {}
    for pack_id in ("codex", "kimi", "workbuddy"):
        pack_path = ROOT / "platform" / "packs" / pack_id / "pack.json"
        pack = json.loads(pack_path.read_text(encoding="utf-8"))
        assets = set(pack.get("import_assets", []))
        commands = set(pack.get("local_verification_commands", []))
        evidence = set(pack.get("acceptance_evidence", []))
        missing_assets = sorted(required_assets - assets)
        require(not missing_assets, f"{pack_path.relative_to(ROOT)} missing policy gate assets: {missing_assets}")
        require(required_command in commands, f"{pack_path.relative_to(ROOT)} missing policy gate command.")
        require(required_evidence in evidence, f"{pack_path.relative_to(ROOT)} missing policy gate evidence.")
        checked[pack_id] = "pass"
    return checked


def build_report() -> dict[str, Any]:
    bundle_cli = load_module(BUNDLE_CLI_PATH, "study_anything_review_agent_acceptance_bundle")
    policy_cli = load_module(POLICY_GATE_CLI_PATH, "study_anything_review_agent_policy_gate")
    with tempfile.TemporaryDirectory(prefix="study-anything-review-agent-policy-gate-") as tmp_name:
        output_root = Path(tmp_name)
        bundle_dirs = {fixture: build_bundle_for_fixture(bundle_cli, fixture, output_root) for fixture in REPORT_FIXTURES}
        bundle_matrix: dict[str, dict[str, dict[str, Any]]] = {}
        receipt_matrix: dict[str, dict[str, dict[str, Any]]] = {}
        for fixture, bundle_dir in bundle_dirs.items():
            bundle_matrix[fixture] = {
                policy: evaluate_bundle(policy_cli, bundle_dir, policy=policy) for policy in POLICIES
            }
            receipt_path = bundle_dir / "review-agent-ci-receipt.json"
            receipt_matrix[fixture] = {
                policy: evaluate_receipt(policy_cli, receipt_path, policy=policy) for policy in POLICIES
            }
        cli_exit = validate_cli_exit_codes(bundle_dirs["needs-fix.json"])

    observed = {
        policy: {
            fixture.removesuffix(".json"): bundle_matrix[fixture][policy]["exit_code"]
            for fixture in REPORT_FIXTURES
        }
        for policy in POLICIES
    }
    require(observed == EXPECTED_EXIT_CODES, f"Policy exit matrix drifted: {observed}")
    require(bundle_matrix == receipt_matrix, "Bundle and receipt policy gate behavior diverged.")
    negative = {"raw-diff-leak": validate_negative_bundle(policy_cli)}
    docs = validate_docs()
    platform_packs = validate_platform_packs()
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "gate_schema_version": GATE_SCHEMA_VERSION,
        "cli": "scripts/cognitive_loop_review_agent_policy_gate.py",
        "policy_matrix": observed,
        "bundle_matrix": bundle_matrix,
        "receipt_matrix": receipt_matrix,
        "cli_exit_check": cli_exit,
        "negative_bundles": negative,
        "docs": docs,
        "platform_packs": platform_packs,
        "quality_gates": {
            "policy_coverage": list(POLICIES),
            "decision_path_coverage": ["approved", "needs-fix", "needs-review"],
            "bundle_and_receipt_parity": "pass",
            "nonzero_exit_coverage": "pass",
            "metadata_only_gate": "pass",
            "privacy_leak_rejection": "pass",
        },
        "privacy": {
            "raw_diff_included": False,
            "file_bodies_included": False,
            "finding_evidence_included": False,
            "report_summary_included": False,
            "agent_endpoint_secrets_included": False,
            "real_model_keys_included": False,
            "hidden_chain_of_thought_included": False,
            "safe_to_attach_to_pr": True,
        },
        "acceptance": {
            "advisory_command": "python3 scripts/cognitive_loop_review_agent_policy_gate.py --bundle-dir /tmp/review-agent-acceptance --policy advisory",
            "soft_command": "python3 scripts/cognitive_loop_review_agent_policy_gate.py --bundle-dir /tmp/review-agent-acceptance --policy soft",
            "strict_command": "python3 scripts/cognitive_loop_review_agent_policy_gate.py --bundle-dir /tmp/review-agent-acceptance --policy strict",
            "minimum_command": "python3 scripts/verify_cognitive_loop_review_agent_policy_gate.py --check",
            "generated_report": "platform/generated/study-anything-cognitive-loop-review-agent-policy-gate.json",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", default=str(REPORT))
    args = parser.parse_args()

    output = Path(args.output)
    report = build_report()
    serialized = dump_json(report)
    if args.write:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
    if args.check:
        if not output.is_file():
            raise SystemExit(f"Cognitive Loop Review Agent policy gate report is missing: {output}")
        current = output.read_text(encoding="utf-8")
        if current != serialized:
            raise SystemExit(
                "Cognitive Loop Review Agent policy gate report is out of date. "
                "Run: python3 scripts/verify_cognitive_loop_review_agent_policy_gate.py --write"
            )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReviewAgentPolicyGateVerificationError as exc:
        raise SystemExit(f"error: {exc}") from exc
