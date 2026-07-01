import * as fs from "fs";
import * as os from "os";
import * as path from "path";
import { execFile } from "child_process";
import {
  AnalysisResult,
  FeatureContribution,
  Severity,
  SymbolResult,
} from "./types";

const PROJECT_ROOT = path.resolve(__dirname, "../..");
const VENV_PYTHON = path.join(PROJECT_ROOT, "venv", "Scripts", "python.exe");
const PYTHON_PATH = fs.existsSync(VENV_PYTHON) ? VENV_PYTHON : "python";

interface AnalyzerRawResult {
  function_name: string;
  entity_type: string;
  confidence: number;
  severity: string;
  reasons_dead: string[];
  reasons_alive: string[];
  summary: string;
  explanation: string;
  top_features: {
    name: string;
    label: string;
    value: number;
    contribution: number;
    direction: string;
  }[];
  features: {
    call_count: number;
    is_exported: number;
    used_in_tests: number;
    dynamic_call_risk: number;
    cyclomatic_complexity: number;
    file_depth: number;
  };
  start_line: number;
  end_line: number;
  snippet: string;
  deepseek_analysis?: {
    is_unused: boolean | null;
    reasoning: string;
    key_observations: string[];
  };
  xai_explanation?: {
    summary: string;
    risk_level: "Low" | "Medium" | "High";
    confidence: number;
    confidence_explanation: string;
    factors: Array<{
      feature: string;
      impact: "high" | "medium" | "low";
      description: string;
    }>;
    llm_reasoning: string;
    recommendation: string;
    action: "keep" | "review" | "remove";
  };
}

function runAnalyzer(args: string[]): Promise<AnalyzerRawResult[]> {
  return new Promise((resolve, reject) => {
    execFile(
      PYTHON_PATH,
      args,
      {
        encoding: "utf8",
        maxBuffer: 10 * 1024 * 1024,
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

        try {
          const parsed = JSON.parse(stdout);
          if (Array.isArray(parsed)) {
            resolve(parsed);
          } else if (parsed.error) {
            reject(parsed.error);
          } else if (Array.isArray(parsed.results)) {
            resolve(parsed.results);
          } else {
            resolve([parsed]);
          }
        } catch {
          reject("Failed to parse analyzer output: " + stdout);
        }
      },
    );
  });
}

export async function runPythonAnalyzerOnFile(
  filePath: string,
  analyzerPath: string,
  projectRoot?: string,
): Promise<AnalyzerRawResult[]> {
  const args = [analyzerPath, filePath];
  if (projectRoot) {
    args.push("--project-root", projectRoot);
  }
  return runAnalyzer(args);
}

export async function runPythonAnalyzerOnCode(
  selectedCode: string,
  analyzerPath: string,
): Promise<AnalyzerRawResult[]> {
  const tmpDir = os.tmpdir();
  const tmpFile = path.join(tmpDir, `dcc_selected_${Date.now()}.py`);
  fs.writeFileSync(tmpFile, selectedCode, "utf8");

  try {
    return await runAnalyzer([analyzerPath, tmpFile]);
  } finally {
    try {
      fs.unlinkSync(tmpFile);
    } catch {
      // Ignore temp cleanup failures.
    }
  }
}

export function mapToAnalysisResult(
  rawResults: AnalyzerRawResult[],
  fileUri: string,
  filename: string,
  language: string,
  durationMs: number,
): AnalysisResult {
  const symbols: SymbolResult[] = rawResults.map((raw) => {
    const kind = (raw.entity_type === "class" ? "class" : "function") as SymbolResult["kind"];
    const severity = raw.severity as Severity;
    const topFeatures: FeatureContribution[] = (raw.top_features || []).map((feature) => ({
      name: feature.name,
      label: feature.label,
      value: feature.value,
      contribution: feature.contribution,
      direction: feature.direction as "dead" | "live",
    }));

    return {
      id: `${raw.function_name}_${raw.start_line}`,
      name: raw.function_name,
      kind,
      startLine: raw.start_line,
      endLine: raw.end_line,
      confidence: raw.confidence,
      severity,
      reasonsDead: raw.reasons_dead || [],
      reasonsAlive: raw.reasons_alive || [],
      topFeatures,
      summary: raw.summary || "",
      explanation: raw.explanation || "",
      snippet: raw.snippet ? raw.snippet.split("\n")[0] : "",
      features: raw.features,
      deepseek_analysis: raw.deepseek_analysis,
      xai_explanation: raw.xai_explanation,
    };
  });

  const dangerCount = symbols.filter((symbol) => symbol.severity === "danger").length;
  const warningCount = symbols.filter((symbol) => symbol.severity === "warning").length;
  const reviewCount = symbols.filter((symbol) => symbol.severity === "review").length;
  const safeCount = symbols.filter((symbol) => symbol.severity === "safe").length;

  return {
    fileUri,
    filename,
    language,
    analyzedAt: new Date().toISOString(),
    durationMs,
    symbols,
    totalSymbols: symbols.length,
    dangerCount,
    warningCount,
    reviewCount,
    safeCount,
  };
}
