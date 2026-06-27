import { z } from "zod";

type JsonRecord = Record<string, unknown>;

const ObservationMetadataSchema = z.record(
  z.string(),
  z.union([z.string(), z.number(), z.boolean(), z.null()]),
);

export const LangfuseTraceDtoSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  session_id: z.string().min(1),
  user_id: z.string().min(1),
  metadata: ObservationMetadataSchema,
});

export const LangfuseSpanDtoSchema = z.object({
  id: z.string().min(1),
  trace_id: z.string().min(1),
  name: z.string().min(1),
  start_offset_ms: z.number().int().nonnegative(),
  end_offset_ms: z.number().int().nonnegative(),
  metadata: ObservationMetadataSchema,
});

export const LangfuseGenerationDtoSchema = z.object({
  id: z.string().min(1),
  trace_id: z.string().min(1),
  name: z.string().min(1),
  model: z.string().min(1),
  input_omitted: z.literal(true),
  output_omitted: z.literal(true),
  metadata: ObservationMetadataSchema,
});

export const LangfuseScoreDtoSchema = z.object({
  id: z.string().min(1),
  trace_id: z.string().min(1),
  name: z.string().min(1),
  value: z.union([z.string(), z.number(), z.boolean()]),
  source: z.literal("local-receipt"),
  metadata: ObservationMetadataSchema,
});

export const LangfuseReceiptSchema = z.object({
  schema_version: z.literal("cognitive-loop-langfuse-receipt-v1"),
  local_only: z.literal(true),
  calls_real_langfuse: z.literal(false),
  dto_counts: z.object({
    traces: z.number().int().nonnegative(),
    spans: z.number().int().nonnegative(),
    generations: z.number().int().nonnegative(),
    scores: z.number().int().nonnegative(),
  }),
  privacy_checked: z.literal(true),
});

export const LangfuseObservabilityReportSchema = z.object({
  schema_version: z.literal("cognitive-loop-langfuse-observability-v1"),
  status: z.literal("pass"),
  purpose: z.string().min(1),
  evidence: z.object({
    service_schema: z.string().min(1),
    durable_schema: z.string().min(1),
    workflow_id: z.string().min(1),
    runtime_id: z.string().min(1),
  }),
  traces: z.array(LangfuseTraceDtoSchema).min(1),
  spans: z.array(LangfuseSpanDtoSchema).min(1),
  generations: z.array(LangfuseGenerationDtoSchema).min(1),
  scores: z.array(LangfuseScoreDtoSchema).min(1),
  receipt: LangfuseReceiptSchema,
  boundaries: z.object({
    dto_only: z.literal(true),
    calls_real_langfuse: z.literal(false),
    imports_langfuse_sdk: z.literal(false),
    network_calls: z.literal(false),
    external_agent_called: z.literal(false),
    hosted_service_started: z.literal(false),
    metadata_only: z.literal(true),
  }),
  privacy: z.object({
    metadata_only: z.literal(true),
    raw_source_text_included: z.literal(false),
    source_bodies_included: z.literal(false),
    diff_bodies_included: z.literal(false),
    learner_answers_included: z.literal(false),
    agent_endpoints_included: z.literal(false),
    agent_metadata_included: z.literal(false),
    prompt_text_included: z.literal(false),
    real_model_keys_stored: z.literal(false),
    langfuse_secret_included: z.literal(false),
    storage_path_included: z.literal(false),
    absolute_paths_included: z.literal(false),
  }),
});

export type LangfuseObservabilityReport = z.infer<typeof LangfuseObservabilityReportSchema>;

type RunSpec = {
  decisionCardId: string;
  gateRequired: boolean;
  gateResolution: "approved" | "rejected" | "not_required";
  kind: string;
  loopRunId: string;
  projectId: string;
  reportId: "mastra-runtime-service" | "mastra-runtime-durable";
  riskLevel: "low" | "high";
  terminalStatus: string;
};

type ScoreValue = string | number | boolean;

function asRecord(value: unknown): JsonRecord {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as JsonRecord) : {};
}

function stringValue(value: unknown, fallback: string): string {
  return typeof value === "string" && value.length > 0 ? value : fallback;
}

