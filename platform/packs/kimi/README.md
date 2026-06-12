# Kimi Pack

Use this pack in two ways:

1. Import Study Anything learning tools into a Kimi-compatible function-calling environment.
2. Use Kimi as the user-owned reasoning model behind the local HTTP Agent gateway.

Browser-only Kimi chat cannot call `127.0.0.1` directly. A terminal, workspace Agent, or private
gateway must make the local HTTP calls.

## Tool Import

Use one of:

```text
platform/generated/study-anything-openai-tools.json
platform/generated/study-anything-platform-openapi.json
```

Set the API base to:

```text
http://127.0.0.1:8000
```

Run the clean-clone adoption smoke before wiring real credentials:

```bash
python3 scripts/verify_clean_clone_adoption.py --repo .
```

## Kimi As Reasoning Agent

First verify the same gateway entrypoint without a real key:

```bash
python3 scripts/verify_openai_compatible_gateway.py --gateway-only
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_openai_compatible_gateway.py
```

Then switch the gateway to real Kimi credentials:

```bash
export AGENT_LLM_BASE_URL="https://api.moonshot.cn/v1"
export AGENT_LLM_API_KEY="$MOONSHOT_API_KEY"
export AGENT_LLM_MODEL="${AGENT_LLM_MODEL:-kimi-k2.6}"

python3 scripts/openai_compatible_agent_gateway.py --host 127.0.0.1 --port 8787
python3 scripts/study_anything_cli.py agent-add-http \
  --label "My Kimi gateway" \
  --endpoint "http://127.0.0.1:8787/invoke" \
  --set-default
```

Keep Moonshot/Kimi credentials in the gateway environment, not in Study Anything. The default
`agent-add-http --set-default` command registers teaching layers, quiz generation, grading, synthesis,
scribe notes, source verification, and embedding tasks.

## Acceptance

After a completed learning loop, the platform Agent should fetch:

```text
GET /v1/sessions/{session_id}/agent-audit
GET /v1/sessions/{session_id}/agent-eval/artifact
```

Share only compact mastery and redacted evidence. Do not log raw source text, learner answers,
grading feedback, Agent endpoints, or model secrets.

## Troubleshooting

```bash
python3 scripts/diagnose_adoption.py --agent-endpoint http://127.0.0.1:8787/invoke
```

If browser-only Kimi cannot call localhost, move the HTTP calls to a terminal-capable Agent, local
gateway, or authenticated private gateway.
