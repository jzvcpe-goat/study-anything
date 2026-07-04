# Spec/Eval Scenario Execution Rehearsal

Spec/Eval Scenario Execution Rehearsal is the bridge from Product Loop evidence
to sandboxed implementation work.

It consumes the Real-Adopter Scenario Import output:

```text
real-adopter issue summary
  -> product-spec-eval-brief-v1
  -> product-loop-run-v1
  -> spec/eval execution rehearsal
```

The layer proves one narrow claim:

```text
Executable implementation work may start only inside a controlled failure
sandbox, after active human boundary reconstruction, with no customer-visible
action and no production mutation.
```

It does not execute implementation work, call models, send customer messages,
publish externally, or mutate production.

## Artifacts

Each deterministic case emits:

- `spec-eval-acceptance-receipt-v1`
- `spec-eval-execution-rehearsal-receipt-v1`
- Dual Loop metadata artifacts when applicable:
  - `failure-contract-v1`
  - `sandbox-receipt-v1`
  - `attention-reconstruction-trace-v1`
  - `attention-reconstruction-summary-v1`
  - `dual-loop-gate-receipt-v1`

Generated public evidence:

```text
platform/generated/study-anything-spec-eval-scenario-execution-rehearsal.json
platform/generated/study-anything-spec-eval-scenario-execution-rehearsal.md
platform/generated/study-anything-spec-eval-scenario-execution-rehearsal.html
```

Fixtures:

```text
fixtures/spec-eval-scenario-execution-rehearsal/
```

## Cases

- `pass`
- `blocked-missing-sandbox`
- `blocked-missing-human-reconstruction`
- `blocked-ai-review-only`
- `blocked-customer-visible-action`
- `blocked-production-mutation`

## Acceptance

```bash
python3 scripts/verify_spec_eval_scenario_execution_rehearsal.py --check
```

To regenerate fixtures and reports:

```bash
python3 scripts/verify_spec_eval_scenario_execution_rehearsal.py --write
```

To run the CLI directly:

```bash
python3 scripts/spec_eval_scenario_execution_rehearsal.py --case all
```

## Boundary

This layer is still before customer delivery. A passing rehearsal only
authorizes a sandboxed implementation rehearsal boundary. It does not authorize
customer send, external publication, production deployment, or real-world
claims about model correctness.
