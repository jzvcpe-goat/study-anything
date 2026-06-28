# Use Study Anything With Hermes Agent

Study Anything works with Hermes Agent as a local-first learning engine. Hermes
should remain the user's Agent surface: model choice, conversation, memory,
browsing, MCP servers, app tools, and real credentials stay in Hermes or in the
user's private gateway. Study Anything supplies the source-bound learning loop,
local receipts, redacted eval evidence, Obsidian/NotebookLM-style exports, and
Cognitive Loop metadata artifacts.

## Current Path: Hermes Skill

Hermes can install a direct `SKILL.md` URL. Use this when a Hermes Agent can run
local commands in, or against, a Study Anything checkout:

```bash
hermes skills install \
  https://raw.githubusercontent.com/jzvcpe-goat/study-anything/main/skills/study-anything/SKILL.md \
  --name study-anything \
  --yes
```

For local development, you can also expose the checked-out skill directory to
Hermes:

```bash
mkdir -p ~/.hermes/skills
ln -s "$(pwd)/skills/study-anything" ~/.hermes/skills/study-anything
```

Then start Study Anything locally:

```bash
./START_HERE.command
python3 scripts/study_anything_cli.py health
```

Ask Hermes to use the `study-anything` skill and run a first source-bound lesson
through the local CLI. The lowest-friction smoke is:

```bash
./scripts/run_skill_mode_demo.sh
```

For live local API verification:

```bash
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_agent_tools.py
python3 scripts/verify_platform_plugin_packs.py --platform hermes --check
```

## Download Pack

The generated Hermes pack is:

```text
platform/generated/study-anything-hermes-plugin-pack.zip
```

It includes:

- `skills/study-anything/SKILL.md`
- `platform/packs/hermes/pack.json`
- `platform/packs/hermes/README.md`
- `platform/generated/study-anything-platform-openapi.json`
- `platform/generated/study-anything-tool-catalog.md`
- local launch and verification scripts

The pack is an import helper. It is not an official Hermes marketplace listing
and not yet a Hermes-native Python plugin.

## Future Path: Hermes Plugin Repo

Hermes supports plugins installed from Git repositories with:

```bash
hermes plugins install owner/repo --enable
```

Do not use that command for the current `study-anything` repository yet. A
Hermes-native plugin should be a separate, field-tested repository with a root
`plugin.yaml`, typed tool registration, and a verifier proving it can call the
local Study Anything runtime without leaking raw source text, learner answers,
Agent endpoints, prompts, model keys, cookies, bearer tokens, or signed URLs.

Until that exists, the supported Hermes path is Skill + local CLI/HTTP tools.

## Privacy Boundary

Hermes may know user conversation context, browser/app state, and model
credentials. Study Anything must not store them. Share only redacted Study
Anything artifacts back to Hermes:

- health and readiness receipts
- mastery summaries
- Agent audit/eval reports
- Obsidian export notes
- NotebookLM-style handoff metadata
- Cognitive Loop receipts and static HTML reports

Do not paste raw source text, raw diffs, learner answers, grading feedback,
generated private insights, Agent endpoints, raw Agent metadata, prompts, model
keys, cookies, bearer tokens, signed URLs, screenshots, keystrokes, mouse
coordinates, biometrics, or private browser/video/app context into shared logs
or support bundles.
