# Platform Agent Integrations

Study Anything is designed to be called by a platform Agent rather than to replace one. The platform
Agent owns browsing, files, apps, video tools, external data, user conversation, and model credentials.
Study Anything owns the learning loop: source binding, optional layered teaching output, quiz
generation, answer grading, mastery, scribe logs, HITL state, Agent audit, and eval artifacts.

## Recommended Split

| Layer | Responsibility |
| --- | --- |
| Platform Agent | Find sources, operate browser/apps, call external tools, prepare source text or excerpts, explain results to the user. |
| Study Anything API | Persist learning sessions, call the configured learning Agent, validate outputs, expose audit/eval evidence. |
| User-Owned Agent Gateway | Use the user's chosen model, credentials, tools, and reasoning strategy for real learning tasks. |

Study Anything should not store real model API keys. Keep keys inside the platform Agent or the
user-owned HTTP gateway.

## Machine-Readable Tool Contract

Platform integrations should start from the repo-local manifest:

```text
platform/study-anything-platform-tools.json
```

The manifest declares the minimum tool surface for Codex, Kimi Work, WorkBuddy-style workspaces, and
private Agent platforms:

- API health
- session creation
- source attachment
- enrichment attachment for web, document/PDF, video-slice, app-context, Markdown, and Obsidian excerpts
- optional teaching layers such as overview, glossary, examples, or Obsidian-style notes
- workflow run/resume
- answer submission
- mastery lookup
- redacted Agent audit
- redacted Agent eval artifact
- redacted teaching-quality eval
- redacted retrieval/context quality eval
- redacted Markdown+HTML enrichment micro-lesson export
- Obsidian-compatible markdown export
- portable learning package export for NotebookLM-style bridges and platform-agent handoff
- strict second-brain handoff export for Obsidian, NotebookLM-style manual import, and local archives

It intentionally does not expose Agent provider configuration, deprecated model aliases, plugin
installation, encrypted sync export, PMF export, or other management surfaces. Configure user-owned
Agent gateways outside the platform learning tools, then let the platform Agent call only the learning
contract.

Validate a running integration with:

```bash
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_agent_tools.py
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_lesson_flow.py
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_openai_compatible_gateway.py
API_BASE=http://127.0.0.1:8000 python3 scripts/run_external_agent_evals.py --tool deepeval --create-session --allow-native-quality-fallback
STUDY_ANYTHING_RETRIEVAL_BACKEND=memory API_BASE=http://127.0.0.1:8000 \
  python3 scripts/verify_platform_ecosystem_eval_flow.py
```

`./scripts/run_skill_mode_demo.sh` also runs this verifier after the CLI learning smoke.

For a release or external-platform handoff, use the adoption pack verifier instead of manually
assembling commands:

```bash
python3 scripts/generate_platform_adoption_pack.py --check
python3 scripts/verify_platform_operator_drill.py --check
python3 scripts/verify_agent_eval_baseline.py --check
python3 scripts/verify_external_adoption.py \
  --pack platform/generated/study-anything-platform-adoption-pack.zip \
  --copy-worktree
```

The operator drill emits `study-anything-operator-drill-v1` and proves that the pack can be consumed
as a platform tool directory before any runtime starts. The adoption verifier emits
`adoption-proof-v1` and proves that a fresh operator can start Study Anything in Skill Mode, use the
platform tool surface, complete the importer/enrichment/retrieval/teaching/eval loop, and export
Obsidian plus NotebookLM-style handoff artifacts without a standalone frontend.

## Generated Import Assets

The checked-in generated files are derived from the manifest:

```text
platform/generated/study-anything-platform-openapi.json
platform/generated/study-anything-openai-tools.json
platform/generated/study-anything-tool-catalog.md
platform/generated/study-anything-platform-bundle.json
platform/generated/study-anything-operator-drill-transcript.json
platform/generated/study-anything-platform-adoption-pack.json
platform/generated/study-anything-platform-adoption-pack.zip
evals/baselines/study-anything-agent-eval-baseline.json
```

Use the OpenAPI file for HTTP tool importers. Use the OpenAI-compatible tools JSON for
Kimi-compatible model APIs, Codex-style tool runners, and other function-calling Agent platforms that
need tool names, descriptions, and JSON schemas.

Regenerate and verify these assets after changing the manifest, platform packs, or bundled docs:

```bash
python3 scripts/generate_platform_agent_assets.py
python3 scripts/generate_platform_agent_assets.py --check
python3 scripts/verify_openai_compatible_gateway.py --gateway-only
python3 scripts/generate_platform_bundle_manifest.py --check
python3 scripts/verify_platform_operator_drill.py --check
python3 scripts/verify_agent_eval_baseline.py --check
python3 scripts/generate_platform_adoption_pack.py --check
```

