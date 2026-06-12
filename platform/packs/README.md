# Study Anything Platform Packs

These packs are copy-ready starting points for agent platforms that call Study Anything as a
local-first learning engine.

Each pack points back to the same constrained public contract:

- `platform/study-anything-platform-tools.json`
- `platform/generated/study-anything-platform-openapi.json`
- `platform/generated/study-anything-openai-tools.json`
- `platform/generated/study-anything-tool-catalog.md`
- `platform/generated/study-anything-platform-bundle.json`

The packs do not configure real model credentials. Keep model keys and browsing/tool access inside
the user's platform Agent or user-owned HTTP Agent gateway.

## Packs

- `codex`: terminal-capable agents that can use the repo-local Skill and CLI.
- `kimi`: Kimi-compatible or OpenAI-compatible tool-calling agents, plus Kimi as a user-owned
  reasoning model through the local gateway.
- `workbuddy`: HTTP-tool workspace agents that import OpenAPI tools and call the local API.

## Verify

```bash
.venv/bin/python scripts/verify_clean_clone_adoption.py --repo . --copy-worktree
.venv/bin/python scripts/verify_platform_ecosystem_packs.py
.venv/bin/python scripts/generate_platform_bundle_manifest.py --check
```

For a running API:

```bash
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_agent_tools.py
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_openai_compatible_gateway.py
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_agent_eval_flow.py
```

For adoption troubleshooting:

```bash
python3 scripts/diagnose_adoption.py
```
