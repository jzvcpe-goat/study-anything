# Human Review Cockpit

The Human Review Cockpit is the local interaction surface for the observed
Native Agent vs Delivery Clearance pilot. It replaces long terminal sessions
with a browser workflow while preserving the same frozen packets, order seeds,
roles, receipt schemas, and `personal_local` claim boundary.

It runs only on `127.0.0.1`. It does not call a model, upload review material,
send a customer package, or authorize production use.

## Start The Cockpit

Run from the repository root:

```bash
.venv/bin/python scripts/delivery_clearance_review_cockpit.py --max-items 5
```

The installed entrypoint is equivalent:

```bash
.venv/bin/delivery-clearance-review --max-items 5
```

The command opens `http://127.0.0.1:8765`. Use `--no-open` when the browser
should not open automatically, or `--port 8766` when the default port is busy.

Before opening the UI, verify all three frozen queues without writing evidence:

```bash
.venv/bin/delivery-clearance-review --max-items 5 --dry-run
```

To review the committed real-project delivery sequence instead of the public benchmark
pilot, use its bounded two-mode protocol:

```bash
.venv/bin/delivery-clearance-review \
  --protocol docs/evaluation/real-project-v0.1-human-protocol.json \
  --max-items 4
```

That protocol enables boundary reconstruction and the full-review reference only. It does
not invent a blinded adjudicator or turn a machine-ready state into a release authorization.

To review the frozen real-Agent patch set, first generate its ignored local reviewer
materials, then run:

```bash
.venv/bin/delivery-clearance-review \
  --protocol docs/evaluation/real-agent-v0.1-human-protocol.json \
  --max-items 12
```

For this protocol, boundary reconstruction remains metadata-only. Full review reads the
actual issue and Agent patch from the Git-ignored local material directory. The server
checks both the patch digest and combined review-material digest before showing either
document. Raw material is never appended to the human-session JSONL.

## Three Physically Separate Review Tasks

The top segmented control switches between three local queues. Switching the
view does not merge their roles or evidence.

| Mode | Human task | Stored result |
| --- | --- | --- |
| Boundary reconstruction | Reconstruct scope, recipient, risk owner, visible failure, recovery, and prohibited use from the bounded packet. | Aggregate correctness, unresolved count, active-visible time, and optional workload. |
| Full review reference | Review the complete label-free metadata packet, then answer the same five boundary questions. | A separately timed full-review session using the same aggregate fields. |
| Blinded adjudication | Decide clear, restrict, hold, or deny using candidate evidence and the official scorer receipt. | Disposition, bounded rationale codes, role, scope, and integrity digest. |

Case IDs, reference labels, hidden tests, experimental arm identities, and
experimental arm decisions are not exposed in the browser state. The server
computes aggregate correctness after submission and does not return answer
feedback that could train the reviewer during the pilot.

## Evidence Locations

The Cockpit reads the canonical protocol at:

```text
docs/evaluation/pilot-v0.1-human-protocol.json
```

It appends review evidence to the paths frozen in that protocol:

```text
.delivery-clearance/benchmarks/pilot-v0.1-observed-human-sessions.jsonl
.delivery-clearance/benchmarks/pilot-v0.1-observed-adjudications.jsonl
```

Writes are append-only, flushed, and synchronized to disk for every completed
item. Existing matching receipts are skipped when a new Cockpit session starts.
An interrupted item is not recorded.

## Privacy And Security Boundary

The local service:

- binds only to `127.0.0.1`;
- accepts only trusted local host headers and same-origin JSON submissions;
- requires a per-process review token and per-item token;
- permits raw local candidate material only in `full_review_reference`, rejects symbolic
  links and repository escape, and fails closed on missing, oversized, non-UTF-8, or
  digest-mismatched material;
- sends no CORS permission and disables caching and framing;
- tracks only aggregate active-visible milliseconds in the browser;
- stores no raw answer sequence, attention stream, screenshot, keystroke,
  biometric data, free-form review notes, model prompt, or reviewer identity;
- never raises authority above `personal_local`.

The browser is an interaction surface, not a new trust source. Server-side code
revalidates every packet and creates the existing `human-review-session-v1` or
`blinded-adjudication-receipt-v1` artifact. Client-side state cannot change the
frozen expected answer codes, candidate digest, order seed, role, or output path.

## Interpretation Boundary

The current local project owner may complete more than one role for pilot
calibration only when that limitation is disclosed. This does not establish
reviewer independence. A confirmatory study still requires separately assigned
reviewers and adjudicators.

Completing the Cockpit queues proves that the required observed human evidence
was recorded under the frozen protocol. It does not by itself prove Delivery
Clearance effectiveness, cost-effectiveness, customer readiness, professional
qualification, or production approval.

## Verify

```bash
.venv/bin/python -m unittest discover \
  -s apps/api/tests \
  -p 'test_delivery_clearance_review_cockpit.py'

.venv/bin/python scripts/delivery_clearance_benchmark.py human-evidence-status \
  --packet-dir .delivery-clearance/benchmarks/pilot-v0.1-observed-assembly-v2/reviewer-packets \
  --human-sessions .delivery-clearance/benchmarks/pilot-v0.1-observed-human-sessions.jsonl \
  --adjudications .delivery-clearance/benchmarks/pilot-v0.1-observed-adjudications.jsonl \
  --output .delivery-clearance/benchmarks/pilot-v0.1-human-evidence-status.json
```

The status remains `incomplete` until every frozen case has one boundary
reconstruction, one separately timed full review, and one blinded adjudication.
