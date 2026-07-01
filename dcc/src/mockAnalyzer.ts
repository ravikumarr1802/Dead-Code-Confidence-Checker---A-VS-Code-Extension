/**
 * Mock Analyzer — Phase 1
 *
 * Parses the document with simple regex to find real function/class names,
 * then attaches realistic (but random) confidence scores and explanations.
 *
 * SWAP POINT (Phase 2): Replace this entire module with a call to the ML server.
 * The return type `AnalysisResult` stays identical — no other files change.
 */

import * as vscode from 'vscode';
import * as path from 'path';
import { AnalysisResult, SymbolResult, Severity, FeatureContribution } from './types';

// ─── Regex patterns per language ────────────────────────────────────────────

const PATTERNS: Record<string, RegExp[]> = {
  python: [
    /^(?:async\s+)?def\s+(\w+)\s*\(/gm,
    /^class\s+(\w+)\s*[:(]/gm,
  ],
  javascript: [
    /^(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(/gm,
    /^(?:export\s+)?class\s+(\w+)/gm,
    /^(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s*)?\(/gm,
    /^(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s*)?\w+\s*=>/gm,
  ],
  typescript: [
    /^(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*[<(]/gm,
    /^(?:export\s+)?class\s+(\w+)/gm,
    /^(?:export\s+)?const\s+(\w+)\s*(?::\s*\w+\s*)?=\s*(?:async\s*)?\(/gm,
    /^(?:private|protected|public|static)?\s+(?:async\s+)?(\w+)\s*\(/gm,
  ],
};

// ─── Evidence templates ──────────────────────────────────────────────────────

const DEAD_REASONS = [
  'Never called within this file',
  'No cross-file imports detected',
  'Not exported — locally scoped only',
  'No test coverage found',
  'Not modified in over 180 days',
  'Zero sibling functions reference this',
  'Low cyclomatic complexity — possible stub or placeholder',
  'Naming suggests deprecated intent (_old, _unused, _legacy)',
];

const ALIVE_REASONS = [
  'Called directly within this file',
  'Exported — accessible to external consumers',
  'Referenced by test suite',
  'High cyclomatic complexity — load-bearing logic',
  'Recently modified (within 30 days)',
  'Multiple sibling functions depend on this',
  'Overrides a parent class method',
  'May be invoked dynamically — unsafe to remove automatically',
  'Framework decorator detected — likely registered callback',
];

const FEATURE_LABELS: Record<string, string> = {
  call_frequency: 'Call Frequency',
  cross_file_refs: 'Cross-file References',
  is_exported: 'Exported',
  is_tested: 'Test Coverage',
  dynamic_risk: 'Dynamic Invocation Risk',
  complexity: 'Cyclomatic Complexity',
  lines_of_code: 'Lines of Code',
  last_modified_days: 'Days Since Modified',
  sibling_calls: 'Sibling Call Count',
  has_decorator: 'Has Decorator',
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

function seededRandom(seed: number): () => number {
  let s = seed;
  return () => {
    s = (s * 1664525 + 1013904223) & 0xffffffff;
    return (s >>> 0) / 0xffffffff;
  };
}

function getSeverity(confidence: number): Severity {
  if (confidence >= 0.75) return 'danger';
  if (confidence >= 0.55) return 'warning';
  if (confidence >= 0.35) return 'review';
  return 'safe';
}

function pickN<T>(arr: T[], n: number, rand: () => number): T[] {
  const shuffled = [...arr].sort(() => rand() - 0.5);
  return shuffled.slice(0, n);
}

function buildFeatures(confidence: number, rand: () => number): FeatureContribution[] {
  const features = Object.entries(FEATURE_LABELS).map(([name, label]) => {
    // Higher confidence → more dead-leaning feature contributions
    const contribution = (rand() - (1 - confidence)) * 0.4;
    return {
      name,
      label,
      value: Math.round(rand() * 10),
      contribution: parseFloat(contribution.toFixed(4)),
      direction: contribution > 0 ? 'dead' as const : 'live' as const,
    };
  });
  return features.sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution)).slice(0, 6);
}

function buildSummary(name: string, kind: string, confidence: number, severity: Severity): string {
  const pct = Math.round(confidence * 100);
  const summaries: Record<Severity, string> = {
    danger:  `\`${name}\` is ${pct}% likely dead — no callers detected and not exported.`,
    warning: `\`${name}\` shows strong dead code signals (${pct}%) — verify before removing.`,
    review:  `\`${name}\` has ambiguous signals (${pct}%) — manual review recommended.`,
    safe:    `\`${name}\` appears active (${pct}% dead) — no action needed.`,
  };
  return summaries[severity];
}

// ─── Main mock extract ────────────────────────────────────────────────────────

interface RawSymbol {
  name: string;
  kind: 'function' | 'class' | 'variable' | 'method';
  startLine: number;
  endLine: number;
  snippet: string;
}

function extractSymbols(source: string, langId: string): RawSymbol[] {
  const lines = source.split('\n');
  const results: RawSymbol[] = [];
  const seen = new Set<string>();

  const lang = langId.replace('react', '').replace('typescriptreact', 'typescript').replace('javascriptreact', 'javascript');
  const patterns = PATTERNS[lang] || PATTERNS['javascript'];

  for (const pattern of patterns) {
    pattern.lastIndex = 0;
    let match: RegExpExecArray | null;
    while ((match = pattern.exec(source)) !== null) {
      const name = match[1];
      if (!name || seen.has(name) || name.length < 2) continue;
      seen.add(name);

      const upToMatch = source.slice(0, match.index);
      const startLine = upToMatch.split('\n').length;
      const endLine = Math.min(startLine + Math.floor(Math.random() * 20) + 3, lines.length);
      const snippet = lines[startLine - 1]?.trim() || '';

      const isClass = pattern.source.includes('class');
      const isVar = pattern.source.includes('const') && !pattern.source.includes('function');
      const kind = isClass ? 'class' : isVar ? 'variable' : 'function';

      results.push({ name, kind, startLine, endLine, snippet });
    }
  }

  return results;
}

// ─── Public API ───────────────────────────────────────────────────────────────

export async function mockAnalyze(document: vscode.TextDocument): Promise<AnalysisResult> {
  const start = Date.now();

  // Simulate network delay (remove in Phase 2 — real server has its own latency)
  await new Promise(r => setTimeout(r, 600 + Math.random() * 400));

  const source = document.getText();
  const langId = document.languageId;
  const rawSymbols = extractSymbols(source, langId);

  const symbols: SymbolResult[] = rawSymbols.map((raw, i) => {
    // Use name + position as seed for stable results on re-analysis
    const seed = raw.name.split('').reduce((acc, c) => acc + c.charCodeAt(0), 0) + raw.startLine;
    const rand = seededRandom(seed + i * 37);

    // Names starting with _ are biased toward high confidence
    const isPrivate = raw.name.startsWith('_');
    const isOld = /old|unused|deprecated|legacy|temp|todo/i.test(raw.name);
    const bias = isPrivate ? 0.3 : isOld ? 0.4 : 0;

    const confidence = Math.min(0.98, Math.max(0.02, rand() * 0.7 + bias));
    const severity = getSeverity(confidence);

    const nDead = severity === 'danger' ? 4 : severity === 'warning' ? 3 : severity === 'review' ? 2 : 1;
    const nAlive = severity === 'safe' ? 3 : severity === 'review' ? 2 : 1;

    return {
      id: `${raw.name}_${raw.startLine}`,
      name: raw.name,
      kind: raw.kind,
      startLine: raw.startLine,
      endLine: raw.endLine,
      confidence: parseFloat(confidence.toFixed(4)),
      severity,
      reasonsDead: pickN(DEAD_REASONS, nDead, rand),
      reasonsAlive: pickN(ALIVE_REASONS, nAlive, rand),
      topFeatures: buildFeatures(confidence, rand),
      summary: buildSummary(raw.name, raw.kind, confidence, severity),
      explanation: `Mock analysis: '${raw.name}' scored ${Math.round(confidence * 100)}% dead code confidence based on simulated feature analysis.`,
      snippet: raw.snippet,
    };
  });


  const dangerCount  = symbols.filter(s => s.severity === 'danger').length;
  const warningCount = symbols.filter(s => s.severity === 'warning').length;
  const reviewCount  = symbols.filter(s => s.severity === 'review').length;
  const safeCount    = symbols.filter(s => s.severity === 'safe').length;

  return {
    fileUri: document.uri.toString(),
    filename: path.basename(document.fileName),
    language: langId,
    analyzedAt: new Date().toISOString(),
    durationMs: Date.now() - start,
    symbols,
    totalSymbols: symbols.length,
    dangerCount,
    warningCount,
    reviewCount,
    safeCount,
  };
}