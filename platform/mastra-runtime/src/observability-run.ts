import { readFile, writeFile } from "node:fs/promises";
import { buildLangfuseObservabilityReport } from "./observability.js";

type JsonRecord = Record<string, unknown>;

type ParsedArgs = {
  durableReport: string;
  json: boolean;
  receiptFile?: string;
  serviceReport: string;
};

function parseArgs(): ParsedArgs {
  const args = process.argv.slice(2);
  const value = (flag: string): string | undefined => {
    const index = args.indexOf(flag);
    return index >= 0 ? args[index + 1] : undefined;
  };
  const serviceReport = value("--service-report");
  const durableReport = value("--durable-report");
  if (!serviceReport) {
    throw new Error("--service-report is required.");
  }
  if (!durableReport) {
    throw new Error("--durable-report is required.");
  }
  return {
    durableReport,
    json: args.includes("--json"),
    receiptFile: value("--receipt-file"),
    serviceReport,
  };
}

async function readJson(path: string): Promise<JsonRecord> {
  const text = await readFile(path, "utf8");
  return JSON.parse(text) as JsonRecord;
}

async function main(): Promise<void> {
  const args = parseArgs();
  const payload = buildLangfuseObservabilityReport({
    serviceReport: await readJson(args.serviceReport),
    durableReport: await readJson(args.durableReport),
  });
  const output = JSON.stringify(payload, null, 2);
  if (args.receiptFile) {
    await writeFile(args.receiptFile, `${output}\n`, "utf8");
  }
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
