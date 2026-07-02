# CustomerHandoffPackage v1

CustomerHandoffPackage is the portable package layer above
`delivery-trust-receipt-v1`.

It is not a new trust source. It cannot approve a candidate that the
DeliveryTrustReceipt blocked, and it cannot expand the customer delivery scope.
It only packages scoped evidence, limitations, rollback, reconstruction
summaries, external eval receipt references, artifact digests, and platform
Agent handoff instructions.

## What It Proves

A valid `customer-handoff-package-v1` proves only this:

> This candidate handoff package is consistent with the scoped local
> deterministic DeliveryTrustReceipt and referenced Dual Loop evidence.

It does not prove:

- production approval
- legal certification
- compliance certification
- security certification
- general model correctness
- customer outcome guarantees
- AI-review-only sufficiency

## Required Inputs

The package builder requires structured metadata artifacts:

- `delivery-trust-receipt-v1`
- `failure-contract-v1`
- `sandbox-receipt-v1`
- `attention-reconstruction-summary-v1`
- `dual-loop-gate-receipt-v1`
- optional external eval receipt refs marked `supporting_only_not_sufficient`

The package cannot be built without an allowed DeliveryTrustReceipt.

## Package Contents

The package includes:

- manifest
- delivery trust receipt
- claim boundary
- limitations
- rollback strategy
- controlled failure summary
- human reconstruction summary
- Dual Loop gate receipt
- external eval receipt refs
- artifact refs and SHA-256 digests
- WorkBuddy, Hermes, and Codex handoff instructions
- provenance metadata

Every artifact ref in the manifest has a digest. The verifier recomputes those
digests and rejects drift.

## Boundary Rules

The verifier rejects packages when:

- the DeliveryTrustReceipt is missing
- the DeliveryTrustReceipt is blocked
- the package scope exceeds the DeliveryTrustReceipt scope
- external eval receipts are marked sufficient
- high-risk handoff lacks available rehearsed rollback
- the claim boundary is missing
- secret-like content appears
- artifact digests do not match
- the ZIP cannot validate offline
- Agent handoff instructions request production mutation or scope escalation

## Privacy Rules

The package is metadata-only by default. It must not contain:

- raw source text
- raw customer payload
- screenshots
- keystrokes
- attention streams
- model prompts
- model keys
- cookies
- bearer tokens
- signed URLs
- platform Agent credentials
- production mutation
- model calls
- automatic customer sending

## CLI

Build JSON, HTML, and ZIP output:

```bash
python3 scripts/customer_handoff_package.py build \
  --delivery-trust-receipt fixtures/customer-handoff/pass/delivery-trust-receipt.json \
  --failure-contract fixtures/customer-handoff/pass/failure-contract.json \
  --sandbox-receipt fixtures/customer-handoff/pass/sandbox-receipt.json \
  --attention-summary fixtures/customer-handoff/pass/attention-reconstruction-summary.json \
  --dual-loop-gate fixtures/customer-handoff/pass/dual-loop-gate-receipt.json \
  --output .cognitive-loop/artifacts/customer-handoff/customer-handoff-package.json \
  --html-output .cognitive-loop/artifacts/customer-handoff/customer-handoff-package.html \
  --zip-output .cognitive-loop/artifacts/customer-handoff/customer-handoff-package.zip
```

Validate a ZIP offline:

```bash
python3 scripts/customer_handoff_package.py validate-zip \
  --zip platform/generated/study-anything-customer-handoff-package.zip
```

## Verifier

Run the deterministic verifier:

```bash
python3 scripts/verify_customer_handoff_package.py --check
```

Regenerate fixtures and public package artifacts:

```bash
python3 scripts/verify_customer_handoff_package.py --write
```

Generated public artifacts:

- `platform/generated/study-anything-customer-handoff-package.json`
- `platform/generated/study-anything-customer-handoff-package.html`
- `platform/generated/study-anything-customer-handoff-package.zip`

## Platform Agent Handoff

WorkBuddy, Hermes, and Codex may open the package, inspect claim boundaries,
display limitations, validate digests, and prepare operator-owned notes. They
must not mutate production, escalate the scope, request credentials, or send the
package to a customer automatically.
