#!/usr/bin/env python3
"""Verify the Web UI container can reach the API through its same-origin proxy."""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, Optional
from urllib.error import HTTPError
from urllib.request import Request, urlopen


WEB_BASE = os.getenv("WEB_BASE", "http://127.0.0.1:5173").rstrip("/")


def request(path: str, payload: Optional[Dict[str, Any]] = None) -> Any:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(
        f"{WEB_BASE}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )
    try:
        with urlopen(req, timeout=10) as response:
            raw = response.read().decode("utf-8")
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type:
                return json.loads(raw)
            return raw
    except HTTPError as exc:
        detail = exc.read().decode("utf-8")
        raise RuntimeError(f"{exc.code} {path}: {detail}") from exc


def main() -> None:
    index = request("/")
    if "Study Anything" not in index:
        raise RuntimeError("Web index did not load Study Anything.")

    health = request("/v1/health")
    if health.get("status") != "ok":
        raise RuntimeError(f"Same-origin API proxy health is not ok: {health}")

    session = request("/v1/sessions", {"user_id": "web-smoke-user", "track": "ACADEMIC", "use_demo_agent": True})
    session_id = session["session_id"]
    request(
        f"/v1/sessions/{session_id}/reading",
        {
            "source_type": "local_text",
            "reference": "demo://web-full-stack",
            "title": "Web Full Stack",
            "text": "The web container should proxy API calls and complete the source-bound learning loop.",
        },
    )
    running = request(f"/v1/sessions/{session_id}/run", {})
    quiz_id = running["quiz_items"][0]["item_id"]
    completed = request(
        f"/v1/sessions/{session_id}/answers",
        {"answers": {quiz_id: "The same-origin web proxy reaches the API container."}},
    )
    if completed["stage"] != "completed":
        raise RuntimeError(f"Expected completed stage, got {completed['stage']}")
    print(
        json.dumps(
            {
                "status": "ok",
                "web_base": WEB_BASE,
                "session_id": session_id,
                "stage": completed["stage"],
                "mastery": completed["mastery"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_full_stack_web failed: {exc}", file=sys.stderr)
        sys.exit(1)
