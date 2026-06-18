import { createStep, createWorkflow } from "@mastra/core/workflows";
import { z } from "zod";

const ArtifactRefSchema = z.object({
  artifactId: z.string().min(1),
  kind: z.enum([
    "project_snapshot",
    "loop_run",
    "decision_card",
    "human_gate",
    "evidence_bundle",
    "event_index",
    "event_store",
    "review_agent_report",
  ]),
  path: z.string().min(1),
  sha256: z.string().regex(/^[a-f0-9]{64}$/),
  schemaVersion: z.string().min(1),
  status: z.string().min(1),
});

const RiskSchema = z.object({
  level: z.enum(["low", "medium", "high", "critical"]),
  requiresHumanGate: z.boolean(),
  reasons: z.array(z.string().min(1)).max(12),
});

export const CognitiveLoopRunInputSchema = z.object({
  projectId: z.string().min(1),
  loopRunId: z.string().min(1),
  decisionCardId: z.string().min(1),
  actor: z.string().min(1),
  eventStorePath: z.string().min(1),
  artifactRefs: z.array(ArtifactRefSchema).min(1),
  risk: RiskSchema,
  constraints: z.object({
    metadataOnly: z.literal(true),
    noRawSourceText: z.literal(true),
    noDiffBodies: z.literal(true),
    noAgentSecrets: z.literal(true),
    noModelKeys: z.literal(true),
  }),
});

const EvidenceValidatedSchema = z.object({
  projectId: z.string().min(1),
  loopRunId: z.string().min(1),
  decisionCardId: z.string().min(1),
  eventStorePath: z.string().min(1),
  artifactCount: z.number().int().nonnegative(),
  risk: RiskSchema,
  evidenceStatus: z.enum(["ready", "blocked"]),
  missingEvidence: z.array(z.string()).max(20),
});

const HumanGateSuspendSchema = z.object({
  reason: z.string().min(1),
  loopRunId: z.string().min(1),
  decisionCardId: z.string().min(1),
  requiredEvidence: z.array(z.string().min(1)).max(20),
  privacy: z.object({
    metadataOnly: z.literal(true),
    rawSourceTextIncluded: z.literal(false),
    diffBodiesIncluded: z.literal(false),
    agentSecretsIncluded: z.literal(false),
    modelKeysIncluded: z.literal(false),
  }),
});

const HumanGateResumeSchema = z.object({
  approved: z.boolean(),
  reviewer: z.string().min(1),
  reason: z.string().min(1).max(280),
});

const CognitiveLoopRunOutputSchema = z.object({
  status: z.enum(["approved", "rejected", "not_required"]),
  projectId: z.string().min(1),
  loopRunId: z.string().min(1),
  decisionCardId: z.string().min(1),
  humanGate: z.object({
    required: z.boolean(),
    reviewer: z.string().optional(),
    reason: z.string().optional(),
  }),
  eventStoreProjection: z.object({
    path: z.string().min(1),
    metadataOnly: z.literal(true),
  }),
});

export type CognitiveLoopRunInput = z.infer<typeof CognitiveLoopRunInputSchema>;
export type CognitiveLoopRunOutput = z.infer<typeof CognitiveLoopRunOutputSchema>;
type ArtifactKind = z.infer<typeof ArtifactRefSchema>["kind"];

export const validateCognitiveLoopEvidenceStep = createStep({
  id: "validate-cognitive-loop-evidence",
  inputSchema: CognitiveLoopRunInputSchema,
  outputSchema: EvidenceValidatedSchema,
  execute: async ({ inputData }) => {
    const requiredKinds = new Set<ArtifactKind>(["project_snapshot", "decision_card", "event_store"]);
    const presentKinds = new Set(inputData.artifactRefs.map((artifact) => artifact.kind));
    const missingEvidence = [...requiredKinds].filter((kind) => !presentKinds.has(kind));

    return {
      projectId: inputData.projectId,
      loopRunId: inputData.loopRunId,
      decisionCardId: inputData.decisionCardId,
      eventStorePath: inputData.eventStorePath,
      artifactCount: inputData.artifactRefs.length,
      risk: inputData.risk,
      evidenceStatus: missingEvidence.length === 0 ? "ready" : "blocked" as "ready" | "blocked",
      missingEvidence,
    };
  },
});

export const humanMasteryGateStep = createStep({
  id: "human-mastery-gate",
  inputSchema: EvidenceValidatedSchema,
  outputSchema: CognitiveLoopRunOutputSchema,
  resumeSchema: HumanGateResumeSchema,
  suspendSchema: HumanGateSuspendSchema,
  execute: async ({ inputData, resumeData, suspend, bail }) => {
    if (inputData.evidenceStatus === "blocked") {
      return bail({
        status: "rejected" as const,
        projectId: inputData.projectId,
        loopRunId: inputData.loopRunId,
        decisionCardId: inputData.decisionCardId,
        humanGate: {
          required: true,
          reason: `Missing required evidence: ${inputData.missingEvidence.join(", ")}`,
        },
        eventStoreProjection: {
          path: inputData.eventStorePath,
          metadataOnly: true as const,
        },
      });
    }

    if (!inputData.risk.requiresHumanGate) {
      return {
        status: "not_required" as const,
        projectId: inputData.projectId,
        loopRunId: inputData.loopRunId,
        decisionCardId: inputData.decisionCardId,
        humanGate: {
          required: false,
        },
        eventStoreProjection: {
          path: inputData.eventStorePath,
          metadataOnly: true as const,
        },
      };
    }

    if (!resumeData) {
      return await suspend({
        reason: "Human Mastery Gate approval required before this Cognitive Loop run can continue.",
        loopRunId: inputData.loopRunId,
        decisionCardId: inputData.decisionCardId,
        requiredEvidence: ["project_snapshot", "decision_card", "event_store"],
        privacy: {
          metadataOnly: true,
          rawSourceTextIncluded: false,
          diffBodiesIncluded: false,
          agentSecretsIncluded: false,
          modelKeysIncluded: false,
        },
      });
    }

    if (resumeData.approved === false) {
      return bail({
        status: "rejected" as const,
        projectId: inputData.projectId,
        loopRunId: inputData.loopRunId,
        decisionCardId: inputData.decisionCardId,
        humanGate: {
          required: true,
          reviewer: resumeData.reviewer,
          reason: resumeData.reason,
        },
        eventStoreProjection: {
          path: inputData.eventStorePath,
          metadataOnly: true as const,
        },
      });
    }

    return {
      status: "approved" as const,
      projectId: inputData.projectId,
      loopRunId: inputData.loopRunId,
      decisionCardId: inputData.decisionCardId,
      humanGate: {
        required: true,
        reviewer: resumeData.reviewer,
        reason: resumeData.reason,
      },
      eventStoreProjection: {
        path: inputData.eventStorePath,
        metadataOnly: true as const,
      },
    };
  },
});

export const cognitiveLoopRuntimeAdapterWorkflow = createWorkflow({
  id: "cognitive-loop-runtime-adapter",
  inputSchema: CognitiveLoopRunInputSchema,
  outputSchema: CognitiveLoopRunOutputSchema,
})
  .then(validateCognitiveLoopEvidenceStep)
  .then(humanMasteryGateStep)
  .commit();
