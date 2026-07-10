# External Platform Operator Drill

This drill proves that the Study Anything adapter can be adopted through a platform Agent
without a standalone frontend. It is for Kimi Work, Codex, WorkBuddy-style HTTP
workspaces, Hermes Agent, and other agents that can import local HTTP tools or
run the repo Skill.

## What The Operator Owns

The platform Agent owns browser access, files, external data, video slicing,
application context, real model credentials, and the user-facing conversation.
Study Anything owns the source-bound learning state, workflow contracts, output
validation, audit/eval evidence, review memory, and Obsidian/NotebookLM handoff.

Do not store real model keys in Study Anything. Keep Kimi, OpenAI-compatible, or
other model credentials inside the user's platform Agent, gateway, or local
environment.

## Drill

1. Pick the platform package:
   `study-anything-codex-plugin-pack.zip`,
   `study-anything-kimi-plugin-pack.zip`, or
   `study-anything-workbuddy-plugin-pack.zip`, or
   `study-anything-hermes-plugin-pack.zip`.
2. Verify the package with its `.sha256` file, then unpack it. Each archive has
   one root directory and a `manifest.json`.
3. Open `platform/packs/kimi`, `platform/packs/codex`,
   `platform/packs/workbuddy`, or `platform/packs/hermes`, depending on the
   host platform.
4. Import `platform/generated/study-anything-platform-openapi.json` or
   `platform/generated/study-anything-openai-tools.json`, or install
   `skills/study-anything` for Codex.
5. Start Skill Mode or the published API image locally.
6. Run importer/enrichment, retrieval, teaching layers, quiz, answer, mastery,
   agent audit, quality eval, Obsidian export, and learning-package export.
7. Share only redacted proof: schema names, statuses, tool counts, session ids,
   and export shapes. Do not share raw source text, answers, generated insight
   text, endpoints with secrets, agent metadata, or API keys.

## Machine Check

Generate and validate the deterministic operator transcript:

```bash
python3 scripts/verify_platform_operator_drill.py --write
python3 scripts/verify_platform_operator_drill.py --check
python3 scripts/generate_platform_plugin_packs.py --check
python3 scripts/verify_platform_plugin_packs.py --check
python3 scripts/verify_platform_submission_dry_run.py --check
```

Validate the full external adoption proof:

```bash
python3 scripts/verify_external_adoption.py \
  --pack platform/generated/study-anything-platform-adoption-pack.zip \
  --copy-worktree
```

The first command verifies that the adoption pack can be consumed as an external
platform tool directory. The dry-run report summarizes per-platform submission
readiness. The external adoption command starts the local runtime and proves the
learning/eval/export loop.

## Acceptance Evidence

- `study-anything-operator-drill-v1` transcript is current.
- `study-anything-platform-plugin-pack-v1` manifests and zip checksums are current.
- `adoption-proof-v1` is emitted within the target window.
- Kimi, Codex, WorkBuddy, and Hermes packs reference existing files only.
- Generated OpenAPI/OpenAI tool assets expose the required Study Anything tool
  names.
- Obsidian export and learning package schemas are present.
- No standalone frontend is required.
- No real model keys are stored by Study Anything.
- `platform-submission-dry-run-v1` has no blocked platform and no private
  learning data.
