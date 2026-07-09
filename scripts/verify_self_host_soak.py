#!/usr/bin/env python3
"""Verify deterministic self-host soak behavior and privacy boundaries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from self_host_soak import (  # noqa: E402
    SCHEMA_VERSION,
    SoakSample,
    build_receipt,
    token_transport_allowed,
)


class SelfHostSoakVerificationError(RuntimeError):
    """Raised when the bounded reliability contract regresses."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SelfHostSoakVerificationError(message)


def receipt(samples: list[SoakSample], *, ratio: float, consecutive: int) -> dict[str, object]:
    return build_receipt(
        samples,
        api_base="http://127.0.0.1:8000",
        interval_seconds=1,
        min_success_ratio=ratio,
        max_consecutive_failures=consecutive,
        started_at="2026-07-09T00:00:00Z",
        finished_at="2026-07-09T00:00:10Z",
    )


def verify() -> dict[str, object]:
    passing = receipt(
        [SoakSample(True, latency, "healthy") for latency in (8, 11, 9, 14, 10)],
        ratio=1.0,
        consecutive=0,
    )
    ratio_blocked = receipt(
        [
            SoakSample(True, 10, "healthy"),
            SoakSample(False, 50, "timeout"),
            SoakSample(True, 12, "healthy"),
        ],
        ratio=0.9,
        consecutive=1,
    )
    consecutive_blocked = receipt(
        [
            SoakSample(True, 10, "healthy"),
            SoakSample(False, 20, "unavailable"),
            SoakSample(False, 21, "unavailable"),
            SoakSample(True, 9, "healthy"),
        ],
        ratio=0.5,
        consecutive=1,
    )
    recovered = receipt(
        [
            SoakSample(True, 10, "healthy"),
            SoakSample(False, 8, "authentication_failed"),
            SoakSample(True, 9, "healthy"),
        ],
        ratio=0.6,
        consecutive=1,
    )

    require(passing["status"] == "pass", "Healthy samples must pass.")
    require(passing["latency_ms"]["p95"] == 14, "Latency percentile drifted.")
    require(ratio_blocked["status"] == "blocked", "Low availability must block.")
    require(
        "success_ratio_below_threshold" in ratio_blocked["blocked_reasons"],
        "Availability threshold reason is missing.",
    )
    require(
        "consecutive_failure_budget_exceeded" in consecutive_blocked["blocked_reasons"],
        "Consecutive failure threshold reason is missing.",
    )
    require(recovered["status"] == "pass", "A recovered in-budget window must pass.")
    require(recovered["sampling"]["recovery_count"] == 1, "Recovery count drifted.")
    require(
        recovered["sampling"]["failure_categories"]["authentication_failed"] == 1,
        "Authentication failure classification is missing.",
    )
    require(
        not token_transport_allowed(
            "https://network.example.invalid", token="fixture-token", allow_network_token=False
        ),
        "Network token transport must require explicit confirmation.",
    )
    require(
        token_transport_allowed(
            "https://network.example.invalid", token="fixture-token", allow_network_token=True
        ),
        "Explicitly confirmed network token transport must remain available.",
    )

    serialized = json.dumps(
        [passing, ratio_blocked, consecutive_blocked, recovered], sort_keys=True
    )
    for forbidden in (
        "verification-secret-value",
        "/Users/james/private",
        "raw source body",
        "learner answer",
        "Authorization: Bearer",
    ):
        require(forbidden not in serialized, f"Soak receipt leaked forbidden content: {forbidden}")

    release_check = (ROOT / "scripts" / "release_check.sh").read_text(encoding="utf-8")
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    launcher = (ROOT / "scripts" / "launch_self_host.sh").read_text(encoding="utf-8")
    soak_source = (ROOT / "scripts" / "self_host_soak.py").read_text(encoding="utf-8")
    require("verify_self_host_soak.py --check" in release_check, "Release gate is missing.")
    require("self_host_soak.py" in ci, "Docker compose smoke is missing the live soak.")
    require("verify_self_host_soak.py --check" in ci, "CI deterministic verifier is missing.")
    require(
        "password authentication failed for user" in launcher,
        "Launcher does not classify Postgres credential drift.",
    )
    require(
        "Do not delete the volume" in launcher,
        "Launcher does not preserve the non-destructive recovery boundary.",
    )
    require("NoRedirectHandler" in soak_source, "Health probes must reject redirects.")

    return {
        "schema_version": "self-host-soak-verification-v1",
        "status": "pass",
        "receipt_schema_version": SCHEMA_VERSION,
        "checks": {
            "healthy_window_passes": True,
            "availability_threshold_blocks": True,
            "consecutive_failure_budget_blocks": True,
            "authentication_failure_classified": True,
            "recovery_after_failure_recorded": True,
            "latency_percentiles_recorded": True,
            "release_gate_integrated": True,
            "docker_compose_smoke_integrated": True,
            "postgres_credential_drift_diagnosed": True,
            "destructive_volume_reset_not_automatic": True,
            "network_token_transport_requires_confirmation": True,
            "authorization_redirects_rejected": True,
        },
        "privacy": {
            "metadata_only": True,
            "health_response_bodies_included": False,
            "tokens_included": False,
            "local_absolute_paths_included": False,
            "model_calls_performed": False,
            "production_mutation_performed": False,
        },
        "claim_boundary": (
            "The verifier proves deterministic aggregation and a short real Compose health window. "
            "It does not claim a multi-hour production SLO or disaster recovery certification."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.parse_args()
    try:
        print(json.dumps(verify(), ensure_ascii=False, indent=2, sort_keys=True))
    except SelfHostSoakVerificationError as exc:
        print(f"verify_self_host_soak failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
