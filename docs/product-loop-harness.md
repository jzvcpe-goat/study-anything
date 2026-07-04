# Product Loop Harness

Product Loop Harness is the reusable engineering layer behind Cognitive Black
Box product development. It turns the three feedback loops into deterministic,
metadata-only evidence before a candidate can move into the Delivery Trust
Harness.

The canonical upstream path is:

```text
Product Spec/Eval Authoring Gate
  -> product-spec-eval-brief-v1
  -> Product Loop Brief Intake Gate
  -> product-loop-scenario-v1 + product-loop-run-v1
  -> Product Loop Harness
```

This keeps the harness from accepting raw specs, raw eval bodies, or generic
`product-spec-evals.json` claims as the only bridge evidence.

## Three Loops

```text
Agentic Coding Loop        Developer Feedback Loop        External Feedback Loop
coding agent               developer vision               external feedback
~minutes                   ~hours                         ~days
```

Each loop is equal weight:

- the agentic loop must have product spec/evals and cannot promote by AI review
  alone;
- the developer loop must include active reconstruction of the product boundary;
- the external loop must be structured feedback metadata and cannot expand scope
  to production by itself.

## Artifacts

The harness emits two contracts:

- `product-loop-scenario-v1`
- `product-loop-run-v1`

The generated report is:

```text
platform/generated/study-anything-product-loop-harness.json
```

Fixtures live under:

```text
fixtures/product-loop-harness/
```

Brief-intake bridge fixtures live under:

```text
fixtures/product-loop-brief-intake/
```

## Acceptance

```bash
python3 scripts/verify_product_loop_harness.py --check
```

To regenerate fixtures and the report:

```bash
python3 scripts/verify_product_loop_harness.py --write
```

To run the CLI directly:

```bash
python3 scripts/product_loop_harness.py run --case all
```

To verify the canonical brief-intake bridge:

```bash
python3 scripts/verify_product_loop_brief_intake.py --check
```

## Gate Rules

The harness allows promotion only when:

- product spec/evals are present;
- developer vision is present;
- external feedback stays within the allowed scope;
- AI-review-only evidence is rejected;
- no loop may dominate the others;
- no model calls, daemon, production mutation, raw feedback, raw product spec, or
  customer payload is stored.

The pass case promotes only to the Delivery Trust Harness, not to production.

## Blocked Fixtures

The deterministic fixtures prove these failures:

- `blocked-missing-product-spec-evals`
- `blocked-missing-developer-vision`
- `blocked-external-scope-expansion`
- `blocked-ai-review-only`
- `blocked-loop-dominance`

This layer is intentionally before customer handoff. Customer handoff still
requires Dual Loop receipts, Delivery Trust Receipt, and CustomerHandoffPackage.
