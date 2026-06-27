---
name: Agent eval evidence failure
about: Request help with a redacted Study Anything platform adoption issue
title: "[Support]: Agent eval evidence failure - "
labels: support,agent-eval
assignees: ""
---

<!--
schema_version: platform-support-issue-template-v1
release_target: v0.3.29-alpha
Do not paste raw source text, learner answers, Agent prompts, Agent endpoints, model keys,
browser/video private context, or personal profile data.
-->

## Summary

## Platform

- Platform id: <!-- kimi | codex | workbuddy | generic -->
- Study Anything release: v0.3.29-alpha
- Runtime mode: <!-- skill-mode | published-image | source-compose | other -->

## Command Ran

```sh
python3 scripts/verify_agent_eval_marketplace_enforcement.py --check
```

## Diagnostic Code

<!-- Use one of: agent_eval_evidence_missing, missing_required_command, version_drift -->

## Workflow Stage

<!-- cleanroom_bootstrap | platform_import | local_gateway | published_image_pull | agent_eval | docs -->

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

## Maintainer Replay

```sh
python3 scripts/replay_support_bundle.py --bundle support-bundle.json --issue-body
```

## Expected Result

## Actual Result
