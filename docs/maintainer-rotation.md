# Maintainer Rotation

Study Anything v0.3.19-alpha defines `maintainer-sla-labels-v1` and
`maintainer-rotation-checklist-v1` so external adopter issues can be handled
when the original author is not present.

Run:

```bash
python3 scripts/verify_platform_onboarding_readiness.py --check
```

Then open:

```text
platform/generated/study-anything-platform-triage-dashboard.md
```

## SLA Labels

- `intake`: new external adopter issue; first check support bundle completeness.
- `needs-repro`: maintainer needs a fixture-backed reproduction.
- `confirmed`: maintainer reproduced the issue with current generated assets.
- `blocked-by-platform`: host platform capability or localhost policy blocks the path.
- `docs-fix`: documentation or copyable command fix is enough to close.
- `release-blocker`: a supported happy path fails with current release assets.
- `resolved`: reporter or maintainer verified the closing command.

## Rotation Checklist

1. Run `python3 scripts/verify_platform_onboarding_readiness.py --check`.
2. Review `platform/generated/study-anything-platform-triage-dashboard.md`.
3. Review every fixture under `fixtures/platform-release-blockers/`.
4. Confirm each support category can be reproduced without private user data.
5. Close only with a verified command, documented platform limitation, or merged fix.

## Close Standard

Every issue should close with one of these:

- a passing command output from the current release assets;
- a linked docs or code fix;
- a documented platform limitation with a fallback path;
- a confirmed duplicate linked to an existing release-blocker fixture.

Never ask for raw source text, learner answers, Agent prompts, real Agent
endpoints, model keys, browser context, app context, video context, or personal
profile data.
