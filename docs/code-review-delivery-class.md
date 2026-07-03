# Code Review Delivery Class Handoff

This slice maps the Delivery Trust Case Pack into the first concrete delivery
class: a metadata-only code-review handoff. It answers a narrow question:
when may an AI-assisted code-review result be handed to an operator or customer
as controlled delivery evidence?

It does not claim model correctness, complete vulnerability discovery, security
certification, merge approval, deployment approval, or permission to post
comments to a PR automatically.

## Artifacts

- `code-review-handoff-case-v1`: one metadata-only handoff case.
- `code-review-delivery-class-verification-v1`: verifier report for the pass
  and blocked fixtures.
- `fixtures/code-review-delivery-class/*/code-review-handoff-case.json`:
  deterministic pass and blocked examples.
- `platform/generated/study-anything-code-review-delivery-class.json`: generated
  machine-readable report.
- `platform/generated/study-anything-code-review-delivery-class.html`: static
  HTML report for human inspection.

## Gate Logic

The pass fixture is allowed only when all required loops pass:

- Product Loop evidence exists.
- Dual Loop gate is allowed.
- Delivery Trust Case is allowed.
- Customer handoff package is ready.
- Human reconstruction checkpoint passed.
- Sandbox risk remains within budget.
- Source-grounding citations are present.

The blocked fixtures prove the non-negotiable boundaries:

- Missing human reconstruction blocks handoff, even if the sandbox side is
  otherwise healthy.
- Sandbox risk outside budget blocks handoff, even if human reconstruction is
  present.
- AI-review-only evidence blocks handoff; external eval receipts are supporting
  evidence only and cannot replace Product Loop or Dual Loop evidence.

## Privacy Boundary

The code-review delivery class is metadata-only. It must not include raw diff,
raw source text, raw review text, screenshots, keystrokes, mouse coordinates,
eye tracking, biometrics, cookies, bearer tokens, signed URLs, real secrets, or
user-owned Agent credentials.

The CLI and verifier do not call models, start daemons, mutate production, post
PR comments, send customer messages, merge code, or deploy anything.

## Commands

Generate deterministic local artifacts:

```bash
python3 scripts/code_review_delivery_class_handoff.py --case all
```

Refresh fixtures and generated reports:

```bash
python3 scripts/verify_code_review_delivery_class_handoff.py --write
```

Verify the delivery class:

```bash
python3 scripts/verify_code_review_delivery_class_handoff.py --check
```

The verifier also runs negative checks that reject raw diff fields, automatic PR
commenting, production mutation, and treating external eval receipts as
sufficient by themselves.
