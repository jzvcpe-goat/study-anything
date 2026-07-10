# Threat Model

## Protected Assets

- OIDC identity assertions and opaque principal or tenant bindings.
- Workspace membership, session state, HITL tasks, and learning exports.
- Agent provider configuration and allowed outbound Agent destinations.
- Local API tokens, deployment configuration, and public signing keys.
- Plugin packages, backup archives, sync packages, and release artifacts.
- Dual Loop, Delivery Trust, and release evidence integrity.

## Trust Boundaries

1. Client or platform Agent to the Study Anything API.
2. OIDC issuer assertion to hosted identity middleware.
3. API authorization to workspace, session, and tenant-filtered stores.
4. Study Anything to a user-controlled HTTP Agent endpoint.
5. Plugin package to local plugin quarantine and installation.
6. Local data to backup, restore, sync, and export artifacts.
7. Repository source to CI, SBOM, generated evidence, and release packages.

## Threat Actors

- Unauthenticated network client.
- Authenticated user attempting cross-tenant or cross-workspace access.
- Compromised or malicious allowed Agent gateway.
- Malicious plugin or tampered distribution package.
- Dependency or CI supply-chain attacker.
- Local process with access to the same host account.
- Operator misconfiguration or stale identity signing material.

## Required Abuse Cases

| ID | Abuse case | Expected boundary |
| --- | --- | --- |
| TM-01 | Missing, expired, forged, or wrong-audience hosted token | Reject before route execution |
| TM-02 | Body or query identity spoofing | Ignore supplied identity in hosted mode |
| TM-03 | Cross-tenant session, workspace, HITL, or Agent lookup | Return no cross-tenant resource data |
| TM-04 | Same-tenant cross-workspace retrieval | Require source workspace read permission |
| TM-05 | Agent endpoint SSRF, redirect, credential, or origin bypass | Reject outside exact configured policy |
| TM-06 | Session identifier path traversal or symlink escape | Reject before filesystem access |
| TM-07 | Malicious or digest-mismatched plugin | Quarantine; do not execute entrypoints |
| TM-08 | Backup or package traversal and tampering | Reject before restore or extraction |
| TM-09 | Secret, token, raw learning content, or private path in evidence | Fail privacy verifier |
| TM-10 | AI-only approval or missing human reconstruction | Block Dual Loop promotion |
| TM-11 | Dependency or generated artifact drift | Fail lock, hash, SBOM, or topology gate |
| TM-12 | Hosted route without tenant-scoped storage | Fail closed until scoped |

## Out Of Scope For Repository-Only Evidence

- Security of an external identity provider or platform Agent implementation.
- Customer cloud account configuration and network perimeter controls.
- Physical host compromise or a fully privileged local operating-system user.
- Legal, regulatory, financial, medical, or factual certification.
- Availability and incident response claims not exercised in a deployed target.

These exclusions do not remove deployment risk. The external report must state
which deployed controls were tested and which remained outside its engagement.
