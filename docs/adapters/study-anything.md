# Study Anything Human Reconstruction / Learning Adapter

Study Anything is a compatibility adapter inside the CBB reference harness. It is
not the protocol, the Trust Kernel, or the top-level product identity.

## Adapter Responsibility

The adapter helps a human reconstruct and retain the control boundary behind an AI
delivery candidate. It can contribute:

- source-bound learning sessions;
- passive attention metadata for focus routing;
- active reconstruction checkpoints;
- understanding-gap and mastery evidence;
- redacted learning, audit, and handoff artifacts;
- mappings from existing `attention-reconstruction-*` receipts into future canonical
  qualified-reconstruction evidence.

The adapter may package evidence produced by other parts of the reference harness.
It does not independently authorize delivery.

## Boundary

- Passive attention is weak evidence and cannot pass a consequential gate alone.
- A learning score is not general reviewer qualification.
- Qualification is scoped to a project, boundary type, delivery scenario, and time.
- The adapter cannot expand a Delivery Trust Receipt or Customer Handoff Package.
- Real model keys, user-owned Agent credentials, raw customer data, screenshots,
  keystrokes, mouse coordinates, biometrics, and hidden reasoning remain outside the
  adapter evidence boundary.
- The adapter has no production mutation or automatic customer-sending authority.

## Platform Agents

Codex, Kimi, WorkBuddy, Hermes, or another platform Agent may call the adapter through
its historical API, Skill, CLI, or platform pack. The platform Agent owns model
choice, browsing, private tools, and credentials. Study Anything receives structured
inputs and emits redacted evidence.

Agent output is supporting material. The deterministic CBB gate remains the decision
authority.

## Compatibility

The following names remain stable for current adopters:

- Python distribution `study-anything`;
- Python package `study_anything`;
- existing `/v1/...` routes;
- `study_anything_*` platform tool names;
- Study Anything plugin and archive names;
- existing learning and attention reconstruction schema versions.

These are compatibility surfaces, not the current project positioning. See
[Naming and Compatibility](../naming-and-compatibility.md).

## Intended V1 Mapping

```text
Study Anything session evidence
  + attention reconstruction summary
  + scoped reviewer capability evidence
  -> cbb.qualified-reconstruction.v1
  -> cbb.evidence-bundle.v1
  -> deterministic CBB gate
```

The mapping may narrow or expire a claim. It may never increase delivery scope.
