# Real Project Delivery Evaluation v0.1

## Why This Exists

The protocol is not useful if it can only classify invented fixtures. This evaluation
replays four real delivery states from the development history of Delivery Clearance
itself. Each state is checked in an isolated temporary Git clone. The source worktree is
read-only, and the result stores hashes, exit codes, bounded failure nodes, and timing
rather than source code or raw command output.

The evaluation asks one narrow question:

> Can the declared machine gates distinguish incomplete delivery states from a state that
> is ready for human boundary reconstruction?

It does not ask whether Delivery Clearance has already reduced user workload or error
rates. Those outcomes require real human sessions and a stronger paired study.

## Evaluation Set

The four cases come from one real PR repair sequence:

| Case | Repository state | Replayed check | Expected machine state |
| --- | --- | --- | --- |
| `rp-01` | Human Review Cockpit code added, Python supply-chain receipt stale | Python supply-chain check | `blocked` |
| `rp-02` | Supply-chain receipt refreshed, six downstream evidence nodes stale | Generated evidence topology | `blocked` |
| `rp-03` | Partial downstream refresh, five topology nodes still stale | Generated evidence topology | `blocked` |
| `rp-04` | Evidence topology converged, 59/59 declared nodes pass | Generated evidence topology | `ready_for_human_review` |

The frozen inputs and expected results are in
[`real-project-v0.1-scenarios.json`](real-project-v0.1-scenarios.json). The cases use full
commit SHAs and bounded expected failure markers. Their oracle is the exit status and
machine-readable failed-node set produced by the repository's own checks, not a model
opinion.

## Reproduce

From the repository root:

```bash
.venv/bin/python scripts/delivery_clearance_project_scenarios.py --replace
```

The command creates:

```text
validation/results/real-project-v0.1/
  scenario-set.json
  result.json
  report.md
  check-receipts/
  reviewer-packets/
```

Every check runs in a separate temporary clone. The runner verifies that the check did
not mutate Git-visible project state. A timeout, infrastructure failure, output mismatch,
unexpected failed-node set, or mutation makes the case fail closed.

## Observed Result

The committed July 14, 2026 run observed:

- four of four cases matched the frozen oracle;
- three incomplete historical states were blocked;
- one converged state became `ready_for_human_review`;
- zero cases were release-authorized without human review;
- all four checks left Git-visible state unchanged;
- raw source, raw check output, model calls, production mutation, and local absolute paths
  were excluded from the result.

The evidence is in
[`validation/results/real-project-v0.1`](../../validation/results/real-project-v0.1/).
This is one project and one incident sequence. It is mechanism evidence, not a general
effectiveness estimate.

## Complete The Human Comparison

Use the same real packets in the local Cockpit:

```bash
.venv/bin/delivery-clearance-review \
  --protocol docs/evaluation/real-project-v0.1-human-protocol.json \
  --max-items 4
```

The protocol exposes two physically separate tasks:

1. boundary reconstruction of scope, recipient, risk owner, visible failure, recovery,
   and prohibited use;
2. full metadata review followed by the same five questions.

The Cockpit records aggregate correctness, unresolved count, active-visible time, and
optional workload. It does not store raw answers or reviewer identity. These sessions
must be completed by a human; the repository currently records no completed human result
for this real-project set.

## Layered Evaluation Strategy

This real-project set complements, rather than replaces, the existing evaluations:

| Layer | Current asset | What it can establish |
| --- | --- | --- |
| State integrity | 14 verifier cases and 12 focused Personal Clearance tests | Stale, tampered, missing, failed, or mutated evidence fails closed |
| Real project replay | Four historical delivery states in this document | The declared gates can replay one real incomplete-to-converged sequence |
| Agent comparison | Frozen 40-case Native Agent vs Delivery Clearance harness | A paired methodology for comparing review mechanisms; human evidence remains incomplete |
| User value | Planned human full-review vs boundary-reconstruction sessions | Review time, workload, false clearance, false block, and decision-quality effects; not yet established |

The next useful expansion is not more variants from this same incident. It is a second
project and a different failure family, followed by preregistered human comparison.

## Claim Boundary

This run proves only that the declared checks reproduced three historical blockers and one
machine-ready state on the recorded repository revisions and local environment. A
machine-ready state is still blocked from release until a human reconstructs the boundary
and accepts responsibility. This is not production approval, customer validation,
independent audit, or evidence of statistically significant benefit.
