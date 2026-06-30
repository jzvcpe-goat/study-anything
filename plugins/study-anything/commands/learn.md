# Learn With Study Anything

Use Study Anything for a WorkBuddy-owned source-bound learning loop. WorkBuddy
should gather the topic, source material, learner profile, and user answer in
conversation; then use its own model to create teaching claims, glossary terms,
quiz items, and grading feedback.

Before calling Study Anything, WorkBuddy must create `workbuddy-learning-input.json`
with `agent_evidence.generated_by_platform_agent=true`, `platform_agent`, and a
non-demo `model_label` such as `Kimi model via WorkBuddy`. If this evidence is
missing, `run` should fail and WorkBuddy should generate the lesson content with
its own model first.

Preferred inline flow:

```bash
python3 scripts/workbuddy_learning_flow.py run \
  --input workbuddy-learning-input.json \
  --output workbuddy-learning-output.json \
  --markdown study-card.md
```

For a deterministic diagnostic example only:

```bash
python3 scripts/workbuddy_learning_flow.py demo --case deepseek-pm-interview
```

Never use deterministic demo content as the learner-facing lesson.

Do not show the user raw session ids. Keep `session_ref` in WorkBuddy hidden
context and respond conversationally with overview, glossary, quiz, feedback,
mastery, and export options.

Fallback OpenAPI tool import:

```text
platform/generated/study-anything-platform-openapi.json
```

HTTP CLI fallback:

```bash
python3 scripts/study_anything_cli.py start \
  --title "$ARGUMENTS" \
  --text "PASTE_SOURCE_TEXT_HERE" \
  --reference "workbuddy-source"

python3 scripts/study_anything_cli.py teach <SESSION_ID> --layer overview
python3 scripts/study_anything_cli.py teach <SESSION_ID> --layer glossary
python3 scripts/study_anything_cli.py answer <SESSION_ID> --text "USER_ANSWER"
python3 scripts/study_anything_cli.py mastery <SESSION_ID>
```

Keep raw private source text and learner answers out of public logs or
marketplace evidence.
