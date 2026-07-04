# Patch Proposal Customer Delivery Outcome Receipt

Patch Proposal Customer Delivery Outcome Receipt sits after Patch Proposal
Customer Delivery Rehearsal. It records only metadata that a human operator or
host platform Agent says an external customer handoff action happened outside
Study Anything.

This is not a sender, publisher, PR commenter, repository mutator, production
mutator, model caller, daemon, or hosted service.

## Boundary

Allowed:

- read a ready Patch Proposal Customer Delivery Rehearsal receipt;
- record the external actor type as `human_operator` or `host_platform_agent`;
- record a deterministic action reference hash;
- record source fixture refs and report refs;
- emit metadata-only outcome receipts and reports.

Blocked:

- customer-visible bodies;
- PR comment bodies;
- raw patch, diff, source, report, or repository file bodies;
- external publication payloads;
- production payloads;
- automatic customer sending;
- Study Anything PR commenting;
- source mutation;
- production mutation;
- secrets, cookies, bearer tokens, signed URLs, Agent endpoint credentials, and
  model keys.

## Cases

The verifier covers recorded and blocked outcomes:

- `pass-human-operator`
- `pass-host-platform-agent`
- `blocked-rehearsal-blocked`
- `blocked-missing-external-actor`
- `blocked-missing-action-reference`
- `blocked-missing-claim-boundary`
- `blocked-missing-privacy-boundary`
- `blocked-customer-visible-body`
- `blocked-pr-comment-body`
- `blocked-external-publication-payload`
- `blocked-production-payload`
- `blocked-automatic-send`
- `blocked-source-mutation`
- `blocked-secret`
- `blocked-model-credential`

## Commands

Check committed fixtures and generated reports:

```bash
python3 scripts/verify_patch_proposal_customer_delivery_outcome_receipt.py --check
```

Regenerate fixtures and reports after an intentional contract change:

```bash
python3 scripts/verify_patch_proposal_customer_delivery_outcome_receipt.py --write
```

Generate temporary local outcome receipts:

```bash
python3 scripts/patch_proposal_customer_delivery_outcome_receipt.py --case all --report
```

## Claim Boundary

The receipt proves only that Study Anything can record metadata-only evidence of
an external customer handoff outcome. It does not prove content quality, send any
message, publish externally, comment on a PR, mutate source, mutate production,
or certify truth or security.
