---
name: Platform import failure
about: Request help with a redacted Study Anything platform adoption issue
title: "[Support]: Platform import failure - "
labels: support,platform-import
assignees: ""
---

<!--
schema_version: platform-support-issue-template-v1
release_target: v0.3.18-alpha
Do not paste raw source text, learner answers, Agent prompts, Agent endpoints, model keys,
browser/video private context, or personal profile data.
-->

## Summary

## Platform

- Platform id: <!-- kimi | codex | workbuddy | generic -->
- Study Anything release: v0.3.18-alpha
- Runtime mode: <!-- skill-mode | published-image | source-compose | other -->

## Command Ran

```sh
python3 scripts/verify_platform_field_rehearsal.py --check
```

## Diagnostic Code

<!-- Use one of: schema_mismatch, missing_local_gateway, unsupported_auth_mode, tool_naming_drift, timeout, cors_localhost, package_corruption, version_drift -->

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
