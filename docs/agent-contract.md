# Agent Contract

Study Anything uses Bring Your Own Agent. The app orchestrates learning state and validates outputs; the user's agent owns model choice, credentials, tools, and internal reasoning.

## Provider Types

- `fake_agent`: deterministic local agent for tests and demos.
- `http_agent`: local or private HTTP endpoint, recommended for MVP launch.
- `cli_agent`: reserved adapter, disabled by default and requires explicit allowlist.
- `mcp_agent`: future plugin ecosystem adapter.

## Capabilities

- `teach.overview`
- `teach.glossary`
- `teach.examples`
- `quiz.generate`
- `answer.grade`
- `insight.synthesize`
- `note.scribe`
- `source.verify`
- `memory.retrieve`
- `embedding.create`

Teaching capabilities are intentionally separate from the quiz loop so a user-owned
Agent Gateway can route each layer to a different model. For example, it can send
`teach.overview` to a strong reasoning model, `teach.glossary` to a cheaper fast
model, and `teach.examples` to a multimodal or code-specialized model. Study
Anything records only the provider id, task type, latency, status, confidence,
and redacted token/cost metadata.

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

Allowed `status` values are `ok`, `needs_human`, and `error`. For `answer.grade`, `score` is required and must be a number from `0` to `1`. For `teach.overview`, `teach.glossary`, `teach.examples`, `quiz.generate`, `insight.synthesize`, and `note.scribe`, `content` is required.

## Teaching Layer Tasks

Use `POST /v1/sessions/{session_id}/teaching-layers` after attaching a reading source
when a platform Agent wants layered teaching output before the quiz loop. The
endpoint accepts layer names and routes each layer through capability defaults:

```json
{
  "layers": ["overview", "glossary", "examples"],
  "language": "zh",
  "level": "beginner",
  "max_terms": 8,
  "example_mode": "mixed"
}
```

Layer mapping:

- `overview` -> `teach.overview`: whole-topic frame, key points, and learning path.
- `glossary` -> `teach.glossary`: professional terms with plain-language explanation,
  technical definition, and example.
- `examples` -> `teach.examples`: concrete examples, analogies, HTML explainer ideas,
  or code/business examples.
- `scribe` -> `note.scribe`: compact Markdown note suitable for Obsidian-style review.

The response contains private learning output and should not be logged by platform
wrappers. Agent audit/eval artifacts return only redacted provider/task evidence.

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
        if task_type == "teach.overview":
            result["content"] = {"summary": "This source explains the main idea."}
        elif task_type == "teach.glossary":
            result["content"] = [{"term": "source evidence", "plain_language": "proof from the material"}]
        elif task_type == "answer.grade":
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

The repository also includes `scripts/openai_compatible_agent_gateway.py` for user-owned
OpenAI-compatible APIs, including Kimi. Run
`python3 scripts/verify_openai_compatible_gateway.py --gateway-only` to verify the gateway contract
without a model key, then see `docs/kimi-agent-gateway.md`.

## Security Rules

- Do not put real model API keys into Study Anything.
- Keep provider secrets inside the user's agent process or its own secret manager.
- Do not put credentials in Agent endpoint URLs, query parameters, or provider metadata.
- `POST /v1/agents/providers` rejects endpoint credentials and secret-like metadata keys.
- Local single-operator mode permits operator-selected HTTP(S) endpoints. Production
  requires `STUDY_ANYTHING_AGENT_ENDPOINT_POLICY=allowlist` and exact origins in
  `STUDY_ANYTHING_AGENT_ENDPOINT_ALLOWLIST`.
- Non-loopback allowlisted origins must use HTTPS. Agent HTTP redirects are rejected,
  and the endpoint origin is revalidated immediately before invocation.
- `GET /v1/agents/status` returns redacted provider metadata and URL-level endpoint redaction.
- HTTP traces record provider id, task type, latency, status, token/cost metadata if supplied, and redacted metadata only.
- HTTP Agent responses are limited to 1 MiB before JSON parsing and contract validation.
- CLI adapters are disabled until an operator explicitly enables a command allowlist and timeout policy.
- Run `python3 scripts/verify_agent_gateway_hardening.py` and
  `python3 scripts/verify_external_agent_adapter_hardening.py` before release or platform handoff.
- Run `python3 scripts/verify_agent_endpoint_policy.py --check` for the configured
  outbound destination boundary. It does not replace hosted identity, tenant
  isolation, or network-layer egress controls.
