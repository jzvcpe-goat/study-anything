# Generated Evidence Topology

The release-facing platform assets form a dependency graph, not a flat list of files. Some consumer
reports read the adoption pack and are then included in the next adoption pack. The orchestrator makes
that feedback explicit and refreshes until the checked assets reach a fixed point.

## Check Every Declared Node

```bash
python3 scripts/generated_evidence_topology.py --check
```

Check mode runs every node even after one fails, then emits a metadata-only receipt at:

```text
.cognitive-loop/artifacts/release/generated-evidence-topology-receipt.json
```

Use `execution.failed_node_ids` to see the complete stale set. Each terminal failure also prints the
single node command that can be rerun.

## Refresh In Dependency Order

```bash
python3 scripts/generated_evidence_topology.py --refresh
```

Refresh mode:

1. validates unique node IDs and all declared dependencies;
2. rejects hard dependency cycles;
3. runs writers in hard-dependency order;
4. checks every node;
5. repeats for at most three passes when feedback-edge outputs have not converged;
6. stops immediately after a writer failure so retries cannot hide a broken generator.

No shell is used to execute nodes. Every command is a fixed repository-owned Python argument list.
Commands have a per-node timeout and do not require a model call or production mutation.

## Scope And Claim Boundary

The graph covers the release-distribution evidence chain: platform Agent assets and replay evidence,
published-image and release bootstrap evidence, plugin packs, handoff evidence, platform
bundle/adoption pack, external consumer drills, maintainer ledger, and adopter archive.

It intentionally does not claim to cover every generated fixture or every verifier in the repository.
Feature-specific contracts remain owned by their existing verifier gates. The orchestrator supplements
those gates; it does not replace or weaken them.

The receipt stores node IDs, aggregate statuses, dependency counts, timings, and a graph fingerprint.
It excludes command output, environment values, secrets, source text, learner answers, and local
absolute paths. `--refresh` changes only repository-generated assets.
