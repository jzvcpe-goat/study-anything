# Diagnose Study Anything

Run local diagnostics when CodeBuddy/WorkBuddy cannot run Study Anything.

```bash
python3 scripts/verify_workbuddy_inline_learning_flow.py --check
python3 scripts/study_anything_cli.py health
python3 scripts/diagnose_adoption.py
python3 scripts/verify_platform_agent_tools.py
python3 scripts/verify_workbuddy_plugin_marketplace.py --check
```

Common fixes:

- If inline flow passes but HTTP fails, keep using inline mode in WorkBuddy.
- Start the fallback runtime with `./START_HERE.command` or `./scripts/launch_skill_mode.sh`.
- If localhost is blocked by the host platform, use a private reachable HTTP endpoint.
- If dependency install is slow, configure `PIP_INDEX_URL` or retry from a normal terminal.
- If Docker is unavailable, use Skill Mode first.

Only share redacted diagnostic output. Do not share real model keys, Agent
endpoint secrets, raw source text, learner answers, or private browser/app data.