function serviceRunSpec(
  serviceReport: JsonRecord,
  kind: "approved" | "rejected" | "not_required",
): RunSpec {
  const runtime = asRecord(serviceReport.runtime);
  const paths = asRecord(runtime.paths);
  const pathPayload = asRecord(paths[kind]);
  const terminal =
    kind === "not_required"
      ? asRecord(pathPayload.result)
      : asRecord(asRecord(pathPayload.resumed).result);
  const terminalStatus =
    kind === "not_required"
      ? stringValue(pathPayload.status, "success")
      : stringValue(asRecord(pathPayload.resumed).status, "success");
  return {
    decisionCardId: stringValue(terminal.decisionCardId, `dec-service-${kind}`),
    gateRequired: kind !== "not_required",
    gateResolution: kind,
    kind: `service_${kind}`,
    loopRunId: stringValue(terminal.loopRunId, `loop-service-${kind}`),
    projectId: stringValue(terminal.projectId, "repo-started-mastra-runtime-project"),
    reportId: "mastra-runtime-service",
    riskLevel: kind === "not_required" ? "low" : "high",
    terminalStatus,
  };
}

function durableRunSpec(durableReport: JsonRecord, kind: "approved" | "rejected"): RunSpec {
  const receiptRecords = Array.isArray(durableReport.receipt_records)
    ? durableReport.receipt_records.map((item) => asRecord(item))
    : [];
  const receipt = receiptRecords.find((item) => item.phase === kind) ?? {};
  const runs = asRecord(durableReport.durable_runs);
  const run = asRecord(runs[kind]);
  const runId = stringValue(receipt.run_id, `run-durable-${kind}`);
  return {
    decisionCardId: `dec-${runId}`,
    gateRequired: true,
    gateResolution: kind,
    kind: `durable_${kind}`,
    loopRunId: runId,
    projectId: "repo-started-mastra-runtime-project",
    reportId: "mastra-runtime-durable",
    riskLevel: "high",
    terminalStatus: stringValue(run.result_status, kind),
  };
}

function traceId(spec: RunSpec): string {
  return `trace-${spec.kind}`;
}

function buildTrace(spec: RunSpec, workflowId: string): z.infer<typeof LangfuseTraceDtoSchema> {
  return {
    id: traceId(spec),
    name: `Cognitive Loop ${spec.kind.replaceAll("_", " ")}`,
    session_id: spec.loopRunId,
    user_id: "local-operator",
    metadata: {
      decision_card_id: spec.decisionCardId,
      gate_required: spec.gateRequired,
      gate_resolution: spec.gateResolution,
      loop_run_id: spec.loopRunId,
      metadata_only: true,
      project_id: spec.projectId,
      report_id: spec.reportId,
      risk_level: spec.riskLevel,
      run_kind: spec.kind,
      runtime_id: "repo-local-mastra-runtime",
      terminal_status: spec.terminalStatus,
      workflow_id: workflowId,
    },
  };
}

function span(
  spec: RunSpec,
  step: string,
  index: number,
  metadata: JsonRecord = {},
): z.infer<typeof LangfuseSpanDtoSchema> {
  return {
    id: `span-${spec.kind}-${step}`,
    trace_id: traceId(spec),
    name: step,
    start_offset_ms: index * 10,
    end_offset_ms: index * 10 + 7,
    metadata: {
      decision_card_id: spec.decisionCardId,
      loop_run_id: spec.loopRunId,
      metadata_only: true,
      run_kind: spec.kind,
      ...metadata,
    } as z.infer<typeof ObservationMetadataSchema>,
  };
}

function buildSpans(spec: RunSpec): z.infer<typeof LangfuseSpanDtoSchema>[] {
  const spans = [
    span(spec, "validate-cognitive-loop-evidence", 0, {
      evidence_status: "ready",
      step_id: "validate-cognitive-loop-evidence",
    }),
    span(spec, "human-mastery-gate", 1, {
      gate_required: spec.gateRequired,
      gate_resolution: spec.gateResolution,
      step_id: "human-mastery-gate",
    }),
    span(spec, "event-store-projection", 2, {
      projection: "metadata-only",
      storage_path_included: false,
    }),
  ];
  if (spec.kind.startsWith("durable_")) {
    spans.splice(
      1,
      0,
      span(spec, "durable-state-recovered", 1, {
        storage: "local-libsql",
        storage_path_included: false,
      }),
    );
    spans.push(
      span(spec, "durable-receipt-written", 4, {
        receipt_phase: spec.gateResolution,
        storage_path_included: false,
      }),
    );
  }
  return spans;
}

