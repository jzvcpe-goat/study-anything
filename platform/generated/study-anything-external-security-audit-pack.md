# External Security Audit Pack

- Schema: `external-security-audit-pack-v1`
- Status: `ready_for_independent_audit`
- Version: `v0.3.31-alpha`
- Scope areas: `7`
- Source/evidence files: `27`
- Archive SHA-256: `a2ab7821fe008e67c17e74cd0b5899a2a50901cc62d1b6285bc6535ca72a6d8c`

This pack is ready for an external human-led security audit at a pinned commit.
It does not claim that an audit, penetration test, or production certification
has completed. AI-only review and repository self-certification are forbidden.

Verification:

```bash
python3 scripts/generate_external_security_audit_pack.py --check
python3 scripts/verify_external_security_audit_pack.py --check
```
