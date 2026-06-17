# Study Anything Public Maintainer Dashboard

Schema: `public-maintainer-dashboard-v1`
Version: `v0.3.30-alpha`
Status: `pass`

## Platforms

- `kimi`: `supported_for_first_adopter`
- `codex`: `supported_for_first_adopter`
- `workbuddy`: `supported_for_first_adopter`
- `generic`: `supported_for_first_adopter`

## Known Blocker Fixtures

- `tool_import_blocker` -> `platform_import_failure`: `python3 scripts/verify_ecosystem_submission_pack.py`
- `local_gateway_blocker` -> `local_gateway_failure`: `python3 scripts/verify_openai_compatible_gateway.py --gateway-only`
- `published_image_blocker` -> `published_image_pull_failure`: `python3 scripts/verify_published_image_launch.py --tag v0.3.30-alpha --pull-timeout-seconds 180 --allow-pull-timeout-report`
- `agent_eval_blocker` -> `agent_eval_evidence_failure`: `python3 scripts/verify_agent_eval_marketplace_enforcement.py --check`
- `support_bundle_privacy_blocker` -> `docs_confusion`: `python3 scripts/verify_platform_onboarding_readiness.py --check`

## Maintainer Labels

- `intake`
- `needs-repro`
- `confirmed`
- `blocked-by-platform`
- `docs-fix`
- `release-blocker`
- `resolved`

## Public Verification Commands

- `python3 scripts/verify_platform_public_support_status.py --check`
- `python3 scripts/generate_platform_public_support_status.py --check`
- `python3 scripts/verify_platform_onboarding_readiness.py --check`
- `python3 scripts/verify_platform_support_triage.py --check`

## Privacy

This dashboard is generated from schema metadata, status labels, fixture hashes, and copyable
commands only. It must not include raw source text, learner answers, Agent prompts, real Agent
endpoints, model keys, personal profiles, or browser/video/app private context.