## Packaged Ecosystem Starters

Copy-ready platform packs live in:

```text
platform/packs/codex
platform/packs/kimi
platform/packs/workbuddy
```

Each pack includes a `pack.json` plus README with the recommended entrypoints, import assets,
verification commands, acceptance evidence, and privacy boundary for that platform shape.

Verify the packs against the source manifest:

```bash
python3 scripts/verify_platform_ecosystem_packs.py
python3 scripts/generate_platform_bundle_manifest.py --check
python3 scripts/generate_platform_adoption_pack.py --check
```

The bundle manifest records sha256 hashes and purposes for the platform manifest, generated import
assets, ecosystem packs, key docs, and repo-local Skill entrypoint. Use it as the release artifact
index when publishing platform integration assets.

## Codex Or Terminal-Capable Agents

Use the repo-local skill and CLI when the platform Agent can run shell commands in this repository:

```bash
./scripts/launch_skill_mode.sh
python3 scripts/study_anything_cli.py health
python3 scripts/study_anything_cli.py start \
  --title "Source title" \
  --reference "local://source" \
  --text "Paste source material here."
python3 scripts/study_anything_cli.py answer SESSION_ID \
  --text "Answer grounded in the source."
python3 scripts/study_anything_cli.py agent-audit SESSION_ID
python3 scripts/study_anything_cli.py agent-eval SESSION_ID
python3 scripts/study_anything_cli.py quality-eval SESSION_ID
python3 scripts/study_anything_cli.py enrichment-artifact SESSION_ID --markdown
python3 scripts/study_anything_cli.py obsidian-export SESSION_ID --markdown
python3 scripts/study_anything_cli.py package-export SESSION_ID
python3 scripts/study_anything_cli.py second-brain-handoff SESSION_ID --archive-dir /tmp/study-anything-archive
```

For Codex, symlink the skill:

```bash
ln -s "$(pwd)/skills/study-anything" "${CODEX_HOME:-$HOME/.codex}/skills/study-anything"
```

The platform Agent should report the mastery result plus whether `agent-audit.status` is `verified`.
When the user asks for explanation before answering a quiz, the platform Agent can call
`POST /v1/sessions/{session_id}/teaching-layers` after source attachment and before `run`. Treat the
returned layer content as private learning data.

When the platform Agent has gathered browser pages, PDFs, app state, Markdown notes, Obsidian notes,
or video slices, prefer a Learning Context Package:

```bash
python3 scripts/study_anything_cli.py context-validate \
  fixtures/notebooklm/notebooklm-style-context-package.json
python3 scripts/study_anything_cli.py context-import \
  fixtures/notebooklm/notebooklm-style-context-package.json --session
```

The HTTP equivalents are `POST /v1/context-packages/validate`,
`POST /v1/sessions/from-context-package`, and `POST /v1/sessions/{session_id}/context-package`.
Study Anything validates the package, turns the bounded excerpts into a source-bound bundle, then the
normal teaching/quiz/mastery loop runs against that bundle. The older
`POST /v1/sessions/{session_id}/enrichment` endpoint remains available for simple one-off excerpts.

For a fixed platform-agent acceptance path, run:

```bash
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_lesson_flow.py
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_importer_lesson_flow.py
```

The verifiers complete enriched and importer-based lessons, then fetch Agent audit, Agent eval, quality
eval, Obsidian Markdown, `learning-package-v1`, and `second-brain-handoff-v1`. Use the second-brain
handoff when the platform Agent needs to hand the result to a NotebookLM-style workflow, Obsidian
vault, local archive, or later knowledge-base connector without logging answers or grading feedback.

`agent-add-http --set-default` registers a user-owned HTTP Agent for teaching layers, quiz generation,
grading, synthesis, scribe notes, source verification, and embedding tasks by default. Pass explicit
`--capability` values only when a provider should handle a smaller subset.

## Kimi

Browser-only Kimi cannot run local scripts or reach `127.0.0.1`. Use Kimi as the user-owned reasoning
model through an OpenAI-compatible gateway:

```bash
python3 scripts/verify_openai_compatible_gateway.py --gateway-only
```

Then start the real gateway after adding credentials:

```bash
export AGENT_LLM_BASE_URL="https://api.moonshot.cn/v1"
export AGENT_LLM_API_KEY="$MOONSHOT_API_KEY"
export AGENT_LLM_MODEL="${AGENT_LLM_MODEL:-kimi-k2.6}"

python3 scripts/openai_compatible_agent_gateway.py \
  --host 127.0.0.1 \
  --port 8787
```

Then register it from Study Anything:

```bash
python3 scripts/study_anything_cli.py agent-add-http \
  --label "My Kimi gateway" \
  --endpoint "http://127.0.0.1:8787/invoke" \
  --set-default
python3 scripts/study_anything_cli.py agent-test PROVIDER_ID
```

