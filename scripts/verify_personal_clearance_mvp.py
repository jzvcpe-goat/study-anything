#!/usr/bin/env python3
"""Verify the personal-local Delivery Clearance MVP and generated contracts."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
from typing import Any

from pydantic import ValidationError


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from study_anything.cbb.personal.audit import (  # noqa: E402
    ARTIFACT_RELATIVE_DIR,
    CONFIG_RELATIVE_PATH,
    PersonalClearanceError,
    audit_project,
    default_config,
    load_config,
    verify_project_clearance,
    write_audit_artifacts,
)
from study_anything.cbb.personal.models import (  # noqa: E402
    PERSONAL_CLEARANCE_MODELS,
    PersonalClearanceConfigV1,
)
from study_anything.cbb.protocol.canonical import (  # noqa: E402
    assert_safe_metadata,
    pretty_json,
    schema_text,
)
from study_anything.cbb.protocol.models import DeliveryScope  # noqa: E402


REPORT_PATH = Path("platform/generated/study-anything-personal-clearance-mvp.json")
FIXTURE_ROOT = Path("fixtures/personal-clearance")
SCHEMA_ROOT = Path("platform/schemas/cbb")
EVALUATED_AT = "2026-07-11T12:00:00Z"
VERIFIED_AT = "2026-07-11T12:05:00Z"


def _complete_config(project_id: str = "personal-clearance-fixture") -> PersonalClearanceConfigV1:
    payload = default_config(project_id).model_dump(mode="json")
    payload.update(
        {
            "purpose": "Audit one exact local development candidate.",
            "non_goals": ["No external delivery, customer handoff, or production use."],
            "critical_failure_path": "A required local verification can fail.",
            "rollback_trigger": "Any failed check or unexpected project-state mutation.",
            "rollback_strategy": "Discard the candidate and return to the last Git state.",
        }
    )
    return PersonalClearanceConfigV1.model_validate(payload)


def _write_config(root: Path, config: PersonalClearanceConfigV1) -> None:
    config_path = root / CONFIG_RELATIVE_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(pretty_json(config), encoding="utf-8")
    (config_path.parent / ".gitignore").write_text("/artifacts/\n", encoding="utf-8")


def _git_repo() -> tempfile.TemporaryDirectory[str]:
    temporary = tempfile.TemporaryDirectory()
    root = Path(temporary.name).resolve()
    completed = subprocess.run(
        ["git", "init"],
        cwd=root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        temporary.cleanup()
        raise RuntimeError("could not create verifier Git fixture")
    return temporary


def _expect_error(action: Any, text: str) -> bool:
    try:
        action()
    except (PersonalClearanceError, ValidationError, ValueError) as exc:
        return text in str(exc)
    return False


def _dynamic_cases() -> dict[str, bool]:
    cases: dict[str, bool] = {}

    help_result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "personal_clearance.py"), "--help"],
        cwd=ROOT,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    cases["repository_cli_help_succeeds"] = (
        help_result.returncode == 0 and "init" in help_result.stdout
    )
    time_override = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "personal_clearance.py"),
            "verify",
            "--verified-at",
            VERIFIED_AT,
        ],
        cwd=ROOT,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    cases["public_cli_rejects_time_override"] = (
        time_override.returncode == 2 and "unrecognized arguments" in time_override.stderr
    )
    project_metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    cases["installed_console_entrypoint_declared"] = (
        project_metadata.get("project", {}).get("scripts", {}).get("delivery-clearance")
        == "study_anything.cbb.personal.cli:main"
    )

    with _git_repo() as directory:
        root = Path(directory).resolve()
        _write_config(root, _complete_config())
        _, allowed = audit_project(
            root,
            execute_checks=True,
            accept_responsibility=True,
            evaluated_at=EVALUATED_AT,
        )
        write_audit_artifacts(root, allowed)
        verified = verify_project_clearance(root, verified_at=VERIFIED_AT)
        cases["complete_self_audit_allows_personal_local"] = (
            allowed.receipt.status == "allow"
            and allowed.receipt.approved_scope == DeliveryScope.PERSONAL_LOCAL
            and verified["status"] == "pass"
        )
        cases["personal_receipt_disclaims_independent_review"] = (
            not allowed.receipt.independent_review_performed
            and "independent review" in allowed.receipt.claim_boundary.not_claimed
        )
        cases["artifacts_do_not_disclose_local_absolute_path"] = all(
            str(root) not in path.read_text(encoding="utf-8")
            for path in (root / ARTIFACT_RELATIVE_DIR).glob("*.json")
        )

        _, no_acceptance = audit_project(
            root,
            execute_checks=True,
            accept_responsibility=False,
            evaluated_at=EVALUATED_AT,
        )
        cases["missing_run_specific_responsibility_blocks"] = (
            no_acceptance.receipt.status == "needs_evidence"
            and no_acceptance.receipt.approved_scope == DeliveryScope.BLOCKED
        )

        _, no_checks = audit_project(
            root,
            execute_checks=False,
            accept_responsibility=True,
            evaluated_at=EVALUATED_AT,
        )
        cases["unexecuted_checks_block"] = (
            no_checks.receipt.status == "needs_evidence"
            and "configured_checks" in no_checks.receipt.missing_evidence_types
        )

        (root / "state-change.txt").write_text("changed\n", encoding="utf-8")
        cases["state_change_invalidates_receipt"] = _expect_error(
            lambda: verify_project_clearance(root, verified_at=VERIFIED_AT),
            "project_state_current",
        )

    with _git_repo() as directory:
        root = Path(directory).resolve()
        payload = _complete_config().model_dump(mode="json")
        payload["checks"] = [
            {
                "check_id": "mutating-check",
                "argv": [
                    "python3",
                    "-c",
                    "from pathlib import Path; Path('mutation.txt').write_text('changed')",
                ],
                "timeout_seconds": 30,
                "required": True,
            }
        ]
        _write_config(root, PersonalClearanceConfigV1.model_validate(payload))
        _, mutated = audit_project(
            root,
            execute_checks=True,
            accept_responsibility=True,
            evaluated_at=EVALUATED_AT,
        )
        cases["check_mutation_is_hard_deny"] = (
            mutated.receipt.status == "block"
            and "hard_deny:audit_check_mutated_project" in mutated.receipt.reasons
        )

    with _git_repo() as directory:
        root = Path(directory).resolve()
        _write_config(root, _complete_config())
        _, allowed = audit_project(
            root,
            execute_checks=True,
            accept_responsibility=True,
            evaluated_at=EVALUATED_AT,
        )
        write_audit_artifacts(root, allowed)
        receipt_path = root / ARTIFACT_RELATIVE_DIR / "personal-clearance-receipt.json"
        receipt_payload = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt_payload["policy_digest_sha256"] = "0" * 64
        receipt_path.write_text(json.dumps(receipt_payload), encoding="utf-8")
        cases["receipt_tamper_is_rejected"] = _expect_error(
            lambda: verify_project_clearance(root, verified_at=VERIFIED_AT),
            "policy_digest_matches",
        )

    expanded = deepcopy(_complete_config().model_dump(mode="json"))
    expanded["maximum_scope"] = "controlled_customer_handoff"
    cases["scope_expansion_is_schema_rejected"] = _expect_error(
        lambda: PersonalClearanceConfigV1.model_validate(expanded),
        "maximum_scope",
    )

    with _git_repo() as directory:
        root = Path(directory).resolve()
        payload = _complete_config().model_dump(mode="json")
        payload["purpose"] = "credential " + "sk-" + ("x" * 24)
        config_path = root / CONFIG_RELATIVE_PATH
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(payload), encoding="utf-8")
        cases["secret_like_config_is_rejected"] = _expect_error(
            lambda: load_config(root),
            "secret-like",
        )

    cases["personal_config_is_metadata_safe"] = not _expect_error(
        lambda: assert_safe_metadata(
            _complete_config().model_dump(mode="json"),
            label="fixture config",
        ),
        "forbidden",
    )
    failed = sorted(name for name, passed in cases.items() if not passed)
    if failed:
        raise RuntimeError("personal clearance verifier cases failed: " + ", ".join(failed))
    return cases


def build_report() -> dict[str, Any]:
    cases = _dynamic_cases()
    return {
        "schema_version": "delivery-clearance.personal-mvp-verification.v1",
        "status": "pass",
        "case_count": len(cases),
        "cases": cases,
        "contracts": sorted(PERSONAL_CLEARANCE_MODELS),
        "entrypoint": "delivery-clearance",
        "compatibility_entrypoint": "python3 scripts/personal_clearance.py",
        "workflow": ["init", "audit", "verify"],
        "maximum_scope": "personal_local",
        "claim_boundary": (
            "This proves a deterministic, state-bound personal self-audit workflow. It does not "
            "prove AI correctness, independent review, external delivery authority, production "
            "approval, or OS-level containment of configured child checks."
        ),
        "privacy": {
            "metadata_only": True,
            "raw_source_text_included": False,
            "raw_check_output_included": False,
            "local_absolute_paths_included": False,
            "model_calls_performed": False,
            "automatic_external_delivery_performed": False,
        },
    }


def expected_outputs() -> dict[Path, str]:
    outputs = {
        ROOT / SCHEMA_ROOT / f"{schema_version}.schema.json": schema_text(model_type)
        for schema_version, model_type in PERSONAL_CLEARANCE_MODELS.items()
    }
    outputs[ROOT / FIXTURE_ROOT / "pass-config.json"] = pretty_json(_complete_config())
    outputs[ROOT / FIXTURE_ROOT / "placeholder-config.json"] = pretty_json(
        default_config("personal-clearance-placeholder")
    )
    outputs[ROOT / REPORT_PATH] = (
        json.dumps(build_report(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.check == args.write:
        raise SystemExit("Choose exactly one of --check or --write.")

    outputs = expected_outputs()
    if args.write:
        for path, content in outputs.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    else:
        stale = [
            path.relative_to(ROOT).as_posix()
            for path, expected in outputs.items()
            if not path.is_file() or path.read_text(encoding="utf-8") != expected
        ]
        if stale:
            raise SystemExit(
                "Personal Clearance MVP artifacts are stale. Run: "
                "python3 scripts/verify_personal_clearance_mvp.py --write\n"
                + "\n".join(stale)
            )
    print(
        json.dumps(build_report(), ensure_ascii=False, indent=2, sort_keys=True),
        end="\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
