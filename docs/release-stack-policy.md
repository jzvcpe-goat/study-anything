# Release-Stack Recursion Guard

The release stack is an evidence chain, not a machine that must consume its own
tail forever. A self-intake PR records meaningful release evidence after a
substantive change. It must not automatically create another self-intake PR just
because the previous PR was itself a self-intake.

This policy stops the #280 -> #281 -> #282 recursion pattern from continuing
into an automatic #283 self-intake.

## Default Rule

Do not self-intake every merged PR by default.

A PR requires release-stack self-intake only when it changes one of these
substantive release surfaces:

- release policy;
- release-stack verifier behavior;
- public evidence-chain contents or semantics;
- the current release-stack group.

Everything else should use one of two paths:

- batch archive: maintenance-only evidence is grouped later;
- product runway: product work returns to Dual Loop trust protocol development.

## Self-Intake Stop Rule

A self-intake-only PR does not require a follow-up self-intake merely because it
updated release-stack metadata, hashes, or generated package evidence. That kind
of PR has already recorded its release-stack purpose.

For the current chain, PR #282 is the terminal self-intake recursion boundary.
The next PR is not automatically forced to be a self-intake for #282.

## Batch Archive Rule

Use batch archive when the PR is:

- generated evidence hash refresh only;
- docs copy or operator wording that does not change release policy;
- ordinary maintenance without a new public claim;
- a self-intake-only PR whose only effect was to record the previous group.

Batch archive preserves auditability without turning every release-stack change
into another release-stack change.

## Product Runway Rule

When release-stack evidence is current and no substantive release surface has
changed, the next default destination is product development, not release-stack
maintenance.

The next product runway is Cognitive Black Box / Dual Loop trust protocol:
scenario harnesses that show how AI-generated delivery can become trustworthy
without excessive human re-review and without black-box AI-reviewing-AI.

## Machine Contract

The machine-readable policy is:

```text
.cognitive-loop/release-stack-policy.yaml
```

The verifier is:

```bash
python3 scripts/verify_release_stack_policy.py --check
```

Generated evidence:

```text
platform/generated/study-anything-release-stack-policy.json
```
