import { Mastra } from "@mastra/core";

import { cognitiveLoopRuntimeAdapterWorkflow } from "./workflows/cognitive-loop-mastra-adapter.js";

export const mastra = new Mastra({
  workflows: {
    cognitiveLoopRuntimeAdapterWorkflow,
  },
});
