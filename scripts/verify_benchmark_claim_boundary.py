#!/usr/bin/env python3
"""Verify that mechanism and personal-local evidence cannot overclaim efficacy."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.cbb.benchmark.verification import (  # noqa: E402
    claim_boundary_report,
    write_or_check_report,
)


REPORT = ROOT / "platform" / "generated" / "delivery-clearance-benchmark-claim-boundary.json"
HUMAN_PROTOCOL = ROOT / "docs" / "evaluation" / "pilot-v0.1-human-protocol.json"
PROTOCOL_DEVIATIONS = (
    ROOT / "docs" / "evaluation" / "pilot-v0.1-protocol-deviations.json"
)
METHODOLOGY = ROOT / "docs" / "evaluation" / "native-agent-vs-delivery-clearance.md"


def _build_report() -> dict[str, object]:
    report = claim_boundary_report()
    human_protocol = json.loads(HUMAN_PROTOCOL.read_text(encoding="utf-8"))
    deviations = json.loads(PROTOCOL_DEVIATIONS.read_text(encoding="utf-8"))
    methodology = METHODOLOGY.read_text(encoding="utf-8")

    active_seeds = {
        "boundary_reconstruction": human_protocol["boundary_reconstruction"]["order_seed"],
        "full_review_reference": human_protocol["full_review_reference"]["order_seed"],
        "blinded_adjudication": human_protocol["blinded_adjudication"]["order_seed"],
    }
    documented_command_seeds = set(re.findall(r"--order-seed ([^ \\\n]+)", methodology))
    deviation = deviations["deviations"][0]
    claim_boundary = human_protocol["claim_boundary"]
    privacy = human_protocol["privacy"]
    human_checks = {
        "human_protocol_schema_is_v1": human_protocol.get("schema_version")
        == "benchmark-human-protocol-v1",
        "human_protocol_uses_replacement_boundary_seed": active_seeds[
            "boundary_reconstruction"
        ]
        == deviation.get("replacement_order_seed"),
        "personal_pilot_adjudicator_role_does_not_claim_independence": human_protocol[
            "blinded_adjudication"
        ].get("adjudicator_role")
        == "local-project-owner-adjudicator"
        and "--adjudicator-role independent-" not in methodology,
        "retired_boundary_seed_is_not_active": deviation.get("retired_order_seed")
        not in active_seeds.values(),
        "methodology_commands_use_only_canonical_seeds": documented_command_seeds
        == set(active_seeds.values()),
        "human_protocol_remains_personal_local": claim_boundary.get("maximum_scope")
        == "personal_local",
        "human_protocol_claims_no_independence_or_effectiveness": not any(
            claim_boundary.get(field, True)
            for field in (
                "independent_reviewer_claimed",
                "delivery_clearance_effectiveness_claimed",
                "customer_delivery_validation_claimed",
                "production_approval_claimed",
            )
        ),
        "human_protocol_stores_no_disallowed_review_signals": not any(privacy.values()),
    }
    failed = sorted(name for name, passed in human_checks.items() if not passed)
    if failed:
        raise RuntimeError(f"benchmark human-protocol checks failed: {failed}")

    report_checks = report.get("checks")
    if not isinstance(report_checks, dict):
        raise RuntimeError("claim-boundary report checks are invalid")
    report_checks.update(human_checks)
    report["human_protocol"] = {
        "schema_version": human_protocol["schema_version"],
        "active_order_seed_digests_sha256": {
            name: sha256(seed.encode("utf-8")).hexdigest()
            for name, seed in active_seeds.items()
        },
        "protocol_deviation_count": len(deviations.get("deviations", [])),
        "raw_answers_included": privacy["raw_answers_included"],
        "maximum_scope": claim_boundary["maximum_scope"],
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.check == args.write:
        raise SystemExit("Choose exactly one of --check or --write.")
    report = write_or_check_report(path=REPORT, build=_build_report, write=args.write)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
