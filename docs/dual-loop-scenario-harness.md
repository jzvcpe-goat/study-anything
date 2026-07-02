# Dual Loop Scenario Harness

The Dual Loop Scenario Harness turns the Cognitive Black Box trust protocol into
one deterministic customer-delivery scenario.

It answers a narrow question:

```text
May this AI-generated customer handoff candidate be promoted inside the current
controlled local scope?
```

The answer is yes only when both loops pass:

- Controlled Failure Loop: the candidate failed, if at all, only inside an
  observable and reversible sandbox.
- Human Attention Reconstruction Loop: the human reconstructed the key failure
  boundaries through active checkpoints, not passive viewing.

The propagation gate treats both loops as equal weight. If either loop fails or
is missing, the candidate is blocked from customer handoff.

## What This Harness Emits

The runner emits metadata-only JSON artifacts:

```text
failure-contract-v1
sandbox-receipt-v1
attention-reconstruction-trace-v1
attention-reconstruction-summary-v1
dual-loop-gate-receipt-v1
delivery-trust-receipt-v1
customer-handoff-package-v1
dual-loop-trust-scenario-result-v1
```

`customer-handoff-package-v1` is emitted only in the passing scenario. Blocked
scenarios emit a blocked `delivery-trust-receipt-v1` and no handoff package.

## Scenario Matrix

| Case | Sandbox | Human Reconstruction | Gate | Customer Handoff |
| --- | --- | --- | --- | --- |
| `pass` | within budget | passed | allowed | package emitted |
| `attention-missing` | within budget | missing | blocked | no package |
| `risk-over-budget` | outside budget | passed | blocked | no package |
| `both-fail` | failed/outside budget | failed | blocked | no package |

This proves the product rule: a sandbox pass cannot dominate missing human
reconstruction, and human reconstruction cannot dominate sandbox risk.

## Commands

Run the harness:

```bash
python3 scripts/run_dual_loop_scenario_harness.py run --case all
```

Verify fixtures and report:

```bash
python3 scripts/verify_dual_loop_scenario_harness.py --check
```

Run the Dual Loop release subset:

```bash
./scripts/release_check.sh --dual-loop-only
```

## Boundary Model

The harness is local-first and metadata-only.

It does not:

- call models;
- start a daemon;
- send a customer message;
- mutate production;
- store raw source text;
- store raw report text;
- capture screenshots;
- capture keystrokes;
- capture mouse coordinates;
- capture eye tracking or biometrics;
- store real secrets, cookies, bearer tokens, signed URLs, or user-owned Agent
  credentials.

The AI sandbox and human cognition layer stay physically isolated. They exchange
only structured artifacts. The AI side never receives fine-grained attention
streams, and the human reconstruction side never receives production execution
authority.

## Non-Production Statement

This is not production approval. It is a deterministic local trust-protocol
sample for one customer-delivery scenario class. Real production use still
requires domain acceptance tests, operator-owned deployment approval,
customer-specific rollback planning, and legal/security review when required.
