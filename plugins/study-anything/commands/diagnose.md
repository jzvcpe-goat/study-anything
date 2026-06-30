# Diagnose Study Anything

Run local diagnostics when CodeBuddy/WorkBuddy cannot run Study Anything.

```bash
python3 scripts/workbuddy_learning_flow.py doctor
python3 scripts/verify_workbuddy_inline_learning_flow.py --check
python3 scripts/study_anything_cli.py health
python3 scripts/diagnose_adoption.py
python3 scripts/verify_platform_agent_tools.py
python3 scripts/verify_workbuddy_plugin_marketplace.py --check
```

Common fixes:

- If inline flow passes but HTTP fails, keep using inline mode in WorkBuddy.
- If `doctor` says feature files are missing, install the latest plugin pack or update the checkout outside the WorkBuddy sandbox; do not rely on `git pull` inside a restricted sandbox.
- If `run` rejects deterministic input, let WorkBuddy/Kimi generate teaching, quiz, and grading first.
- Start the fallback runtime with `./START_HERE.command` or `./scripts/launch_skill_mode.sh`.
- If localhost is blocked by the host platform, use a private reachable HTTP endpoint.
- Proxy variables are sanitized by the inline CLI; users should not need to type `env -u HTTP_PROXY`.
- If dependency install is slow, configure `PIP_INDEX_URL` or retry from a normal terminal.
- If Docker is unavailable, use Skill Mode first.

Only share redacted diagnostic output. Do not share real model keys, Agent
endpoint secrets, raw source text, learner answers, or private browser/app data.
