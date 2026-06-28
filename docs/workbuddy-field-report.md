# WorkBuddy / CodeBuddy Field Report

Date: 2026-06-27 21:45 PDT
Last updated: 2026-06-27 22:34 PDT

Purpose: verify the Study Anything plugin in a real CodeBuddy Code CLI runtime,
not only with repository-local generators.

## Environment

- Host: macOS local workspace.
- Node: `v22.22.3`.
- npm: `10.9.8`.
- CodeBuddy package: `@tencent-ai/codebuddy-code@2.112.1`.
- CodeBuddy binary: isolated install under `<temp-codebuddy-prefix>`.
- CodeBuddy home/config: isolated `HOME=<temp-codebuddy-home-local>`.
- Study Anything runtime: Skill Mode at `http://127.0.0.1:8000`.
- Study Anything health: `{"status":"ok","version":"0.3.31-alpha"}`.

No real model API keys, learner answers, raw private source text, or Agent
endpoint secrets were used in this field run.

## Commands Run

```bash
npm install --prefix <temp-codebuddy-prefix> @tencent-ai/codebuddy-code@2.112.1
HOME=<temp-codebuddy-home> <temp-codebuddy-prefix>/node_modules/.bin/codebuddy --version
```

```bash
HOME=<temp-codebuddy-home> \
  <temp-codebuddy-prefix>/node_modules/.bin/codebuddy \
  plugin validate .codebuddy-plugin/marketplace.json
```

```bash
HOME=<temp-codebuddy-home> \
  <temp-codebuddy-prefix>/node_modules/.bin/codebuddy \
  plugin validate plugins/study-anything/.codebuddy-plugin/plugin.json
```

```bash
HOME=<temp-codebuddy-home-local> \
  <temp-codebuddy-prefix>/node_modules/.bin/codebuddy \
  plugin marketplace add <repo>
```

```bash
HOME=<temp-codebuddy-home-local> \
  <temp-codebuddy-prefix>/node_modules/.bin/codebuddy \
  plugin install study-anything@study-anything --scope local
```

```bash
STUDY_ANYTHING_DATA_DIR=<temp-runtime> \
  API_PORT=8000 \
  ./scripts/launch_skill_mode.sh
python3 scripts/study_anything_cli.py health
```

In the Codex shell field runner, background processes were reclaimed after the
launcher returned. Keeping the API in a foreground terminal preserved the
runtime for plugin validation:

```bash
STUDY_ANYTHING_DATA_DIR=<temp-runtime> \
  API_PORT=8000 \
  ./scripts/launch_skill_mode.sh --foreground
python3 scripts/study_anything_cli.py --api-base http://127.0.0.1:8000 health
```

```bash
HOME=<temp-codebuddy-home-local> \
  <temp-codebuddy-prefix>/node_modules/.bin/codebuddy \
  -p \
  --output-format json \
  --max-turns 1 \
  --permission-mode bypassPermissions \
  --channels plugin:study-anything@study-anything \
  "/study-anything:learn Rust ownership basics"
```

## Results

| Check | Result | Evidence |
| --- | --- | --- |
| CodeBuddy CLI installs in isolated prefix | pass | `codebuddy --version` returned `2.112.1` |
| Marketplace manifest validates | pass | `codebuddy plugin validate .codebuddy-plugin/marketplace.json` returned `Validation passed` |
| Plugin manifest validates after fix | pass | `codebuddy plugin validate plugins/study-anything/.codebuddy-plugin/plugin.json` returned `Validation passed` |
| Local marketplace add | pass | `Marketplace 'study-anything' added successfully` |
| Local plugin install | pass | `Successfully installed plugin: study-anything@study-anything` |
| Study Anything runtime health | pass | `status=ok`, `version=0.3.31-alpha` |
| Foreground runtime in agent shell | pass | `launch_skill_mode.sh --foreground` kept the API available for CodeBuddy validation |
| Headless command without explicit channel | fail | `/study-anything:learn ... not found` |
| Headless command with explicit channel | partial pass | command reached CodeBuddy model/auth boundary |
| Full first lesson through CodeBuddy | not complete | blocked by CodeBuddy authentication in isolated HOME |

