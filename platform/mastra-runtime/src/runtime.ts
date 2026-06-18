import { Mastra } from "@mastra/core";
import { LibSQLStore } from "@mastra/libsql";

import { cognitiveLoopRuntimeAdapterWorkflow } from "./workflows/cognitive-loop-mastra-adapter.js";

type RuntimeOptions = {
  storageFile?: string;
};

export function createMastraRuntime(options: RuntimeOptions = {}): Mastra {
  const config: ConstructorParameters<typeof Mastra>[0] = {
    workflows: {
      cognitiveLoopRuntimeAdapterWorkflow,
    },
  };
  if (options.storageFile) {
    config.storage = new LibSQLStore({
      id: "cognitive-loop-runtime-storage",
      url: options.storageFile === ":memory:" ? ":memory:" : `file:${options.storageFile}`,
    });
  }
  return new Mastra(config);
}
