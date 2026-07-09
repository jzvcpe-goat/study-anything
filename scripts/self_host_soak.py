#!/usr/bin/env python3
"""Run a bounded self-host health soak and emit a metadata-only receipt."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import ipaddress
import json
import math
import os
from pathlib import Path
import socket
import time
from typing import Callable, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


SCHEMA_VERSION = "self-host-soak-receipt-v1"
MAX_HEALTH_BODY_BYTES = 64 * 1024
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


@dataclass(frozen=True)
class SoakSample:
    success: bool
    latency_ms: int
    category: str


class NoRedirectHandler(HTTPRedirectHandler):
    """Turn redirects into HTTP errors so authorization cannot cross origins."""

    def redirect_request(self, *_args, **_kwargs):
        return None


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_env_value(path: Path, key: str) -> str | None:
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        candidate, value = stripped.split("=", 1)
        if candidate.strip() == key:
            return value.strip().strip("'\"") or None
    return None


def api_token(env_file: Path) -> str | None:
    return os.getenv("STUDY_ANYTHING_API_TOKEN") or parse_env_value(
        env_file, "STUDY_ANYTHING_API_TOKEN"
    )


def endpoint_metadata(api_base: str) -> dict[str, object]:
    parsed = urlparse(api_base)
    host = (parsed.hostname or "").lower()
    scope = "network"
    if host in LOOPBACK_HOSTS:
        scope = "loopback"
    else:
        try:
            if ipaddress.ip_address(host).is_private:
                scope = "private_network"
        except ValueError:
            pass
    return {
        "scope": scope,
        "tls_enabled": parsed.scheme.lower() == "https",
        "host_included": False,
        "url_included": False,
    }


def token_transport_allowed(
    api_base: str, *, token: str | None, allow_network_token: bool
) -> bool:
    if not token or endpoint_metadata(api_base)["scope"] == "loopback":
        return True
    return allow_network_token


def open_health_request(request: Request, *, timeout_seconds: float):
    return build_opener(NoRedirectHandler).open(request, timeout=timeout_seconds)


def probe_health(api_base: str, *, token: str | None, timeout_seconds: float) -> SoakSample:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(api_base.rstrip("/") + "/v1/health", headers=headers)
    started = time.perf_counter()
    try:
        with open_health_request(request, timeout_seconds=timeout_seconds) as response:
            body = response.read(MAX_HEALTH_BODY_BYTES + 1)
            status_code = int(response.status)
        if len(body) > MAX_HEALTH_BODY_BYTES:
            category = "invalid_health_payload"
            success = False
        else:
            payload = json.loads(body.decode("utf-8"))
            success = status_code == 200 and payload.get("status") == "ok"
            category = "healthy" if success else "invalid_health_payload"
    except HTTPError as exc:
        success = False
        category = "authentication_failed" if exc.code in {401, 403} else "http_error"
    except (TimeoutError, socket.timeout):
        success = False
        category = "timeout"
    except (URLError, OSError):
        success = False
        category = "unavailable"
    except (UnicodeDecodeError, json.JSONDecodeError, AttributeError, TypeError, ValueError):
        success = False
        category = "invalid_health_payload"
    latency_ms = max(0, round((time.perf_counter() - started) * 1000))
    return SoakSample(success=success, latency_ms=latency_ms, category=category)


def percentile(values: Sequence[int], percentile_value: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil(percentile_value * len(ordered)) - 1))
    return ordered[index]


def longest_failure_run(samples: Sequence[SoakSample]) -> int:
    longest = 0
    current = 0
    for sample in samples:
        if sample.success:
            current = 0
        else:
            current += 1
            longest = max(longest, current)
    return longest


def recovery_count(samples: Sequence[SoakSample]) -> int:
    """Count successful probes that immediately follow one or more failures."""
    recoveries = 0
    previous_failed = False
    for sample in samples:
        if sample.success:
            if previous_failed:
                recoveries += 1
            previous_failed = False
        else:
            previous_failed = True
    return recoveries


def build_receipt(
    samples: Sequence[SoakSample],
    *,
    api_base: str,
    interval_seconds: float,
    min_success_ratio: float,
    max_consecutive_failures: int,
    started_at: str,
    finished_at: str,
    require_recovery: bool = False,
) -> dict[str, object]:
    completed = len(samples)
    successes = sum(1 for sample in samples if sample.success)
    failures = completed - successes
    success_ratio = round(successes / completed, 4) if completed else 0.0
    consecutive_failures = longest_failure_run(samples)
    recoveries = recovery_count(samples)
    categories: dict[str, int] = {}
    for sample in samples:
        categories[sample.category] = categories.get(sample.category, 0) + 1

    blocked_reasons: list[str] = []
    if success_ratio < min_success_ratio:
        blocked_reasons.append("success_ratio_below_threshold")
    if consecutive_failures > max_consecutive_failures:
        blocked_reasons.append("consecutive_failure_budget_exceeded")
    if require_recovery and recoveries < 1:
        blocked_reasons.append("required_recovery_not_observed")

    latencies = [sample.latency_ms for sample in samples]
    status = "pass" if not blocked_reasons else "blocked"
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "classification": "healthy_window" if status == "pass" else "reliability_gate_blocked",
        "started_at": started_at,
        "finished_at": finished_at,
        "endpoint": endpoint_metadata(api_base),
        "sampling": {
            "sample_count": completed,
            "interval_seconds": interval_seconds,
            "success_count": successes,
            "failure_count": failures,
            "success_ratio": success_ratio,
            "longest_consecutive_failure_run": consecutive_failures,
            "recovery_count": recoveries,
            "recovered_after_failure": recoveries > 0,
            "failure_categories": dict(sorted(categories.items())),
        },
        "thresholds": {
            "minimum_success_ratio": min_success_ratio,
            "maximum_consecutive_failures": max_consecutive_failures,
            "recovery_after_failure_required": require_recovery,
        },
        "latency_ms": {
            "minimum": min(latencies, default=0),
            "maximum": max(latencies, default=0),
            "p50": percentile(latencies, 0.50),
            "p95": percentile(latencies, 0.95),
        },
        "blocked_reasons": blocked_reasons,
        "privacy": {
            "metadata_only": True,
            "health_response_body_included": False,
            "api_url_included": False,
            "api_token_included": False,
            "docker_logs_included": False,
            "local_absolute_paths_included": False,
            "raw_source_text_included": False,
            "learner_answers_included": False,
            "agent_metadata_included": False,
            "model_calls_performed": False,
            "production_mutation_performed": False,
        },
        "claim_boundary": (
            "This receipt proves only bounded HTTP health availability for one self-host window. "
            "It does not prove correctness, tenant isolation, production SLO compliance, or recovery."
        ),
    }


def run_soak(
    *,
    api_base: str,
    token: str | None,
    sample_count: int,
    interval_seconds: float,
    request_timeout_seconds: float,
    min_success_ratio: float,
    max_consecutive_failures: int,
    require_recovery: bool = False,
    probe: Callable[..., SoakSample] = probe_health,
) -> dict[str, object]:
    started_at = utc_now()
    samples: list[SoakSample] = []
    for index in range(sample_count):
        samples.append(probe(api_base, token=token, timeout_seconds=request_timeout_seconds))
        if index + 1 < sample_count and interval_seconds > 0:
            time.sleep(interval_seconds)
    return build_receipt(
        samples,
        api_base=api_base,
        interval_seconds=interval_seconds,
        min_success_ratio=min_success_ratio,
        max_consecutive_failures=max_consecutive_failures,
        started_at=started_at,
        finished_at=utc_now(),
        require_recovery=require_recovery,
    )


def write_receipt(path: Path, receipt: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    path.chmod(0o600)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", default=os.getenv("API_BASE", "http://127.0.0.1:8000"))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--samples", type=int, default=60)
    parser.add_argument("--interval-seconds", type=float, default=5.0)
    parser.add_argument("--request-timeout-seconds", type=float, default=5.0)
    parser.add_argument("--min-success-ratio", type=float, default=0.99)
    parser.add_argument("--max-consecutive-failures", type=int, default=1)
    parser.add_argument(
        "--require-recovery",
        action="store_true",
        help="Block unless a successful probe follows one or more failed probes.",
    )
    parser.add_argument(
        "--allow-network-token",
        action="store_true",
        help="Explicitly allow the local API token to be sent to a non-loopback API base.",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if args.samples < 1:
        parser.error("--samples must be at least 1")
    if args.interval_seconds < 0 or args.request_timeout_seconds <= 0:
        parser.error("interval must be non-negative and request timeout must be positive")
    if not 0 < args.min_success_ratio <= 1:
        parser.error("--min-success-ratio must be greater than 0 and at most 1")
    if args.max_consecutive_failures < 0:
        parser.error("--max-consecutive-failures must be non-negative")
    parsed_api_base = urlparse(args.api_base)
    if parsed_api_base.scheme not in {"http", "https"} or not parsed_api_base.hostname:
        parser.error("--api-base must use http or https")

    token = api_token(args.env_file)
    if not token_transport_allowed(
        args.api_base, token=token, allow_network_token=args.allow_network_token
    ):
        parser.error(
            "refusing to send the local API token to a non-loopback endpoint; "
            "pass --allow-network-token only after verifying the destination"
        )

    receipt = run_soak(
        api_base=args.api_base,
        token=token,
        sample_count=args.samples,
        interval_seconds=args.interval_seconds,
        request_timeout_seconds=args.request_timeout_seconds,
        min_success_ratio=args.min_success_ratio,
        max_consecutive_failures=args.max_consecutive_failures,
        require_recovery=args.require_recovery,
    )
    if args.output:
        write_receipt(args.output, receipt)
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    raise SystemExit(0 if receipt["status"] == "pass" else 1)


if __name__ == "__main__":
    main()
