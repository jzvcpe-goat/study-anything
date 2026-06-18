import { createWorkflowStateReader } from "@mastra/core/workflows";
import { writeFile } from "node:fs/promises";
import { createMastraRuntime } from "./runtime.js";

type JsonRecord = Record<string, unknown>;

type ParsedArgs = {
  decision: "approved" | "rejected";
  json: boolean;
  mode: "start" | "resume";
  receiptFile?: string;
  runId: string;
  storageFile: string;
  watcherEventId: string;
  watcherRef: string;
  watcherSha: string;
};

const WORKFLOW_ID = "cognitiveLoopRuntimeAdapterWorkflow";
const HUMAN_GATE_STEP = "human-mastery-gate";

function parseArgs(): ParsedArgs {
  const args = process.argv.slice(2);
  const value = (flag: string): string | undefined => {
    const index = args.indexOf(flag);
    return index >= 0 ? args[index + 1] : undefined;
  };
  const mode = value("--mode") ?? "start";
  const decision = value("--decision") ?? "approved";
  const parsed: ParsedArgs = {
    decision: decision === "rejected" ? "rejected" : "approved",
    json: args.includes("--json"),
    mode: mode === "resume" ? "resume" : "start",
    receiptFile: value("--receipt-file"),
    runId: value("--run-id") ?? "run-cognitive-loop-durable",
    storageFile: value("--storage-file") ?? ".cognitive-loop/mastra-runtime-durable.sqlite",
    watcherEventId: value("--watcher-event-id") ?? "evt-watcher-durable",
    watcherRef: value("--watcher-ref") ?? ".cognitive-loop/events/watcher-ingest.json",
    watcherSha: value("--watcher-sha") ?? "b".repeat(64),
  };
  if (!/^[a-f0-9]{64}$/.test(parsed.watcherSha)) {
    throw new Error("--watcher-sha must be a lowercase sha256 hex digest.");
  }
  return parsed;
}

function artifact(kind: string, path: string, sha256 = "a".repeat(64)): JsonRecord {
  return {
    artifactId: `artifact-${kind}`,
    kind,
    path,
    sha256,
    schemaVersion: `cognitive-loop-${kind}-v1`,
    status: "pass",
  };
}

function buildInput(args: ParsedArgs): JsonRecord {
  return {
    projectId: "repo-started-mastra-runtime-project",
    loopRunId: args.runId,
    decisionCardId: `dec-${args.runId}`,
    actor: "study-anything-local-runtime",
    eventStorePath: ".cognitive-loop/mastra-runtime-durable.sqlite",
    artifactRefs: [
      artifact("project_snapshot", ".cognitive-loop/events/project-snapshot.json"),
      artifact("decision_card", ".cognitive-loop/events/decision-card.json"),
      artifact("event_store", ".cognitive-loop/events/event-store.json"),
      artifact("watcher_ingest", args.watcherRef, args.watcherSha),
    ],
    risk: {
      level: "high",
      requiresHumanGate: true,
      reasons: ["watcher metadata event requires explicit operator approval before resume"],
    },
    constraints: {
      metadataOnly: true,
      noRawSourceText: true,
      noDiffBodies: true,
      noAgentSecrets: true,
      noModelKeys: true,
    },
  };
}

function summarizeResult(result: JsonRecord): JsonRecord {
  return {
    status: result.status,
    suspended: Array.isArray(result.suspended) ? result.suspended : [],
    result: result.result ?? null,
  };
}

function summarizeState(state: JsonRecord | null): JsonRecord {
  if (!state) {
    return { found: false };
  }
  const reader = createWorkflowStateReader(state as never);
  const suspendedStep = reader.getSuspendedStep();
  return {
    found: true,
    status: reader.getStatus(),
    suspendedStepPath: suspendedStep?.path ?? null,
    suspendedStepId: suspendedStep?.stepId ?? null,
    resumeLabels: reader.getResumeLabels(),
  };
}

async function writeReceipt(path: string | undefined, payload: JsonRecord): Promise<void> {
  if (!path) {
    return;
  }
  await writeFile(path, JSON.stringify(payload, null, 2) + "\n", "utf8");
}

function privacyBlock(): JsonRecord {
  return {
    metadata_only: true,
    raw_source_text_included: false,
    diff_bodies_included: false,
    file_contents_included: false,
    learner_answers_included: false,
    agent_endpoints_included: false,
    prompt_text_included: false,
    real_model_keys_stored: false,
  };
}