See `docs/kimi-agent-gateway.md` for the full flow.

## WorkBuddy Or Other Agent Workspaces

Use the HTTP API contract when the platform can call local or private HTTP tools:

1. Start Study Anything with Docker or Skill Mode.
2. Expose only the needed API base to the platform Agent.
3. Give the platform Agent the public endpoints in `docs/api.md`.
4. Require it to call `agent-audit` and `agent-eval/artifact` after each completed learning loop.
5. Optionally return `agent-eval/quality` and `exports/obsidian` for quality proof and second-brain notes.

Minimum endpoints for a platform tool wrapper:

- `GET /v1/health`
- `POST /v1/sessions`
- `POST /v1/sessions/{session_id}/reading`
- `POST /v1/context-packages/validate` optional importer path
- `POST /v1/sessions/from-context-package` optional importer path
- `POST /v1/sessions/{session_id}/context-package` optional importer path
- `GET /v1/plugins/sdk` optional plugin SDK contract
- `GET /v1/plugins/capabilities` optional plugin capability index
- `POST /v1/plugins/validate-package` optional local plugin package validation
- `POST /v1/importers/{plugin_id}/run` optional local importer runtime
- `GET /v1/retrieval/status` optional retrieval status
- `POST /v1/sessions/{session_id}/retrieval/rebuild` optional retrieval projection
- `POST /v1/sessions/{session_id}/retrieval/search` optional retrieval search
- `POST /v1/sessions/{session_id}/retrieval/eval` optional retrieval/context quality eval
- `POST /v1/sessions/from-retrieval` optional retrieval-to-session path
- `POST /v1/sessions/{session_id}/retrieval/context-package` optional retrieval append path
- `POST /v1/sessions/{session_id}/enrichment` optional
- `POST /v1/sessions/{session_id}/teaching-layers` optional
- `POST /v1/sessions/{session_id}/run`
- `POST /v1/sessions/{session_id}/answers`
- `GET /v1/sessions/{session_id}/mastery`
- `GET /v1/sessions/{session_id}/agent-audit`
- `GET /v1/sessions/{session_id}/agent-eval/artifact`
- `GET /v1/sessions/{session_id}/agent-eval/quality`
- `GET /v1/sessions/{session_id}/exports/obsidian`
- `GET /v1/sessions/{session_id}/exports/second-brain-handoff`
- `GET /v1/sessions/{session_id}/exports/learning-package`

## Acceptance Gate

A platform integration is acceptable when it can complete this sequence:

1. Start or reach a Study Anything API.
2. Submit a user-provided source with a reference, run a confirmed local importer, or validate/import
   `learning-context-package-v1`.
3. Complete one quiz/answer/mastery loop.
4. Return `agent-audit.status=verified`.
5. Return `agent-eval-artifact-v1` with all required native gates passing.
6. Return `agent-quality-eval-v1` with `status=pass`.
7. Return an Obsidian markdown export when the user asks for knowledge deposit.
8. Return `learning-package-v1` when the user wants NotebookLM-style, platform-agent, or local archive handoff.
9. Run `scripts/verify_importer_lesson_flow.py` for package-import release evidence.
10. Run `scripts/verify_importer_runtime_retrieval_flow.py` with retrieval explicitly enabled when
   validating importer runtime plus retrieval.
11. Run `scripts/verify_platform_ecosystem_eval_flow.py` when validating the full platform Agent path:
   importer, enrichment, retrieval, retrieval eval, teaching, learning loop, external eval adapters,
   Obsidian, and learning-package export.
12. Run `scripts/verify_external_adoption.py` against the adoption pack before publishing a platform
   handoff, GitHub prerelease, or external operator guide.
13. Avoid returning source prose, answers, feedback, endpoints, raw Agent metadata, or model secrets in
   logs or shared artifacts.

For local validation:

```bash
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_full_api_flow.py
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_agent_eval_flow.py
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_agent_tools.py
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_importer_lesson_flow.py
STUDY_ANYTHING_RETRIEVAL_BACKEND=memory API_BASE=http://127.0.0.1:8000 python3 scripts/verify_importer_runtime_retrieval_flow.py
STUDY_ANYTHING_RETRIEVAL_BACKEND=memory API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_ecosystem_eval_flow.py
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_lesson_flow.py
API_BASE=http://127.0.0.1:8000 python3 scripts/run_external_agent_evals.py --tool deepeval --create-session --allow-native-quality-fallback
STUDY_ANYTHING_RETRIEVAL_BACKEND=memory API_BASE=http://127.0.0.1:8000 python3 scripts/run_external_agent_evals.py --tool retrieval --create-session --required
```
