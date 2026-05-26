# Agent Contract

Study Anything uses Bring Your Own Agent. The app orchestrates learning state and validates outputs; the user's agent owns model choice, credentials, tools, and internal reasoning.

## Provider Types

- `fake_agent`: deterministic local agent for tests and demos.
- `http_agent`: local or private HTTP endpoint, recommended for MVP launch.
- `cli_agent`: reserved adapter, disabled by default and requires explicit allowlist.
- `mcp_agent`: future plugin ecosystem adapter.

## Capabilities

- `quiz.generate`
- `answer.grade`
- `insight.synthesize`
- `source.verify`
- `memory.retrieve`
- `embedding.create`

## AgentTask Input

The HTTP endpoint receives a single JSON object:

```json
{
  "task_type": "quiz.generate",
  "session_id": "session-id",
  "track": "ACADEMIC",
  "source": {
    "source_type": "local_text",
    "reference": "demo://source",
    "title": "Reading Title",
    "text": "Source text",
    "excerpt_hash": "sha256"
  },
  "quiz_items": [],
  "answers": [],
  "rubric": null,
  "constraints": {
    "source_bound": true
  },
  "metadata": {}
}
```

## AgentResult Output

The agent must return a single JSON object:

```json
{
  "status": "ok",
  "content": "Focus on source-bound mastery",
  "citations": [
    {
      "reference": "demo://source",
      "excerpt_hash": "sha256"
    }
  ],
  "score": null,
  "feedback": null,
  "confidence": 0.9,
  "metadata": {
    "tokens": {
      "prompt": 100,
      "completion": 20
    },
    "cost": {
      "usd": 0.0
    }
  }
}
```

Allowed `status` values are `ok`, `needs_human`, and `error`. For `answer.grade`, `score` is required and must be a number from `0` to `1`. For `quiz.generate` and `insight.synthesize`, `content` is required.

## Minimal HTTP Agent Example

```python
from http.server import BaseHTTPRequestHandler, HTTPServer
import json


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        task = json.loads(self.rfile.read(length))
        task_type = task.get("task_type")
        result = {"status": "ok", "content": "Focus on source evidence", "metadata": {}}
        if task_type == "answer.grade":
            result.update({"score": 0.82, "feedback": "Grounded answer."})
        elif task_type == "insight.synthesize":
            result["content"] = "The reading is linked to current mastery."
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(result).encode("utf-8"))


HTTPServer(("127.0.0.1", 8787), Handler).serve_forever()
```

When Study Anything runs in Docker, use `http://host.docker.internal:8787` as the endpoint for a host-local agent.

## Security Rules

- Do not put real model API keys into Study Anything.
- Keep provider secrets inside the user's agent process or its own secret manager.
- HTTP traces record provider id, task type, latency, status, token/cost metadata if supplied, and redacted metadata only.
- CLI adapters are disabled until an operator explicitly enables a command allowlist and timeout policy.
