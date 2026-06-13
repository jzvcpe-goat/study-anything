# Adoption Telemetry And PMF Readiness

Study Anything v0.3.2 adds a local aggregate telemetry contract for OSS adoption and PMF review.
It is designed for Kimi-compatible tools, Codex Skills, WorkBuddy-style HTTP workspaces, and local
operators who need proof that the learning layer works without collecting private learning content.

## Contracts

- `GET /v1/adoption/telemetry` returns `adoption-telemetry-v1`.
- `GET /v1/pmf/readiness` returns `pmf-readiness-v1`.
- `POST /v1/pmf/export` remains the explicit-consent sharing boundary and now embeds both contracts.
- `scripts/verify_adoption_telemetry.py` validates the privacy contract locally and can also check a
  running API with `--api-base`.

## What It May Include

The telemetry is aggregate-only. It may include:

- clean-clone or current-worktree adoption success
- runtime modes such as Skill Mode or published image
- platform tool import success
- Agent eval and retrieval eval pass/fail status
- session counts, completion rate, repeat local learner counts, and mastery delta aggregates
- plugin validation counts
- explicit opt-in hosted-interest and feedback counts

## What It Must Never Include

The contracts must not include:

- raw source text, source titles, quiz prompts, learner answers, grading feedback, or generated insights
- raw user ids, individual user hashes, contact hashes, raw contacts, or freeform comments
- Agent endpoints, Agent metadata, model secrets, API keys, or bearer tokens
- browser history, video transcripts, app-private context, screenshots, or platform-private traces

## Operator Flow

Run the core verifier:

```bash
python3 scripts/verify_adoption_telemetry.py
```

When the API is running:

```bash
python3 scripts/verify_adoption_telemetry.py --api-base http://127.0.0.1:8000
curl http://127.0.0.1:8000/v1/adoption/telemetry
curl http://127.0.0.1:8000/v1/pmf/readiness
```

The verifier emits `adoption-telemetry-verification-v1`. Treat it as a release gate before claiming
platform-Agent adoption quality.

## Commercial Boundary

`pmf-readiness-v1` is not a sales switch. It keeps the standalone app and hosted paid services out of
the launch path until adoption evidence is strong enough. Early commercialization should prepare
future hosted sync, hosted publish, team workspaces, and trusted plugin operations rather than selling
the local OSS core.
