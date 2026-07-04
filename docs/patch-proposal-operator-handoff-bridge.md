# Patch Proposal Operator Handoff Bridge

This layer connects `Sandboxed Patch Proposal Rehearsal` to operator handoff
rehearsals without executing code, applying patches, opening PRs, posting PR
comments, sending customer-visible output, publishing externally, or mutating
production.

It is intentionally a metadata-only bridge. The bridge consumes a
`sandboxed-patch-proposal-envelope-v1` and emits
`patch-proposal-operator-handoff-bridge-receipt-v1`. A ready receipt means only:

- the upstream sandboxed patch proposal was allowed;
- the operator actively reconstructed the no-mutation boundary;
- rollback and test refs are visible;
- delivery-class operator handoff reports are attached as metadata refs;
- a host platform operator may decide whether to continue outside Study
  Anything / Cognitive Black Box.

It does not mean the patch body exists, the repository changed, a PR was opened,
customer communication was approved, external publication was approved, or a
production change was approved.

## Generated Evidence

- `platform/generated/study-anything-patch-proposal-operator-handoff-bridge.json`
- `platform/generated/study-anything-patch-proposal-operator-handoff-bridge.md`
- `platform/generated/study-anything-patch-proposal-operator-handoff-bridge.html`
- `fixtures/patch-proposal-operator-handoff-bridge/*/patch-proposal-operator-handoff-bridge-receipt.json`

## Verifier

```bash
python3 scripts/verify_patch_proposal_operator_handoff_bridge.py --check
```

Regenerate deterministic fixtures and reports:

```bash
python3 scripts/verify_patch_proposal_operator_handoff_bridge.py --write
```

## Privacy Boundary

The bridge must not include raw spec/eval bodies, raw patch bodies, raw diffs,
raw customer payloads, screenshots, attention streams, real secrets, Agent
endpoint secrets, model keys, or local absolute paths. It stores only refs,
hashes, booleans, bounded delivery-class metadata, and explicit claim limits.

## Failure Cases

The verifier proves the bridge blocks:

- blocked upstream sandboxed patch proposal;
- missing active operator reconstruction;
- raw patch or raw diff requests;
- repository mutation requests;
- customer-visible action requests;
- external publication requests;
- production mutation requests.

## 中文说明

这一层不是自动改代码的工具，而是把“沙盒里的 patch proposal”转换成一个可审计的
操作员交接包。它只包含引用、hash、布尔检查和边界声明，不包含真实 patch、diff、
客户内容或密钥。

`ready` 只表示：平台 Agent 或人工操作员可以在 Study Anything / Cognitive Black
Box 之外决定是否继续。它不表示代码已经被修改，也不表示 PR、客户交付、外部发布
或生产变更已经被批准。
