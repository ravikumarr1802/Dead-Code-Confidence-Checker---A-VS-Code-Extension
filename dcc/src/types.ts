export type Severity = "danger" | "warning" | "review" | "safe";

export interface FeatureContribution {
  name: string;
  label: string;
  value: number;
  contribution: number;
  direction: "dead" | "live";
}

export interface SymbolResult {
  id: string;
  name: string;
  kind: "function" | "class" | "variable" | "method";
  startLine: number;
  endLine: number;
  confidence: number;
  severity: Severity;
  reasonsDead: string[];
  reasonsAlive: string[];
  topFeatures: FeatureContribution[];
  summary: string;
  explanation: string;
  snippet: string;
  features?: {
    call_count: number;
    is_exported: number;
    used_in_tests: number;
    dynamic_call_risk: number;
    cyclomatic_complexity: number;
    file_depth: number;
  };
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

export interface AnalysisResult {
  fileUri: string;
  filename: string;
  language: string;
  analyzedAt: string;
  durationMs: number;
  symbols: SymbolResult[];
  totalSymbols: number;
  dangerCount: number;
  warningCount: number;
  reviewCount: number;
  safeCount: number;
}

export interface ExtensionState {
  lastResult: AnalysisResult | null;
  isAnalyzing: boolean;
  serverOnline: boolean;
}

export interface AnalysisSession {
  id: number;
  project_path: string;
  timestamp: string;
  total_files: number;
}

export interface StoredEntity {
  id: number;
  session_id: number;
  file_name: string;
  entity_name: string;
  entity_type: string;
  start_line: number;
  end_line: number;
  confidence_score: number;
  explanation_summary: string | null;
  risk_level: string | null;
  confidence_explanation: string | null;
  llm_reasoning: string | null;
  recommendation: string | null;
  action: string | null;
  xai_json: string | null;
  call_count: number;
  is_exported: number;
  used_in_tests: number;
  dynamic_call_risk: number;
  cyclomatic_complexity: number;
  file_depth: number;
}

export interface ChatMessage {
  id: number;
  query: string;
  response: string;
  context_file: string | null;
  timestamp: string;
}

export interface RemovalLog {
  id: number;
  entity_id: number;
  file_name: string;
  removed_code: string;
  confidence_score: number;
  timestamp: string;
}