## Post-Merge Public Shorthand Run

After PR #267 was merged to `main`, the public GitHub shorthand path was
rerun from the normal host environment instead of a local marketplace path:

```bash
codebuddy plugin marketplace add jzvcpe-goat/study-anything
codebuddy plugin install study-anything@study-anything --scope local
STUDY_ANYTHING_DATA_DIR=<temp-runtime> API_PORT=8000 ./scripts/launch_skill_mode.sh --foreground
python3 scripts/study_anything_cli.py --api-base http://127.0.0.1:8000 health
codebuddy -p \
  --output-format json \
  --max-turns 6 \
  --permission-mode bypassPermissions \
  --channels plugin:study-anything@study-anything \
  "/study-anything:learn Rust ownership basics"
```

| Check | Result | Evidence |
| --- | --- | --- |
| Public marketplace add | pass | `Marketplace 'study-anything' added successfully` |
| Public plugin install | pass | `Successfully installed plugin: study-anything@study-anything` |
| Skill Mode runtime health | pass | `status=ok`, `version=0.3.31-alpha` |
| Public shorthand first lesson | not complete | `Authentication required. Please use /login command to sign in to your account` |
| Non-interactive `/login` attempt | not complete | `Authentication required. Please use /login command to sign in to your account` |

## Findings

1. Real CodeBuddy validation rejected the original plugin manifest because
   `skills` was a string. The fix is to generate both `commands` and `skills`
   as arrays in the marketplace entry and plugin manifest.

2. Headless CodeBuddy runs do not reliably auto-load the locally installed
   plugin. Use:

```bash
--channels plugin:study-anything@study-anything
```

3. The local plugin install writes local scope state to:

```text
.codebuddy/settings.local.json
```

That file is field-run state and should not be committed.

4. Without a logged-in CodeBuddy account, the first lesson cannot reach the
   model execution step. This reproduced both in an isolated HOME and after
   the post-merge public shorthand install. The real output is:

```text
Authentication required. Please use /login command to sign in to your account
```

This is a platform-account prerequisite, not a Study Anything runtime failure.
Non-interactive `codebuddy -p "/login"` returns the same authentication message;
login must be completed in a real interactive CodeBuddy/WorkBuddy session.

5. Some agent shells reclaim background processes after a successful launcher
   health check. For CodeBuddy headless validation, keep the Skill Mode API in a
   foreground terminal with `./scripts/launch_skill_mode.sh --foreground`.

6. Use `.github/ISSUE_TEMPLATE/platform_import_failure.md` with diagnostic code
   `workbuddy_auth_required` for logged-in WorkBuddy/CodeBuddy first-lesson
   acceptance follow-up.

## Current Verdict

The CodeBuddy/WorkBuddy plugin is now installable and schema-valid in real
CodeBuddy Code CLI 2.112.1. The public GitHub shorthand install path also
works from `main`. The full first lesson is not yet accepted as complete
because the final Agent execution requires a logged-in CodeBuddy account or
equivalent configured platform Agent.

## Next Acceptance Step

Rerun the public GitHub shorthand path from a logged-in CodeBuddy environment:

```bash
HOME=<logged-in-codebuddy-home> codebuddy plugin marketplace add jzvcpe-goat/study-anything
HOME=<logged-in-codebuddy-home> codebuddy plugin install study-anything@study-anything --scope local
STUDY_ANYTHING_DATA_DIR=<temp-runtime> API_PORT=8000 ./scripts/launch_skill_mode.sh
HOME=<logged-in-codebuddy-home> codebuddy -p \
  --channels plugin:study-anything@study-anything \
  "/study-anything:learn Rust ownership basics
Source passage: Rust uses ownership and borrowing to make memory safety a compile-time property.
Please create a Study Anything session, teach overview and glossary, grade this answer:
Ownership controls who can use and free a value.
Return session id and mastery evidence."
```

Acceptance requires CodeBuddy to return a non-empty learning result with:

- a Study Anything session id,
- overview or glossary content,
- answer grading or mastery evidence,
- no real model keys,
- no raw private source text in public report artifacts.
