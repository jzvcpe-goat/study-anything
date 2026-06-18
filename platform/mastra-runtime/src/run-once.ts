import { humanMasteryGateStep } from "./workflows/cognitive-loop-mastra-adapter.js";
import { createMastraRuntime } from "./runtime.js";

type JsonRecord = Record<string, unknown>;

const mastra = createMastraRuntime({
  storageFile: process.env.COGNITIVE_LOOP_MASTRA_STORAGE_FILE,
});
const workflow = mastra.getWorkflow("cognitiveLoopRuntimeAdapterWorkflow");

function artifact(kind: string, path: string): JsonRecord {
  return {
    artifactId: `artifact-${kind}`,
    kind,
    path,
    sha256: "a".repeat(64),
    schemaVersion: `cognitive-loop-${kind}-v1`,
    status: "pass",
  };
}

function buildInput(overrides: JsonRecord = {}): JsonRecord {
  return {
    projectId: "repo-started-mastra-runtime-project",
    loopRunId: "loop-repo-started-mastra-runtime",
    decisionCardId: "dec-repo-started-mastra-runtime",
    actor: "study-anything-local-runtime",
    eventStorePath: ".cognitive-loop/mastra-runtime-service.sqlite",
    artifactRefs: [
      artifact("project_snapshot", ".cognitive-loop/events/project-snapshot.json"),
      artifact("decision_card", ".cognitive-loop/events/decision-card.json"),
      artifact("event_store", ".cognitive-loop/events/event-store.json"),
      artifact("watcher_ingest", ".cognitive-loop/events/watcher-ingest.json"),
    ],
    risk: {
      level: "high",
      requiresHumanGate: true,
      reasons: ["repo-started runtime needs explicit operator approval"],
    },
    constraints: {
      metadataOnly: true,
      noRawSourceText: true,
      noDiffBodies: true,
      noAgentSecrets: true,
      noModelKeys: true,
    },
    ...overrides,
  };
}

function summarizeResult(result: JsonRecord): JsonRecord {
  return {
    status: result.status,
    suspended: Array.isArray(result.suspended) ? result.suspended : [],
    result: result.result ?? null,
  };
}

async function runApprovedPath(): Promise<JsonRecord> {
  const run = await workflow.createRun();
  const started = (await run.start({ inputData: buildInput() as never })) as JsonRecord;
  if (started.status !== "suspended") {
    throw new Error(`Expected high-risk workflow to suspend, got ${String(started.status)}`);
  }
  const resumed = (await run.resume({
    step: humanMasteryGateStep,
    resumeData: {
      approved: true,
      reviewer: "local-operator",
      reason: "Metadata-only Event Store evidence and rollback path were reviewed.",
    },
  })) as JsonRecord;
  if (resumed.status !== "success") {
    throw new Error(`Expected approved workflow to succeed, got ${String(resumed.status)}`);
  }
  return {
    started: summarizeResult(started),
    resumed: summarizeResult(resumed),
  };
}

async function runRejectedPath(): Promise<JsonRecord> {
  const run = await workflow.createRun();
  const started = (await run.start({ inputData: buildInput() as never })) as JsonRecord;
  if (started.status !== "suspended") {
    throw new Error(`Expected rejected-path workflow to suspend, got ${String(started.status)}`);
  }
  const resumed = (await run.resume({
    step: humanMasteryGateStep,
    resumeData: {
      approved: false,
      reviewer: "local-operator",
      reason: "Runtime evidence is not ready for promotion.",
    },
  })) as JsonRecord;
  return {
    started: summarizeResult(started),
    resumed: summarizeResult(resumed),
  };
}

async function runNotRequiredPath(): Promise<JsonRecord> {
  const run = await workflow.createRun();
  const result = (await run.start({
    inputData: buildInput({
      loopRunId: "loop-repo-started-mastra-runtime-low-risk",
      decisionCardId: "dec-repo-started-mastra-runtime-low-risk",
      risk: {
        level: "low",
        requiresHumanGate: false,
        reasons: ["metadata-only dry run"],
      },
    }) as never,
  })) as JsonRecord;
  if (result.status !== "success") {
    throw new Error(`Expected low-risk workflow to succeed, got ${String(result.status)}`);
  }
  return summarizeResult(result);
}

async function main(): Promise<void> {
  const jsonMode = process.argv.includes("--json");
  const approvedPath = await runApprovedPath();
  const rejectedPath = await runRejectedPath();
  const notRequiredPath = await runNotRequiredPath();
  const payload = {
    schema_version: "cognitive-loop-mastra-runtime-service-v1",
    status: "pass",
    package: "@study-anything/cognitive-loop-mastra-runtime",
    workflow_registration_key: "cognitiveLoopRuntimeAdapterWorkflow",
    workflow_id: "cognitive-loop-runtime-adapter",
    paths: {
      approved: approvedPath,
      rejected: rejectedPath,
      not_required: notRequiredPath,
    },
    boundaries: {
      repository_started_mastra_instance: true,
      metadata_only: true,
      raw_source_text_included: false,
      diff_bodies_included: false,
      agent_secrets_included: false,
      model_keys_included: false,
      external_agent_called: false,
    },
  };
  const output = JSON.stringify(payload, null, 2);
  if (jsonMode) {
    console.log(output);
    return;
  }
  console.log(output);
}

main().catch((error: unknown) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
});
