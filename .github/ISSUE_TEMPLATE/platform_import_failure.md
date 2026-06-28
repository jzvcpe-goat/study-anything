---
name: Platform import failure
about: Request help with a redacted Study Anything platform adoption issue
title: "[Support]: Platform import failure - "
labels: support,platform-import
assignees: ""
---

<!--
schema_version: platform-support-issue-template-v1
release_target: v0.3.31-alpha
Do not paste raw source text, learner answers, Agent prompts, Agent endpoints, model keys,
browser/video private context, or personal profile data.
-->

## Summary

## Platform

- Platform id: <!-- kimi | codex | workbuddy | generic -->
- Study Anything release: v0.3.31-alpha
- Runtime mode: <!-- skill-mode | published-image | source-compose | other -->

## Command Ran

```sh
python3 scripts/verify_platform_field_rehearsal.py --check
```

## Diagnostic Code

<!-- Use one of: schema_mismatch, missing_local_gateway, unsupported_auth_mode, tool_naming_drift, timeout, cors_localhost, package_corruption, version_drift, workbuddy_auth_required -->

## WorkBuddy / CodeBuddy First-Lesson Acceptance

Use this section when `/plugin marketplace add jzvcpe-goat/study-anything` and
`/plugin install study-anything@study-anything` worked, but the first lesson did
not finish.

- CodeBuddy package/version: <!-- e.g. @tencent-ai/codebuddy-code@2.112.1 -->
- Marketplace add result: <!-- pass | fail -->
- Plugin install result: <!-- pass | fail -->
- Study Anything health result: <!-- status=ok | status=failed -->
- Command used:

```sh
codebuddy -p --channels plugin:study-anything@study-anything "/study-anything:learn <redacted lesson title>"
```

- If the output says `Authentication required`, run CodeBuddy interactively and
  complete `/login`, then rerun the command above.
- Acceptance evidence must include a session id plus overview/glossary or
  grading/mastery evidence. Do not paste raw source text, learner answers, or
  model keys.

## Fixture Or Quirk Id

<!-- Link to a fixture under fixtures/platform-import-failures/ or fixtures/platform-support-tickets/. -->

## Redacted Log Excerpt

```text
status=needs_attention
diagnostic_code=<redacted diagnostic code>
source_text_redacted=<yes>
answer_redacted=<yes>
agent_endpoint=<redacted>
model_or_judge_secret=<redacted>
```

## Next Commands Tried

- 

## Expected Result

## Actual Result
