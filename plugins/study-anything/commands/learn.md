# Learn With Study Anything

Use Study Anything for a source-bound learning loop. Ask the user for the topic,
the source material, and a short reference label if they have not provided them.

Preferred OpenAPI tool import:

```text
platform/generated/study-anything-platform-openapi.json
```

CLI fallback:

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

Return the session id, overview, glossary, quiz prompt, answer feedback, and
mastery summary. Keep raw private source text and learner answers out of public
logs or marketplace evidence.
