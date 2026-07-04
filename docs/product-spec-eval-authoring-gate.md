# Product Spec/Eval Authoring Gate

Product Spec/Eval Authoring Gate is the boundary after Product Owner
Prioritization Gate. It consumes a metadata-only
`product-spec-eval-candidate-v1` and emits a
`product-spec-eval-authoring-receipt-v1`.

It can create a `product-spec-eval-brief-v1`, but only as metadata for the next
Product Loop Harness candidate. It does not store raw specs, raw acceptance
criteria, raw eval bodies, eval prompts, customer-visible messages, production
payloads, or user-owned Agent credentials. It also does not execute work, assign
priority, publish externally, mutate production, or skip to the Delivery Trust
Harness.

The generated brief should enter `Product Loop Brief Intake Gate` before Product
Loop Harness scenario/run artifacts are created.

## What It Proves

- A spec/eval candidate requires active authoring-boundary reconstruction.
- Invalid or incorrectly routed candidates cannot create a brief.
- Raw product specs and eval bodies are blocked.
- Automatic execution is blocked.
- Customer-visible action and production mutation are blocked.
- The only allowed next boundary is `product_loop_harness_candidate`.
- The generated brief remains metadata-only and is not ready for execution or
  Delivery Trust Harness.

## Artifacts

- `product-spec-eval-authoring-receipt-v1`: allow/block gate receipt.
- `product-spec-eval-brief-v1`: metadata-only brief created only for the pass
  case.
- `product-spec-eval-authoring-gate-verification-v1`: verifier report for
  pass/block cases and privacy-injection checks.
- `fixtures/product-spec-eval-authoring-gate/*/product-spec-eval-authoring-receipt.json`:
  deterministic gate fixtures.
- `fixtures/product-spec-eval-authoring-gate/pass/product-spec-eval-brief.json`:
  the only deterministic brief fixture.
- `platform/generated/study-anything-product-spec-eval-authoring-gate.json`:
  machine-readable verification report.
- `platform/generated/study-anything-product-spec-eval-authoring-gate.md`:
  operator-readable summary.
- `platform/generated/study-anything-product-spec-eval-authoring-gate.html`:
  static HTML report for artifact-console style review.

## Cases

- `pass`: valid spec/eval candidate plus active authoring reconstruction creates
  one metadata-only brief.
- `blocked-missing-authoring-reconstruction`: no active authoring reconstruction.
- `blocked-raw-spec-body`: requester tried to include raw product spec body.
- `blocked-automatic-execution`: requester tried to execute work immediately.
- `blocked-skip-to-delivery-harness`: requester tried to skip directly to
  Delivery Trust Harness.
- `blocked-production-mutation`: requester tried to mutate production.
- `blocked-customer-visible-action`: requester tried to send or expose a
  customer-visible action.
- `blocked-invalid-candidate-source`: source candidate is not from the
  spec/eval candidate queue.

## Run

```bash
python3 scripts/verify_product_spec_eval_authoring_gate.py --check
```

To refresh deterministic fixtures and generated reports:

```bash
python3 scripts/verify_product_spec_eval_authoring_gate.py --write
```

To gate one local spec/eval candidate:

```bash
python3 scripts/product_spec_eval_authoring_gate.py \
  --candidate fixtures/product-owner-prioritization-gate/pass/product-spec-eval-candidate.json \
  --output-dir .cognitive-loop/artifacts/product-spec-eval-authoring
```

## Claim Boundary

This gate only claims that a metadata-only spec/eval candidate can become a
metadata-only spec/eval brief after active authoring-boundary reconstruction. It
does not claim finished product spec quality, finished eval coverage, automatic
priority assignment, automatic execution, customer-visible delivery, production
readiness, external publication, or Delivery Trust Harness readiness.
