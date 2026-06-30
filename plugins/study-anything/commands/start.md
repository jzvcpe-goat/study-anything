# Start Study Anything

Check the Study Anything WorkBuddy inline flow and explain HTTP fallback.

1. Preferred inline check:

```bash
python3 scripts/verify_workbuddy_inline_learning_flow.py --check
```

2. Run the deterministic WorkBuddy demo:

```bash
python3 scripts/workbuddy_learning_flow.py demo --case deepseek-pm-interview
```

3. Use HTTP fallback only when the host can preserve a local runtime:

```bash
./START_HERE.command
python3 scripts/study_anything_cli.py health
```

If the host cannot keep background processes alive, do not force HTTP. Use the
inline flow or the bounded demo:

```bash
./scripts/run_skill_mode_demo.sh
```

If the fallback runtime is remote or uses another port, set:

```bash
export STUDY_ANYTHING_API_BASE="http://127.0.0.1:8000"
```

Do not ask the user for model API keys for Study Anything. Real model
credentials stay inside CodeBuddy/WorkBuddy or the user's private Agent.
