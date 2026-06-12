# Study Anything Platform Packs

These packs are copy-ready starting points for agent platforms that call Study Anything as a
local-first learning engine.

Each pack points back to the same constrained public contract:

- `platform/study-anything-platform-tools.json`
- `platform/generated/study-anything-platform-openapi.json`
- `platform/generated/study-anything-openai-tools.json`
- `platform/generated/study-anything-tool-catalog.md`
- `platform/generated/study-anything-platform-bundle.json`
- `platform/generated/study-anything-operator-drill-transcript.json`
- `platform/generated/study-anything-platform-adoption-pack.json`
- `platform/generated/study-anything-platform-adoption-pack.zip`

The packs do not configure real model credentials. Keep model keys and browsing/tool access inside
the user's platform Agent or user-owned HTTP Agent gateway.

v0.2.23 packs add a deterministic operator drill on top of the distributable adoption archive,
`adoption-proof-v1` verifier, importer, retrieval, and ecosystem eval capabilities:

- Learning Context Package import for web, document, video-slice, app-context, Markdown, and Obsidian
  material gathered by the platform;
- enrichment input for web, document, video-slice, and app-context excerpts gathered by the platform;
- quality eval evidence that separates invocation proof, schema validity, and teaching-quality gates;
- retrieval/context quality eval evidence for source binding, snippet minimality, query relevance, and
  Learning Context Package handoff;
- Obsidian-compatible markdown export for second-brain workflows;
- a portable learning package for platform agents, NotebookLM-style bridges, Obsidian pipelines, and
  local archives.
- a copy-ready platform adoption pack that proves the Kimi/Codex/WorkBuddy-style tool surface works
  without requiring a standalone frontend.
- `study-anything-operator-drill-v1` transcript evidence that proves the pack can be consumed as an
  external platform tool directory.

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
.venv/bin/python scripts/verify_platform_operator_drill.py --check
.venv/bin/python scripts/generate_platform_adoption_pack.py --check
.venv/bin/python scripts/verify_external_adoption.py \
  --pack platform/generated/study-anything-platform-adoption-pack.zip \
  --copy-worktree
```

For a running API:

```bash
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_agent_tools.py
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_importer_lesson_flow.py
STUDY_ANYTHING_RETRIEVAL_BACKEND=memory API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_ecosystem_eval_flow.py
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_lesson_flow.py
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_openai_compatible_gateway.py
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_agent_eval_flow.py
API_BASE=http://127.0.0.1:8000 python3 scripts/run_external_agent_evals.py --tool deepeval --create-session --allow-native-quality-fallback
STUDY_ANYTHING_RETRIEVAL_BACKEND=memory API_BASE=http://127.0.0.1:8000 python3 scripts/run_external_agent_evals.py --tool retrieval --create-session --required
```

For adoption troubleshooting:

```bash
python3 scripts/diagnose_adoption.py
```
