# External Platform Operator Drill

This drill proves that Study Anything can be adopted through a platform Agent
without a standalone frontend. It is for Kimi Work, Codex, WorkBuddy-style HTTP
workspaces, and other agents that can import local HTTP tools or run the repo
Skill.

## What The Operator Owns

The platform Agent owns browser access, files, external data, video slicing,
application context, real model credentials, and the user-facing conversation.
Study Anything owns the source-bound learning state, workflow contracts, output
validation, audit/eval evidence, review memory, and Obsidian/NotebookLM handoff.

Do not store real model keys in Study Anything. Keep Kimi, OpenAI-compatible, or
other model credentials inside the user's platform Agent, gateway, or local
environment.

## Drill

1. Unpack `platform/generated/study-anything-platform-adoption-pack.zip`.
2. Open `platform/packs/kimi`, `platform/packs/codex`, or
   `platform/packs/workbuddy`, depending on the host platform.
3. Import `platform/generated/study-anything-platform-openapi.json` or
   `platform/generated/study-anything-openai-tools.json`, or install
   `skills/study-anything` for Codex.
4. Start Skill Mode or the published API image locally.
5. Run importer/enrichment, retrieval, teaching layers, quiz, answer, mastery,
   agent audit, quality eval, Obsidian export, and learning-package export.
6. Share only redacted proof: schema names, statuses, tool counts, session ids,
   and export shapes. Do not share raw source text, answers, generated insight
   text, endpoints with secrets, agent metadata, or API keys.

## Machine Check

Generate and validate the deterministic operator transcript:

```bash
python3 scripts/verify_platform_operator_drill.py --write
python3 scripts/verify_platform_operator_drill.py --check
```

Validate the full external adoption proof:

```bash
python3 scripts/verify_external_adoption.py \
  --pack platform/generated/study-anything-platform-adoption-pack.zip \
  --copy-worktree
```

The first command verifies that the adoption pack can be consumed as an external
platform tool directory. The second command starts the local runtime and proves
the learning/eval/export loop.

## Acceptance Evidence

- `study-anything-operator-drill-v1` transcript is current.
- `adoption-proof-v1` is emitted within the target window.
- Kimi, Codex, and WorkBuddy packs reference existing files only.
- Generated OpenAPI/OpenAI tool assets expose the required Study Anything tool
  names.
- Obsidian export and learning package schemas are present.
- No standalone frontend is required.
- No real model keys are stored by Study Anything.
