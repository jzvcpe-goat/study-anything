# Delivery Trust Case Harness

Delivery Trust Case Harness is the end-to-end assembly layer for Cognitive Black
Box. It answers one bounded question:

```text
Can this AI-generated candidate be handed to a customer inside the current
controlled, metadata-only scope?
```

It does not replace the lower layers. It requires them:

- Product Loop Harness must pass;
- Dual Loop propagation gate must pass;
- Delivery Trust Receipt must allow controlled handoff;
- CustomerHandoffPackage must validate without expanding scope;
- external eval receipts may support, but cannot be sufficient;
- AI-review-only evidence is rejected;
- automatic customer sending and production mutation stay blocked.

## Contracts

The case layer emits:

```text
delivery-trust-case-v1
```

The generated verifier report is:

```text
platform/generated/study-anything-delivery-trust-case-harness.json
platform/generated/study-anything-delivery-trust-case-harness.html
```

Fixtures live under:

```text
fixtures/delivery-trust-case/
```

## Acceptance

```bash
python3 scripts/verify_delivery_trust_case_harness.py --check
```

To regenerate deterministic fixtures and reports:

```bash
python3 scripts/verify_delivery_trust_case_harness.py --write
```

To run the CLI directly:

```bash
python3 scripts/delivery_trust_case_harness.py run --case all
```

## Scenario Matrix

- `pass`: all layers pass and the candidate is ready for controlled customer
  handoff.
- `blocked-product-loop`: Delivery Trust and CustomerHandoffPackage pass, but
  developer vision is missing, so Product Loop blocks the handoff.
- `blocked-dual-loop`: Product Loop passes, but sandbox risk exceeds budget, so
  Dual Loop and Delivery Trust block.
- `blocked-customer-handoff`: Product Loop, Dual Loop, and Delivery Trust pass,
  but the package attempts to expand scope.
- `blocked-ai-review-only`: downstream evidence passes, but the Product Loop
  rejects AI-review-only evidence.

## Claim Boundary

This harness proves deterministic metadata-only end-to-end gating for
controlled customer handoff. It does not prove production deployment approval,
real customer delivery, general model correctness, legal certification, or
security certification.
