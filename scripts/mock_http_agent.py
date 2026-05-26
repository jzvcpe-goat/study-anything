#!/usr/bin/env python3
"""Minimal Study Anything HTTP agent for local and Compose smoke tests."""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any


class MockAgentHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    def do_GET(self) -> None:
        if self.path != "/health":
            self.send_error(404)
            return
        self._send({"status": "ok"})

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        try:
            task = json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            self.send_error(400, "Malformed JSON")
            return
        task_type = task.get("task_type")
        source = task.get("source") or {}
        result: dict[str, Any] = {
            "status": "ok",
            "content": "Focus on source evidence",
            "citations": [],
            "confidence": 0.95,
            "metadata": {"mock_agent": True},
        }
        if source.get("reference"):
            result["citations"].append(
                {
                    "reference": source.get("reference"),
                    "excerpt_hash": source.get("excerpt_hash"),
                }
            )
        if task_type == "answer.grade":
            result["score"] = 0.84
            result["feedback"] = "Mock agent graded the answer as grounded."
        elif task_type == "insight.synthesize":
            title = source.get("title") or "the source"
            mastery = (task.get("constraints") or {}).get("mastery_level", 0.0)
            result["content"] = f"{title} reached mastery level {float(mastery):.1f}."
        elif task_type == "source.verify":
            result["content"] = "Mock agent accepted the source reference."
            result["score"] = 1.0 if source.get("reference") else 0.0
        elif task_type == "embedding.create":
            result["content"] = "source,evidence,mastery"
            result["metadata"]["embedding_terms"] = ["source", "evidence", "mastery"]
        self._send(result)

    def _send(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8787, type=int)
    args = parser.parse_args()
    HTTPServer((args.host, args.port), MockAgentHandler).serve_forever()


if __name__ == "__main__":
    main()
