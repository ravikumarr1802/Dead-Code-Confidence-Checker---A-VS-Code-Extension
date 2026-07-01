import * as fs from "fs";
import * as path from "path";
import { execFile } from "child_process";

const PROJECT_ROOT = path.resolve(__dirname, "../..");
const VENV_PYTHON = path.join(PROJECT_ROOT, "venv", "Scripts", "python.exe");
const PYTHON_PATH = fs.existsSync(VENV_PYTHON) ? VENV_PYTHON : "python";
const DB_PY_PATH = path.resolve(__dirname, "../../database/db.py");

function runDbCommand(args: string[]): Promise<string> {
  return new Promise((resolve, reject) => {
    execFile(
      PYTHON_PATH,
      [DB_PY_PATH, ...args],
      {
        encoding: "utf8",
        maxBuffer: 5 * 1024 * 1024,
        env: {
          ...process.env,
          DCC_DB_PATH: path.join(PROJECT_ROOT, "dcc", "dcc_analysis.db"),
        },
      },
      (error, stdout, stderr) => {
        if (error) {
          reject(stderr || error.message);
          return;
        }
        resolve(stdout.trim());
      },
    );
  });
}

export async function initializeDatabase(): Promise<void> {
  await runDbCommand(["init"]);
}

export async function insertAnalysisSession(
  projectPath: string,
  totalFiles: number,
): Promise<number> {
  const result = await runDbCommand([
    "insert_analysis_session",
    projectPath,
    totalFiles.toString(),
  ]);
  return Number(result);
}

export async function insertCodeEntity(
  sessionId: number,
  fileName: string,
  entityName: string,
  entityType: string,
  startLine: number,
  endLine: number,
  confidenceScore: number,
): Promise<number> {
  const result = await runDbCommand([
    "insert_code_entity",
    sessionId.toString(),
    fileName,
    entityName,
    entityType,
    startLine.toString(),
    endLine.toString(),
    confidenceScore.toString(),
  ]);
  return Number(result);
}

export async function insertFeatureVector(
  entityId: number,
  callCount: number,
  isExported: number,
  usedInTests: number,
  dynamicCallRisk: number,
  cyclomaticComplexity: number,
  fileDepth: number,
): Promise<number> {
  const result = await runDbCommand([
    "insert_feature_vector",
    entityId.toString(),
    callCount.toString(),
    isExported.toString(),
    usedInTests.toString(),
    dynamicCallRisk.toString(),
    cyclomaticComplexity.toString(),
    fileDepth.toString(),
  ]);
  return Number(result);
}

export async function insertExplanation(
  entityId: number,
  explanationText: string,
): Promise<number> {
  const result = await runDbCommand([
    "insert_explanation",
    entityId.toString(),
    explanationText,
  ]);
  return Number(result);
}

export async function insertXaiExplanation(
  entityId: number,
  xai: Record<string, unknown>,
): Promise<number> {
  const result = await runDbCommand([
    "insert_xai_explanation",
    entityId.toString(),
    JSON.stringify(xai),
  ]);
  return Number(result);
}

export async function logChatQuery(
  query: string,
  response: string,
  contextFile?: string,
): Promise<number> {
  const args = ["log_chat", query, response];
  if (contextFile) {
    args.push(contextFile);
  }
  const result = await runDbCommand(args);
  return Number(result);
}

export async function insertRemovalLog(
  entityId: number,
  fileName: string,
  removedCode: string,
  confidenceScore: number,
): Promise<number> {
  const result = await runDbCommand([
    "insert_removal_log",
    entityId.toString(),
    fileName,
    removedCode,
    confidenceScore.toString(),
  ]);
  return Number(result);
}

export async function fetchPastAnalysis(projectPath: string): Promise<any[]> {
  const result = await runDbCommand(["fetch_past_analysis", projectPath]);
  return JSON.parse(result || "[]");
}

export async function fetchEntitiesForSession(sessionId: number): Promise<any[]> {
  const result = await runDbCommand([
    "fetch_entities_for_session",
    sessionId.toString(),
  ]);
  return JSON.parse(result || "[]");
}

export async function fetchRemovalLogs(): Promise<any[]> {
  const result = await runDbCommand(["fetch_removal_logs"]);
  return JSON.parse(result || "[]");
}

export async function fetchChatHistory(limit: number = 50): Promise<any[]> {
  const result = await runDbCommand(["fetch_chat_history", limit.toString()]);
  return JSON.parse(result || "[]");
}

export async function fetchAnalysisSummary(projectPath: string): Promise<any> {
  const result = await runDbCommand(["fetch_analysis_summary", projectPath]);
  return JSON.parse(result || "{}");
}