async function runStart(args: ParsedArgs): Promise<JsonRecord> {
  const runtime = createMastraRuntime({ storageFile: args.storageFile });
  const workflow = runtime.getWorkflow(WORKFLOW_ID);
  const run = await workflow.createRun({ runId: args.runId });
  const started = (await run.start({ inputData: buildInput(args) as never })) as JsonRecord;
  const state = (await workflow.getWorkflowRunById(args.runId)) as JsonRecord | null;
  const stateSummary = summarizeState(state);
  const receipt = {
    schema_version: "cognitive-loop-mastra-runtime-durable-receipt-v1",
    phase: "suspended",
    run_id: args.runId,
    workflow_id: "cognitive-loop-runtime-adapter",
    status: started.status,
    watcher_event_id: args.watcherEventId,
    watcher_ref: args.watcherRef,
    recovered_state: stateSummary,
    storage: {
      kind: "libsql_file",
      path_included: false,
    },
    privacy: privacyBlock(),
  };
  await writeReceipt(args.receiptFile, receipt);
  return {
    schema_version: "cognitive-loop-mastra-runtime-durable-start-v1",
    status: "pass",
    run_id: args.runId,
    workflow_registration_key: WORKFLOW_ID,
    started: summarizeResult(started),
    recovered_state: stateSummary,
    receipt_written: Boolean(args.receiptFile),
    storage: {
      kind: "libsql_file",
      path_included: false,
    },
    watcher_event: {
      event_id: args.watcherEventId,
      ref: args.watcherRef,
      sha256: args.watcherSha,
    },
    privacy: privacyBlock(),
  };
}

async function runResume(args: ParsedArgs): Promise<JsonRecord> {
  const runtime = createMastraRuntime({ storageFile: args.storageFile });
  const workflow = runtime.getWorkflow(WORKFLOW_ID);
  const state = (await workflow.getWorkflowRunById(args.runId)) as JsonRecord | null;
  const stateSummary = summarizeState(state);
  if (!state || stateSummary.status !== "suspended") {
    throw new Error(`Expected persisted suspended state for run ${args.runId}.`);
  }
  const run = await workflow.createRun({ runId: args.runId });
  const resumed = (await run.resume({
    step: (stateSummary.suspendedStepPath as string[] | undefined) ?? HUMAN_GATE_STEP,
    resumeData: {
      approved: args.decision === "approved",
      reviewer: "local-operator",
      reason:
        args.decision === "approved"
          ? "Durable metadata-only watcher evidence was reviewed."
          : "Durable metadata-only watcher evidence was rejected.",
    },
  })) as JsonRecord;
  const resumedState = (await workflow.getWorkflowRunById(args.runId)) as JsonRecord | null;
  const receipt = {
    schema_version: "cognitive-loop-mastra-runtime-durable-receipt-v1",
    phase: args.decision,
    run_id: args.runId,
    workflow_id: "cognitive-loop-runtime-adapter",
    status: resumed.status,
    result_status: ((resumed.result as JsonRecord | undefined) ?? {}).status ?? null,
    recovered_before_resume: stateSummary,
    recovered_after_resume: summarizeState(resumedState),
    storage: {
      kind: "libsql_file",
      path_included: false,
    },
    privacy: privacyBlock(),
  };
  await writeReceipt(args.receiptFile, receipt);
  return {
    schema_version: "cognitive-loop-mastra-runtime-durable-resume-v1",
    status: "pass",
    run_id: args.runId,
    workflow_registration_key: WORKFLOW_ID,
    decision: args.decision,
    recovered_before_resume: stateSummary,
    resumed: summarizeResult(resumed),
    recovered_after_resume: summarizeState(resumedState),
    receipt_written: Boolean(args.receiptFile),
    storage: {
      kind: "libsql_file",
      path_included: false,
    },
    privacy: privacyBlock(),
  };
}

async function main(): Promise<void> {
  const args = parseArgs();
  const payload = args.mode === "resume" ? await runResume(args) : await runStart(args);
  const output = JSON.stringify(payload, null, 2);
  if (args.json) {
    console.log(output);
    return;
  }
  console.log(output);
}

main().catch((error: unknown) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
});
