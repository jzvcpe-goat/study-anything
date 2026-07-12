# Naming And Compatibility / 命名与兼容边界

## Purpose

This document separates current product identity from historical interfaces. A
positioning pivot should remove obsolete public framing without breaking existing
packages, routes, schemas, receipts, fixtures, or downstream adopters.

本文件把当前项目定位与历史接口分开。定位重构要删除过时的公开主语，但不能粗暴破坏
已经存在的包、路由、schema、收据、fixture 和下游接入。

## Canonical Vocabulary

| Name | Meaning | Public status |
|---|---|---|
| Delivery Clearance | Public product identity | Primary name |
| AI Delivery Clearance Protocol | Open protocol for scoped AI delivery clearance | Primary protocol name |
| AI 交付放行协议 | Canonical Chinese protocol name | Primary Chinese name |
| Delivery Clearance Reference Harness | This repository's local deterministic implementation | Primary implementation name |
| Dual Loop | Controlled Failure plus Qualified Human Reconstruction | Core mechanism |
| Trust Kernel | Deterministic, model-free authority layer | Core architecture term |
| Evolution Layer | Agentic/RAG/tool-assisted proposal and evidence layer | Adaptive architecture term |
| Delivery Trust Receipt | Claim-bounded decision artifact | Core receipt |
| Customer Handoff Package | Portable package above an allowed receipt | Package, not trust source |
| Study Anything Adapter | Human Reconstruction / Learning Adapter | Adapter name |
| Cognitive Loop | Internal evidence and evolution workflow | Internal subsystem |
| CBB / `cbb.*` | Existing Protocol v1 schema and implementation namespace | Compatibility only |

## Compatibility-Only Identifiers

The following identifiers remain because existing code and adopters depend on them:

- GitHub repository name `study-anything`;
- Protocol v1 `cbb.*` schema identifiers and `apps/api/study_anything/cbb/` modules;
- Python distribution `study-anything`;
- Python package `study_anything`;
- `/v1/...` API routes and existing `study-anything-*` schema versions;
- `study_anything_*` platform tool names;
- `cognitive_loop_*` Python modules, scripts, fixtures, artifact paths, and schema
  versions;
- generated archive names used by published release and adoption evidence;
- historical release notes and quality-audit records.

These names identify compatibility surfaces. They must not be presented as the
current top-level product identity.

## Banned Current Framing

The following wording must not appear in current primary positioning, repository
metadata, API title, or generated artifact branding:

- `Cognitive Loop System` as the project name;
- Cognitive Black Box Protocol or CBB Protocol as the current public product name;
- Study Anything as the main product or protocol;
- “learning system” as the repository's primary category;
- Personal Plugin Mode or Professional HTML Artifact Mode as top-level product
  architecture;
- Neural Sync, Neural Publish, Neural Teams, or Catalyst as current product brands;
- AI review or generic human approval as a sufficient trust source.

Historical release notes, audit records, and compatibility fixtures may retain old
wording when changing it would falsify history. New references to those files must
label them as historical.

## Migration Rules

Classify every old identifier before changing it:

| Category | Action |
|---|---|
| Public framing | Replace now |
| Generated presentation branding | Replace now and update verifier assertions |
| Stable API/package/schema identifier | Preserve and document |
| Compatibility command | Preserve, add a future alias before deprecation |
| Historical record | Preserve unchanged |
| Unused obsolete label | Delete after search and tests prove no dependency |

## Technical Rename Criteria

Do not rename `study_anything` or `cognitive_loop_*` technical identifiers until all
of these exist:

1. a canonical replacement identifier;
2. an import, route, or artifact compatibility shim;
3. a machine-readable migration map;
4. tests for old and new consumers;
5. a deprecation period and removal version;
6. a no-new-reference gate;
7. rollback instructions;
8. updated generated assets and checksums.

This keeps the protocol honest: a branding cleanup cannot silently break receipt
verification or adopter workflows.

## Repository Metadata

The GitHub repository name is historical. Until a deliberate repository migration is
approved, the public description and topics must carry the current identity:

```text
Delivery Clearance: AI Delivery Clearance Protocol. No clearance, no delivery.
AI 交付放行协议：未经放行，不得交付。
```

Recommended topics:

```text
delivery-clearance
ai-delivery-clearance
ai-delivery-trust
trust-receipts
dual-loop
local-first
ai-agents
human-reconstruction
```

For the `v0.3.32-alpha` Personal Local Alpha, the GitHub release title is
`Delivery Clearance Personal Local Alpha`. The repository slug and Python distribution retain
`study-anything` as compatibility identifiers. A later repository-slug migration must first
preserve the existing GHCR package path and release-asset URLs; it is not bundled into this
personal-local release.

## Enforcement

Run:

```bash
python3 scripts/verify_cbb_positioning.py --check
```

The verifier checks canonical terms, banned current framing, compatibility notes,
package metadata, API title, generated artifact branding, and Delivery Clearance release-gate
wiring. It intentionally excludes historical release notes and quality-audit records.
