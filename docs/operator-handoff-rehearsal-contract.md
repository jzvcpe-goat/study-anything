# Operator Handoff Rehearsal Contract

This contract is the shared delivery boundary for class-specific operator
handoff rehearsals.

It proves that supported delivery classes can prepare an operator decision from
metadata-only evidence without sending anything to a customer/requester, posting
PR comments, publishing externally, mutating production, or reading raw
payloads.

## Contract

Every supported delivery class must provide:

- one passing class-specific operator handoff rehearsal report;
- exactly one ready case;
- at least one blocked case family for source failure;
- at least one blocked case family for missing human/operator understanding;
- at least one blocked case family for automatic external action attempts;
- at least one blocked case family for raw payload requests;
- explicit claim boundaries that keep customer send approval and production
  approval outside the system.

Current supported classes are Code Review, Client Report, and Support Response.

The generic contract does not replace the class-specific verifiers. It checks
that all current delivery classes obey the same operator handoff shape.

## Boundary

The contract is metadata-only. It must not include raw source text, raw diffs,
raw reports, raw support replies, raw ticket payloads, requester identity, raw
customer payloads, screenshots, attention streams, secrets, user-owned Agent
credentials, model calls, production mutations, customer sends, support reply
sends, external publication, or automatic PR comments.

## Verify

```bash
python3 scripts/verify_operator_handoff_rehearsal_contract.py --check
```