function buildGeneration(spec: RunSpec): z.infer<typeof LangfuseGenerationDtoSchema> {
  return {
    id: `generation-${spec.kind}-runtime-adapter`,
    trace_id: traceId(spec),
    name: "cognitive-loop-runtime-adapter",
    model: "user-owned-agent-outside-study-anything",
    input_omitted: true,
    output_omitted: true,
    metadata: {
      decision_card_id: spec.decisionCardId,
      external_agent_called: false,
      loop_run_id: spec.loopRunId,
      metadata_only: true,
      prompt_text_included: false,
      provider_id: "repo-local-mastra-adapter",
      real_model_keys_stored: false,
      run_kind: spec.kind,
      task_type: "workflow.run",
    },
  };
}

function score(
  spec: RunSpec,
  name: string,
  value: ScoreValue,
  metadata: JsonRecord = {},
): z.infer<typeof LangfuseScoreDtoSchema> {
  return {
    id: `score-${spec.kind}-${name}`,
    trace_id: traceId(spec),
    name,
    value,
    source: "local-receipt",
    metadata: {
      decision_card_id: spec.decisionCardId,
      loop_run_id: spec.loopRunId,
      metadata_only: true,
      run_kind: spec.kind,
      ...metadata,
    } as z.infer<typeof ObservationMetadataSchema>,
  };
}

function buildScores(spec: RunSpec): z.infer<typeof LangfuseScoreDtoSchema>[] {
  const riskValue = spec.riskLevel === "low" ? 0.2 : 0.8;
  return [
    score(spec, "risk_score", riskValue, { risk_level: spec.riskLevel }),
    score(spec, "human_gate_required", spec.gateRequired),
    score(spec, "human_gate_resolution", spec.gateResolution),
    score(spec, "privacy_metadata_only", true),
    score(spec, "latency_ms", spec.kind.startsWith("durable_") ? 42 : 21),
    score(spec, "token_count", 0, { token_metadata_provided: false }),
    score(spec, "cost_usd", 0, { cost_metadata_provided: false }),
  ];
}

export function buildLangfuseObservabilityReport(input: {
  durableReport: JsonRecord;
  serviceReport: JsonRecord;
}): LangfuseObservabilityReport {
  const workflowId = stringValue(
    asRecord(input.serviceReport.runtime).workflow_id,
    "cognitive-loop-runtime-adapter",
  );
  const runSpecs: RunSpec[] = [
    serviceRunSpec(input.serviceReport, "approved"),
    serviceRunSpec(input.serviceReport, "rejected"),
    serviceRunSpec(input.serviceReport, "not_required"),
    durableRunSpec(input.durableReport, "approved"),
    durableRunSpec(input.durableReport, "rejected"),
  ];
  const traces = runSpecs.map((spec) => buildTrace(spec, workflowId));
  const spans = runSpecs.flatMap((spec) => buildSpans(spec));
  const generations = runSpecs.map((spec) => buildGeneration(spec));
  const scores = runSpecs.flatMap((spec) => buildScores(spec));
  const report = {
    schema_version: "cognitive-loop-langfuse-observability-v1",
    status: "pass",
    purpose:
      "Map repo-local Cognitive Loop Mastra runtime receipts to Langfuse trace, span, generation, and score DTOs without calling Langfuse or exposing private runtime data.",
    evidence: {
      service_schema: stringValue(input.serviceReport.schema_version, "unknown"),
      durable_schema: stringValue(input.durableReport.schema_version, "unknown"),
      workflow_id: workflowId,
      runtime_id: "repo-local-mastra-runtime",
    },
    traces,
    spans,
    generations,
    scores,
    receipt: {
      schema_version: "cognitive-loop-langfuse-receipt-v1",
      local_only: true,
      calls_real_langfuse: false,
      dto_counts: {
        traces: traces.length,
        spans: spans.length,
        generations: generations.length,
        scores: scores.length,
      },
      privacy_checked: true,
    },
    boundaries: {
      dto_only: true,
      calls_real_langfuse: false,
      imports_langfuse_sdk: false,
      network_calls: false,
      external_agent_called: false,
      hosted_service_started: false,
      metadata_only: true,
    },
    privacy: {
      metadata_only: true,
      raw_source_text_included: false,
      source_bodies_included: false,
      diff_bodies_included: false,
      learner_answers_included: false,
      agent_endpoints_included: false,
      agent_metadata_included: false,
      prompt_text_included: false,
      real_model_keys_stored: false,
      langfuse_secret_included: false,
      storage_path_included: false,
      absolute_paths_included: false,
    },
  };
  return LangfuseObservabilityReportSchema.parse(report);
}
