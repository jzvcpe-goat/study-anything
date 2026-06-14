# External Adopter Onboarding

Study Anything v0.3.28-alpha adds `platform-onboarding-readiness-v1` as the
first-adopter proof layer. It sits after the support desk: support triage proves
failures are reportable, while onboarding readiness proves a new operator can
complete the shortest happy path and knows what to send when it fails.

Run:

```bash
python3 scripts/generate_platform_onboarding_readiness.py --check
python3 scripts/verify_platform_onboarding_readiness.py --check
python3 scripts/verify_platform_onboarding_readiness.py \
  --pack platform/generated/study-anything-platform-adoption-pack.zip
```

The machine-readable report is:

```text
platform/generated/study-anything-platform-onboarding-readiness.json
```

The walkthrough section uses `first-external-adopter-walkthrough-v1`.

The dashboard views are:

```text
platform/generated/study-anything-platform-triage-dashboard.json
platform/generated/study-anything-platform-triage-dashboard.md
```

## Shortest Success Path

Use this for Kimi, Codex, WorkBuddy-style HTTP workspaces, and generic
OpenAPI/MCP-capable workspaces:

1. Start Study Anything with Skill Mode or the published image.
2. Import `platform/generated/study-anything-platform-openapi.json` or
   `platform/generated/study-anything-openai-tools.json`.
3. Ask the platform Agent to create one session, attach one cited reading,
   run quiz generation, answer once, and check mastery.
4. Run `python3 scripts/verify_external_adoption.py --pack platform/generated/study-anything-platform-adoption-pack.zip --copy-worktree`.

The expected evidence is `adoption-proof-v1`,
`platform-onboarding-readiness-v1`, `platform-triage-dashboard-v1`, and
`public-support-status-v1`.
Use the public status report to show external adopters current platform support
without exposing support bundle private fields.

## Failure Fallback Path

If the first run fails:

1. Run `python3 scripts/diagnose_adoption.py`.
2. Run `python3 scripts/verify_platform_support_triage.py --check`.
3. Pick the matching GitHub issue template.
4. Attach only `platform-support-bundle-v1` fields: version, platform,
   command, diagnostic code, fixture id, redacted log excerpt, and next
   commands tried.

Do not paste raw source text, learner answers, Agent prompts, real Agent
endpoints, model keys, browser context, app context, video context, or personal
profile data.

## Release Blocker Fixtures

The release-blocker fixtures live under:

```text
fixtures/platform-release-blockers/
```

Each fixture uses `platform-release-blocker-fixture-v1` and links back to a
support category. A blocker is real only when it breaks a documented shortest
success path for Kimi, Codex, WorkBuddy, or generic OpenAPI/MCP and the current
generated assets still reproduce the issue.

## Acceptance

A platform handoff is ready only when:

- `platform-onboarding-readiness-v1` passes.
- `platform-triage-dashboard-v1` has release blocker and privacy scan evidence.
- `platform-release-blocker-fixture-v1` fixtures are included in the adoption pack.
- `public-support-status-v1` can publish platform status without private support fields.
- `adoption-proof-v1` completes from the adoption pack.
- No real model keys or private learning material are stored by Study Anything.

## External Adopter Evidence

The v0.3.28-alpha onboarding closeout is `adopter-evidence-archive-v1`. It gives an external adopter
one metadata-only archive with public support status hashes, platform pack checksums, Docker manifest
commands, known limitations, and maintainer handoff checklist.

```bash
python3 scripts/verify_adopter_evidence_archive.py --check
```

Use it after the first successful walkthrough or when handing a blocked case to a platform maintainer.
