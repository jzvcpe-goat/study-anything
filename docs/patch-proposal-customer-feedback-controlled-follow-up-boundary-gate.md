# Patch Proposal Customer Feedback Controlled Follow-up Boundary Gate

This gate is the next customer-feedback layer after the Patch Proposal Delivery
Trust Case Bridge. It converts metadata-only Delivery Trust case and handoff
refs into metadata-only follow-up envelope refs, but only after an active
operator or host-platform Agent reconstructs the customer follow-up boundary.

It is not a customer message sender. It does not generate or store a raw
follow-up body.

## Inputs

- `patch-proposal-delivery-trust-case-bridge-receipt-v1`
- `patch-proposal-delivery-trust-case-handoff-refs-v1`
- `patch-proposal-follow-up-boundary-reconstruction-v1`

The reconstruction must be active evidence from either:

- `operator`
- `host_platform_agent`

Passive attention is rejected. AI-review-only evidence is rejected.

## Required Evidence

The gate requires refs for all of these layers:

- Product Loop run
- Failure contract
- Sandbox receipt
- Attention reconstruction summary
- Dual-Loop gate receipt
- Delivery Trust receipt
- CustomerHandoffPackage
- Delivery Trust Case

The gate also checks that the handoff refs match the bridge receipt that emitted
them.

## Outputs

Passing cases emit:

- `patch-proposal-controlled-follow-up-boundary-receipt-v1`
- `patch-proposal-controlled-follow-up-envelope-refs-v1`

Blocked cases emit only the boundary receipt with deterministic blocked reasons.

## Non-Goals

This layer does not:

- include raw customer feedback;
- include a customer-visible follow-up body;
- send anything to a customer;
- mutate source code;
- mutate production;
- publish externally;
- call models;
- store secrets or user-owned Agent credentials;
- start a daemon or hosted service.

## Local Verification

```bash
python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_boundary_gate.py --check
```

To regenerate deterministic fixtures and public reports:

```bash
python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_boundary_gate.py --write
```

## CLI Demo

```bash
python3 scripts/patch_proposal_customer_feedback_controlled_follow_up_boundary_gate.py \
  --case all \
  --output-dir .cognitive-loop/artifacts/patch-proposal-customer-feedback-controlled-follow-up-boundary-gate
```

Expected summary:

- 3 ready cases prepare metadata-only envelope refs;
- blocked cases cover missing bridge evidence, missing active reconstruction,
  passive reconstruction, missing Product Loop or Dual-Loop refs, missing
  Delivery Trust Case refs, raw follow-up body attempts, customer sends, source
  mutation, production mutation, external publication, secrets, and model
  credentials.

## Claim Boundary

This gate claims only that a follow-up envelope ref is ready for controlled
operator or host-platform Agent handling. It does not claim the follow-up has
been written, reviewed, sent, accepted by a customer, or deployed.
