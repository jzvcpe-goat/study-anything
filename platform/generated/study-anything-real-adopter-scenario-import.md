# Real-Adopter Scenario Import

Prove one bounded real-adopter issue summary can enter the Product Loop as metadata-only evidence and reach a concrete spec/eval brief without raw customer content or production effects.

## Pass Case

- Platform: `workbuddy`
- Tags: `deterministic_quality_gap, real_agent_not_invoked, version_drift, proxy_env_workaround`
- Target spec/eval theme: `real_agent_quality_and_version_drift_gate`
- Next boundary: `product_loop_harness_candidate`

## Blocked Cases

- `blocked-raw-issue-text`: `private_like_value_rejected`
- `blocked-identity`: `forbidden_private_field_rejected`
- `blocked-ai-review-only`: `active_reconstruction_missing`
- `blocked-production-mutation`: `requested_scope_outside_product_loop_budget`

## Privacy Boundary

The importer keeps raw issue text, identities, logs, screenshots, Agent credentials, customer-visible replies, external publication, and production mutation out of the Product Loop.
