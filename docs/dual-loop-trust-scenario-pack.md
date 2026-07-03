# Dual Loop Trust Scenario Pack

The Dual Loop Trust Scenario Pack is the first portable product surface for
Cognitive Black Box. It packages the existing deterministic trust harness into a
downloadable, metadata-only bundle that another operator or platform Agent can
inspect, unzip, and verify locally.

It is not a standalone app and it does not call a model. Its job is narrower:
show how an AI-generated customer handoff candidate can be allowed only when
both trust loops pass.

## What It Proves

The pack proves one customer-delivery scenario class:

```text
May this AI-generated customer handoff candidate be promoted inside the current
controlled local scope?
```

The answer is allowed only when:

- the controlled failure loop stayed inside an observable, reversible sandbox;
- the human reconstructed the key failure boundaries through active checkpoints;
- the Dual Loop gate allowed promotion;
- the delivery trust receipt preserved the claim boundary;
- the customer handoff package did not expand scope.

If the sandbox passes but human reconstruction is missing, the pack blocks. If
human reconstruction passes but sandbox risk is outside budget, the pack blocks.
If evidence is AI-review-only, the pack blocks.

## Generated Assets

```text
platform/generated/study-anything-dual-loop-trust-scenario-pack.json
platform/generated/study-anything-dual-loop-trust-scenario-pack.md
platform/generated/study-anything-dual-loop-trust-scenario-pack.zip
platform/generated/study-anything-dual-loop-trust-scenario-pack.sha256
```

The ZIP has a single root directory and includes:

- Dual Loop scenario fixtures;
- Cognitive Black Box tri-loop delivery fixtures;
- schema files;
- runner and verifier scripts;
- operator docs;
- generated evidence reports;
- a beginner-readable `SCENARIO_PACK_README.md`.

## Commands

Generate or refresh the pack:

```bash
python3 scripts/generate_dual_loop_trust_scenario_pack.py
```

Verify the generated pack:

```bash
python3 scripts/generate_dual_loop_trust_scenario_pack.py --check
python3 scripts/verify_dual_loop_trust_scenario_pack.py --check
```

Run the source harnesses directly:

```bash
python3 scripts/run_dual_loop_scenario_harness.py run --case all
python3 scripts/verify_dual_loop_scenario_harness.py --check
python3 scripts/cbb_delivery_harness.py run --case all
python3 scripts/verify_cbb_delivery_harness.py --check
```

## Boundary

This pack is local-first and metadata-only.

It does not:

- call models;
- start a daemon or hosted service;
- mutate production;
- send messages to customers;
- include raw source text or raw report text;
- include screenshots, keystrokes, mouse coordinates, eye tracking, or
  biometrics;
- include real secrets, cookies, bearer tokens, signed URLs, or user-owned Agent
  credentials.

## How This Helps Platform Agents

Codex, Kimi, WorkBuddy, Hermes, or another platform Agent can use the pack as a
stable trust-protocol sample:

1. unzip the pack;
2. inspect the claim boundary and trust rules;
3. run the included verifiers;
4. compare a future real delivery case against the same artifact contracts.

The platform Agent may own model calls, browsing, project context, and external
tool access. Cognitive Black Box owns the local trust protocol, structured
artifact bridge, and gate receipts.

## Claim Boundary

Current claim:

```text
This pack proves deterministic local metadata-only Dual Loop and CBB scenario
behavior for customer-delivery readiness.
```

Not claimed:

- production deployment approval;
- real customer acceptance;
- general model correctness;
- legal compliance certification;
- security certification.
