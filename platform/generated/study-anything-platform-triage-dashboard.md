# Study Anything Platform Triage Dashboard

Schema: `platform-triage-dashboard-v1`
Version: `v0.3.29-alpha`
Status: `pass`

## Fixture Coverage

- support categories: 5
- release blockers: 5
- platform walkthroughs: 4

## Release Blockers

- `tool_import_blocker` -> `platform_import_failure`: `python3 scripts/verify_ecosystem_submission_pack.py`
- `local_gateway_blocker` -> `local_gateway_failure`: `python3 scripts/verify_openai_compatible_gateway.py --gateway-only`
- `published_image_blocker` -> `published_image_pull_failure`: `python3 scripts/verify_published_image_launch.py --tag v0.3.29-alpha --pull-timeout-seconds 180 --allow-pull-timeout-report`
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

## Privacy

This dashboard is generated from mock fixtures and schema metadata only. It must not include raw
source text, learner answers, real Agent endpoints, model keys, or browser/video private context.
