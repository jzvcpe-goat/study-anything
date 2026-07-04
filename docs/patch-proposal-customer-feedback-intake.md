# Patch Proposal Customer Feedback Intake Receipt

Patch Proposal Customer Feedback Intake Receipt sits after Patch Proposal
Customer Delivery Outcome Receipt. It records only metadata that a customer,
operator, or host platform Agent response signal exists after an external
customer handoff.

This is not a customer inbox, reply store, follow-up sender, PR commenter,
publisher, repository mutator, model caller, daemon, or hosted service.

## Boundary

Allowed:

- read a recorded Patch Proposal Customer Delivery Outcome Receipt;
- record the feedback signal type as `customer_signal`, `operator_signal`, or
  `host_platform_agent_signal`;
- record a deterministic feedback signal reference hash;
- record source fixture refs and report refs;
- emit metadata-only feedback intake receipts and reports.

Blocked:

- raw customer replies;
- private customer data or requester identity;
- PR comment bodies;
- raw patch, diff, source, report, or repository file bodies;
- external publication payloads;
- production payloads;
- automatic follow-up sending;
- Study Anything PR commenting;
- source mutation;
- production mutation;
- secrets, cookies, bearer tokens, signed URLs, Agent endpoint credentials, and
  model keys.

## Cases

The verifier covers accepted and blocked feedback intakes:

- `pass-customer-signal`
- `pass-operator-signal`
- `pass-host-platform-agent-signal`
- `blocked-outcome-blocked`
- `blocked-missing-response-signal`
- `blocked-missing-signal-reference`
- `blocked-missing-claim-boundary`
- `blocked-missing-privacy-boundary`
- `blocked-raw-customer-reply`
- `blocked-private-customer-data`
- `blocked-pr-comment-body`
- `blocked-external-publication-payload`
- `blocked-production-payload`
- `blocked-automatic-follow-up`
- `blocked-source-mutation`
- `blocked-secret`
- `blocked-model-credential`

## Commands

Check committed fixtures and generated reports:

```bash
python3 scripts/verify_patch_proposal_customer_feedback_intake_receipt.py --check
```

Regenerate fixtures and reports after an intentional contract change:

```bash
python3 scripts/verify_patch_proposal_customer_feedback_intake_receipt.py --write
```

Generate temporary local feedback intake receipts:

```bash
python3 scripts/patch_proposal_customer_feedback_intake_receipt.py --case all --report
```

## Claim Boundary

The receipt proves only that Study Anything can represent customer/operator
response signals as metadata-only evidence after an external customer delivery
outcome. It does not store customer reply text, identify the customer, send
follow-ups, publish externally, comment on a PR, mutate source, mutate
production, or certify customer satisfaction.
