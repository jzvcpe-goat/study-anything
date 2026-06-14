# Support Desk

Study Anything v0.3.19-alpha uses a GitHub-first support desk for external platform adoption. The
goal is simple: when a Kimi-compatible, Codex, WorkBuddy-style HTTP, or generic OpenAPI setup fails,
the user can file a useful issue without exposing private learning data or user-owned Agent secrets.

The machine-readable evidence is `platform-support-triage-v1`:

```bash
python3 scripts/generate_platform_support_triage.py --check
python3 scripts/verify_platform_support_triage.py --check
python3 scripts/verify_platform_support_triage.py \
  --pack platform/generated/study-anything-platform-adoption-pack.zip
```

The generated report lives at:

```text
platform/generated/study-anything-platform-support-triage.json
```

## User Issue Flow

Use one of the checked-in templates:

```text
.github/ISSUE_TEMPLATE/platform_import_failure.md
.github/ISSUE_TEMPLATE/local_gateway_failure.md
.github/ISSUE_TEMPLATE/published_image_pull_failure.md
.github/ISSUE_TEMPLATE/agent_eval_evidence_failure.md
.github/ISSUE_TEMPLATE/docs_confusion.md
```

Each template asks for a `platform-support-issue-template-v1` report shape:

- release version
- platform id
- command ran
- diagnostic code
- fixture or quirk id
- redacted log excerpt
- next commands already tried

Do not paste source text, learner answers, grading feedback, generated insights, Agent prompts, real
Agent endpoints, model keys, personal profiles, or browser, app, and video private context. Keep
support upload manual. Study Anything should not automatically send support bundles anywhere.

## Support Bundle Contract

The support bundle is `platform-support-bundle-v1`. Required fields are:

- `release_version`
- `platform_id`
- `command_ran`
- `diagnostic_code`
- `fixture_id`
- `redacted_log_excerpt`
- `next_commands_tried`

The fixtures under `fixtures/platform-support-tickets/` use
`platform-support-ticket-fixture-v1` and are mock-only examples. They link back to
`platform-import-failure-fixture-v1` entries from v0.3.17 so maintainers can reproduce common
failures without asking for private user material.

## Maintainer Playbook

The support triage report covers eight failure IDs:

- `schema_mismatch`
- `missing_local_gateway`
- `unsupported_auth_mode`
- `tool_naming_drift`
- `timeout`
- `cors_localhost`
- `package_corruption`
- `version_drift`

For each failure, the playbook must define:

- first response
- reproduction steps
- close criteria
- escalation criteria

Use the mock fixture first, then ask the reporter for only the missing support-bundle fields. Close
the issue when the verifier passes, the fixture diagnosis matches the user's redacted report, and the
next command is clear. Escalate only when a supported platform still fails after the current release
assets pass local verification.

## Release Gate

`scripts/release_check.sh` runs both support triage commands. A release is not ready if the report,
issue templates, ticket fixtures, platform packs, ecosystem submission metadata, adoption pack, or
docs drift from the support desk contract.

## Onboarding Readiness And SLA

v0.3.19-alpha adds `platform-onboarding-readiness-v1` on top of support triage. It proves first
external adopter walkthroughs, `maintainer-sla-labels-v1`, `maintainer-rotation-checklist-v1`,
`platform-triage-dashboard-v1`, and `platform-release-blocker-fixture-v1` fixtures are present.

```bash
python3 scripts/generate_platform_onboarding_readiness.py --check
python3 scripts/verify_platform_onboarding_readiness.py --check
python3 scripts/verify_platform_onboarding_readiness.py \
  --pack platform/generated/study-anything-platform-adoption-pack.zip
```

Use `docs/adopter-onboarding.md` for the first adopter path and
`docs/maintainer-rotation.md` for SLA labels. The dashboard is generated at:

```text
platform/generated/study-anything-platform-triage-dashboard.md
```

The SLA labels are `intake`, `needs-repro`, `confirmed`, `blocked-by-platform`, `docs-fix`,
`release-blocker`, and `resolved`.
