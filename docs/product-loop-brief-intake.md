# Product Loop Brief Intake Gate

Product Loop Brief Intake Gate is the bridge between Product Spec/Eval
Authoring Gate and Product Loop Harness. It consumes a metadata-only
`product-spec-eval-brief-v1` and emits a
`product-loop-brief-intake-receipt-v1`.

When the brief and boundary checks pass, the receipt includes Product Loop
Harness candidate artifacts:

- `product-loop-scenario-v1`
- `product-loop-run-v1`

The gate does not execute product work, call models, store raw specs, store raw
eval bodies, send customer-visible messages, publish externally, mutate
production, or skip directly to the Delivery Trust Harness.

## What It Proves

- A Product Spec/Eval brief is the only allowed source for Product Loop Harness
  candidate creation.
- The source brief is referenced by ID/hash only; the intake receipt does not
  embed raw spec or eval bodies.
- Active developer/product-loop boundary reconstruction is required.
- AI-review-only evidence is rejected.
- External feedback scope expansion is blocked.
- Production mutation and customer-visible action are blocked.
- The only allowed next boundary is `product_loop_harness`.
- The Product Loop run may promote only to `delivery_trust_harness`, not to
  production or customer handoff.

## Artifacts

- `product-loop-brief-intake-receipt-v1`: allow/block gate receipt.
- `product-loop-scenario-v1`: Product Loop Harness scenario created only for
  the pass case.
- `product-loop-run-v1`: Product Loop Harness run created only for the pass
  case.
- `product-loop-brief-intake-gate-verification-v1`: verifier report for
  pass/block cases and privacy-injection checks.
- `fixtures/product-loop-brief-intake/*/product-loop-brief-intake-receipt.json`:
  deterministic gate fixtures.
- `fixtures/product-loop-brief-intake/pass/product-loop-scenario.json` and
  `fixtures/product-loop-brief-intake/pass/product-loop-run.json`: the only
  deterministic Product Loop candidate fixtures created by this gate.
- `platform/generated/study-anything-product-loop-brief-intake.json`:
  machine-readable verification report.
- `platform/generated/study-anything-product-loop-brief-intake.md`:
  operator-readable summary.
- `platform/generated/study-anything-product-loop-brief-intake.html`:
  static HTML report for artifact-console style review.

## Cases

- `pass`: valid Product Spec/Eval brief plus active developer vision creates
  Product Loop scenario/run candidate artifacts.
- `blocked-missing-brief`: no source brief was provided.
- `blocked-invalid-brief`: source brief is invalid or routed to the wrong
  boundary.
- `blocked-missing-developer-vision`: active developer/product-loop
  reconstruction is missing.
- `blocked-external-scope-expansion`: external feedback tries to move directly
  into production/customer scope.
- `blocked-ai-review-only`: requester tries to use AI review as the sufficient
  trust basis.
- `blocked-production-mutation`: requester tries to mutate production.
- `blocked-skip-to-delivery-harness`: requester tries to bypass Product Loop
  Harness and jump straight to Delivery Trust Harness.

## Run

```bash
python3 scripts/verify_product_loop_brief_intake.py --check
```

To refresh deterministic fixtures and generated reports:

```bash
python3 scripts/verify_product_loop_brief_intake.py --write
```

To gate one local Product Spec/Eval brief:

```bash
python3 scripts/product_loop_brief_intake.py \
  --brief fixtures/product-spec-eval-authoring-gate/pass/product-spec-eval-brief.json \
  --output-dir .cognitive-loop/artifacts/product-loop-brief-intake
```

## Claim Boundary

This gate only claims that a metadata-only Product Spec/Eval brief can become a
Product Loop Harness candidate after active developer/product-loop boundary
reconstruction. It does not claim implementation completion, production
readiness, customer delivery approval, full Delivery Trust Harness completion,
or general model correctness.
