#!/usr/bin/env python3
"""Fetch frozen public inputs for the real-Agent delivery case set."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from study_anything.cbb.benchmark.real_agent_cases import (  # noqa: E402
    load_real_agent_protocol,
    selected_real_agent_task_ids,
)
from study_anything.cbb.protocol.canonical import assert_safe_metadata, pretty_json  # noqa: E402


def _request_bytes(uri: str) -> bytes:
    headers = {
        "Accept": "application/vnd.github.raw+json",
        "User-Agent": "delivery-clearance-real-agent-benchmark-v0.1",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(uri, headers=headers)
    with urlopen(request, timeout=60) as response:
        return response.read()


def _json_object(data: bytes, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"{label} did not return a JSON object") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{label} did not return a JSON object")
    return payload


def _task_identity(task_id: str) -> tuple[str, str, int]:
    owner, remainder = task_id.split("__", 1)
    repository, number_text = remainder.rsplit("-", 1)
    return owner, repository, int(number_text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--protocol",
        default=str(ROOT / "docs" / "evaluation" / "real-agent-v0.1-protocol.json"),
    )
    parser.add_argument(
        "--output",
        default="/tmp/delivery-clearance-real-agent-v0.1",
    )
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    protocol = load_real_agent_protocol(Path(args.protocol).expanduser().resolve())
    output = Path(args.output).expanduser().resolve()
    if output.exists():
        if not args.replace:
            raise RuntimeError(f"source output already exists: {output}")
        shutil.rmtree(output)
    issues = output / "issues"
    issues.mkdir(parents=True)

    encoded_path = quote(protocol.submission_path, safe="/")
    base = f"https://api.github.com/repos/SWE-bench-Live/submission/contents/{encoded_path}"
    predictions_data = _request_bytes(f"{base}/preds.json?ref={protocol.source_revision}")
    results_data = _request_bytes(f"{base}/results.json?ref={protocol.source_revision}")
    if sha256(predictions_data).hexdigest() != protocol.predictions_digest_sha256:
        raise RuntimeError("downloaded public predictions digest drifted")
    if sha256(results_data).hexdigest() != protocol.results_digest_sha256:
        raise RuntimeError("downloaded public results digest drifted")
    predictions = _json_object(predictions_data, label="public predictions")
    results = _json_object(results_data, label="published results")
    selected = selected_real_agent_task_ids(
        predictions=predictions,
        results=results,
        protocol=protocol,
    )
    (output / "preds.json").write_bytes(predictions_data)
    (output / "results.json").write_bytes(results_data)

    issue_digests: dict[str, str] = {}
    for task_id, _ in selected:
        owner, repository, issue_number = _task_identity(task_id)
        issue_data = _request_bytes(
            f"https://api.github.com/repos/{quote(owner)}/{quote(repository)}/issues/{issue_number}"
        )
        issue = _json_object(issue_data, label=f"GitHub task {task_id}")
        expected_repository = f"https://api.github.com/repos/{owner}/{repository}"
        if (
            issue.get("repository_url") != expected_repository
            or issue.get("number") != issue_number
        ):
            raise RuntimeError(f"downloaded GitHub task identity drifted: {task_id}")
        (issues / f"{task_id}.json").write_bytes(issue_data)
        issue_digests[task_id] = sha256(issue_data).hexdigest()

    receipt = {
        "schema_version": "real-agent-source-fetch-receipt-v1",
        "status": "pass",
        "suite_id": protocol.suite_id,
        "source_repository": protocol.source_repository,
        "source_revision": protocol.source_revision,
        "submission_path": protocol.submission_path,
        "predictions_digest_sha256": protocol.predictions_digest_sha256,
        "results_digest_sha256": protocol.results_digest_sha256,
        "selected_task_ids": [task_id for task_id, _ in selected],
        "selected_task_count": len(selected),
        "issue_response_digests_sha256": issue_digests,
        "credentials_included": False,
        "local_absolute_paths_included": False,
        "raw_source_committed": False,
        "claim_boundary": (
            "This receipt proves public source acquisition and identity only. It is not an "
            "official scorer replay, Delivery Clearance result, or effectiveness claim."
        ),
    }
    assert_safe_metadata(receipt, label="real-Agent source fetch receipt")
    (output / "source-fetch-receipt.json").write_text(pretty_json(receipt), encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
