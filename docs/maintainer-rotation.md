# Maintainer Rotation

Study Anything v0.3.29-alpha defines `maintainer-sla-labels-v1` and
`maintainer-rotation-checklist-v1` so external adopter issues can be handled
when the original author is not present.

Run:

```bash
python3 scripts/verify_platform_onboarding_readiness.py --check
```

Then open:

```text
platform/generated/study-anything-platform-triage-dashboard.md
platform/generated/study-anything-public-maintainer-dashboard.md
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
6. Run `python3 scripts/verify_platform_public_support_status.py --check` before publishing a public dashboard.

## Close Standard

Every issue should close with one of these:

- a passing command output from the current release assets;
- a linked docs or code fix;
- a documented platform limitation with a fallback path;
- a confirmed duplicate linked to an existing release-blocker fixture.

Never ask for raw source text, learner answers, Agent prompts, real Agent
endpoints, model keys, browser context, app context, video context, or personal
profile data.

## Public Dashboard

`public-support-status-v1` maps the SLA labels above into
`public-status-linkage-fixture-v1` fixtures. The public dashboard can publish
platform status, known blocker fixture ids, fixture hashes, labels, and
verification commands, but not the private support bundle payload.

## Maintainer Handoff Archive

`adopter-evidence-archive-v1` is the v0.3.29-alpha maintainer handoff package.
Run `python3 scripts/verify_adopter_evidence_archive.py --check` before a release, public retry
request, or platform submission. Link the `adopter-evidence-fixture-v1` fixture id for the current
state, then attach only the archive checksum, public command, public limitation, and release URL.
