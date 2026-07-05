# Patch Proposal Customer Feedback Controlled Follow-up Feedback Intake

Patch Proposal Customer Feedback Controlled Follow-up Feedback Intake sits after
Patch Proposal Customer Feedback Controlled Follow-up Outcome Receipt. It records
only metadata that a customer, operator, or host-platform Agent response signal
exists after an external controlled follow-up action.

This is not a customer inbox, reply store, PR commenter, publisher, source
mutator, production mutator, model caller, daemon, hosted service, or Product
Loop backlog writer.

## Boundary

Allowed:

- read a recorded controlled follow-up outcome receipt;
- preserve Product Loop, Dual Loop, Delivery Trust Case, active reconstruction,
  and controlled follow-up outcome refs;
- record the feedback signal type as `customer_signal`, `operator_signal`, or
  `host_platform_agent_signal`;
- record deterministic signal and Product Loop backlog candidate reference
  hashes;
- emit metadata-only feedback intake receipts and reports.

Blocked:

- raw customer replies;
- customer identity or private customer data;
- PR comment bodies;
- raw patch, diff, source, report, or repository file bodies;
- external publication payloads;
- automatic follow-up sending;
- Product Loop backlog mutation;
- source mutation;
- production mutation;
- model calls;
- secrets, cookies, bearer tokens, signed URLs, Agent endpoint credentials, and
  model keys.

## Cases

The verifier covers accepted and blocked controlled follow-up feedback intakes:

- `pass-customer-signal`
- `pass-operator-signal`
- `pass-host-platform-agent-signal`
- `blocked-outcome-blocked`
- `blocked-missing-response-signal`
- `blocked-missing-signal-reference`
- `blocked-missing-product-loop-target`
- `blocked-missing-claim-boundary`
- `blocked-missing-privacy-boundary`
- `blocked-raw-customer-reply`
- `blocked-customer-identity`
- `blocked-private-customer-data`
- `blocked-pr-comment-body`
- `blocked-external-publication-payload`
- `blocked-automatic-follow-up`
- `blocked-product-loop-backlog-mutation`
- `blocked-source-mutation`
- `blocked-production-mutation`
- `blocked-model-call`
- `blocked-secret`
- `blocked-model-credential`

## Commands

Check committed fixtures and generated reports:

```bash
python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_intake.py --check
```

Regenerate fixtures and reports after an intentional contract change:

```bash
python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_intake.py --write
```

Generate temporary local feedback intake receipts:

```bash
python3 scripts/patch_proposal_customer_feedback_controlled_follow_up_feedback_intake.py --case all --report
```

## Claim Boundary

The receipt proves only that Study Anything can represent response signals after
a controlled follow-up outcome as metadata-only evidence and point toward a
Product Loop backlog candidate. It does not store customer reply text, identify
the customer, send follow-ups, publish externally, comment on PRs, mutate source,
mutate production, call models, or certify customer satisfaction.
