# External Security Audit Pack

- Schema: `external-security-audit-pack-v1`
- Status: `ready_for_independent_audit`
- Version: `v0.3.31-alpha`
- Scope areas: `7`
- Source/evidence files: `56`
- Archive SHA-256: `8e3bb0248a4aa013c4941b5ecca44f48da26211efb9ab0062fe091ac656f59aa`

This pack is ready for an external human-led security audit at a pinned commit.
It does not claim that an audit, penetration test, or production certification
has completed. AI-only review and repository self-certification are forbidden.

Verification:

```bash
python3 scripts/generate_external_security_audit_pack.py --check
python3 scripts/verify_external_security_audit_pack.py --check
```
