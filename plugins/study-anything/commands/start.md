# Start Study Anything

Start or verify the local Study Anything runtime for CodeBuddy/WorkBuddy.

1. From the Study Anything repository checkout, run:

```bash
./START_HERE.command
python3 scripts/study_anything_cli.py health
```

2. If the host cannot keep background processes alive, run the bounded demo:

```bash
./scripts/run_skill_mode_demo.sh
```

3. If the runtime is remote or uses another port, set:

```bash
export STUDY_ANYTHING_API_BASE="http://127.0.0.1:8000"
```

Do not ask the user for model API keys for Study Anything. Real model
credentials stay inside CodeBuddy/WorkBuddy or the user's private Agent.
