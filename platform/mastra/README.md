# Cognitive Loop Mastra Adapter Pack

This pack is a copy-ready adapter scaffold for external Mastra projects. It is not the
shipped Study Anything runtime, does not start Mastra from this repository, and does not
store model keys.

Use it when a platform Agent or maintainer wants to run Cognitive Loop project evidence
through a Mastra workflow while keeping Study Anything as the local-first contract and
evidence source.

## What It Provides

- `cognitive-loop-mastra-adapter.ts`: a TypeScript workflow scaffold using Mastra
  workflow steps, HITL suspend/resume schemas, and a Human Mastery Gate mapping.
- `manifest.json`: a machine-readable file list, privacy boundary, and implementation
  status.
- `python3 scripts/verify_cognitive_loop_mastra_adapter.py --check`: local verification
  that the pack is present, metadata-only, and included in generated platform bundles.
- `python3 scripts/verify_cognitive_loop_mastra_runtime_dry_run.py --check`: a local
  runtime rehearsal that proves high-risk suspension, approved resume, rejected bail, and
  Event Store projection without starting Mastra from this repository.
- `python3 scripts/verify_cognitive_loop_mastra_runtime_service.py --check`: a repo-local
  runtime verifier that starts the isolated `platform/mastra-runtime/` package against
  `@mastra/core` with metadata-only evidence.
- `python3 scripts/verify_cognitive_loop_mastra_runtime_durable.py --check`: a repo-local
  durability verifier that persists a suspended workflow to local libSQL storage, then
  resumes or bails from a separate Node process using watcher-generated metadata evidence.

## Install Into A Mastra Project

Create or open a Mastra project, then copy the TypeScript file into your Mastra workflow
directory:

```bash
npm create mastra@latest cognitive-loop-runtime --default --llm openai
cp platform/mastra/cognitive-loop-mastra-adapter.ts cognitive-loop-runtime/src/mastra/workflows/
```

The adapter expects an external platform Agent or local operator to pass Cognitive Loop
metadata:

- `projectId`
- `loopRunId`
- `decisionCardId`
- `eventStorePath`
- `artifactRefs`
- `risk`
- `constraints`

It does not accept raw source text, diff bodies, learner answers, prompts, Agent endpoint
secrets, or model API keys.

## HITL Mapping

The adapter maps Cognitive Loop Human Mastery Gate state onto Mastra workflow behavior:

- low-risk runs pass through without suspension;
- risky runs suspend with a redacted gate payload;
- approvals resume the workflow;
- explicit rejections bail with a redacted rejection reason.

This mirrors Mastra's workflow HITL pattern while preserving Cognitive Loop as the source
of truth for project evidence.

## Current Boundary

Status: adapter contract pack plus metadata-only runtime dry-run harness plus minimal
repo-started runtime MVP with a local libSQL suspend/resume proof.

This repository still does not ship a watcher daemon, realtime HTML console, hosted service,
or production storage operations. Manual watcher ingest creates metadata-only `ProjectEvent`
artifacts through `scripts/cognitive_loop_watcher_ingest.py`, and the durable verifier proves
the repo-local runtime can persist and recover a Human Mastery Gate snapshot without storing
source text, diff bodies, prompts, endpoints, or keys.
