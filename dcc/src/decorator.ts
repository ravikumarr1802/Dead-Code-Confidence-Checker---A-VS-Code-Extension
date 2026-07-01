/**
 * Decorator - applies gutter highlights and inline confidence badges
 * to the VSCode editor based on analysis results.
 */

import * as vscode from "vscode";
import { AnalysisResult, Severity, SymbolResult } from "./types";

interface SeverityStyle {
  bg: string;
  border: string;
  badgeColor: string;
  icon: string;
}

const STYLES: Record<Severity, SeverityStyle> = {
  danger: { bg: "rgba(220,38,38,0.10)", border: "#dc2626", badgeColor: "#f87171", icon: "🚨" },
  warning: { bg: "rgba(234,179,8,0.10)", border: "#ca8a04", badgeColor: "#fbbf24", icon: "⚠️" },
  review: { bg: "rgba(139,92,246,0.08)", border: "#7c3aed", badgeColor: "#a78bfa", icon: "🔍" },
  safe: { bg: "transparent", border: "transparent", badgeColor: "#34d399", icon: "✅" },
};

export class DeadCodeDecorator {
  private lineDecors: Map<Severity, vscode.TextEditorDecorationType> = new Map();
  private badgeDecors: Map<Severity, vscode.TextEditorDecorationType> = new Map();

  constructor(private context: vscode.ExtensionContext) {
    this.createDecorationTypes();
  }

  private createDecorationTypes() {
    for (const [severity, style] of Object.entries(STYLES) as [Severity, SeverityStyle][]) {
      if (severity === "safe") {
        continue;
      }

      this.lineDecors.set(
        severity,
        vscode.window.createTextEditorDecorationType({
          backgroundColor: style.bg,
          border: `0 0 0 3px solid ${style.border}`,
          borderWidth: "0 0 0 3px",
          borderStyle: "solid",
          borderColor: style.border,
          isWholeLine: true,
          overviewRulerColor: style.border,
          overviewRulerLane: vscode.OverviewRulerLane.Right,
        }),
      );

      this.badgeDecors.set(
        severity,
        vscode.window.createTextEditorDecorationType({
          after: {
            color: style.badgeColor,
            fontStyle: "italic",
            margin: "0 0 0 16px",
          },
        }),
      );
    }
  }

  apply(editor: vscode.TextEditor, result: AnalysisResult): void {
    const cfg = vscode.workspace.getConfiguration("dcc");
    const minConf = cfg.get<number>("minConfidenceThreshold", 0.3);
    const showBadge = cfg.get<boolean>("showInlineBadges", true);

    const bySeverity: Record<
      Severity,
      { line: vscode.DecorationOptions[]; badge: vscode.DecorationOptions[] }
    > = {
      danger: { line: [], badge: [] },
      warning: { line: [], badge: [] },
      review: { line: [], badge: [] },
      safe: { line: [], badge: [] },
    };

    for (const symbol of result.symbols) {
      if (symbol.confidence < minConf || symbol.severity === "safe") {
        continue;
      }

      const startLine = Math.max(0, symbol.startLine - 1);
      const range = new vscode.Range(startLine, 0, startLine, Number.MAX_SAFE_INTEGER);
      const alivePct = Math.round((1 - symbol.confidence) * 100);
      const style = STYLES[symbol.severity];
      const hover = this.buildHoverMessage(symbol);

      bySeverity[symbol.severity].line.push({ range, hoverMessage: hover });

      if (showBadge) {
        bySeverity[symbol.severity].badge.push({
          range,
          hoverMessage: hover,
          renderOptions: {
            after: {
              contentText: `${style.icon} ${alivePct}% alive`,
            },
          },
        });
      }
    }

    for (const severity of ["danger", "warning", "review"] as Severity[]) {
      const lineType = this.lineDecors.get(severity);
      const badgeType = this.badgeDecors.get(severity);
      if (lineType) {
        editor.setDecorations(lineType, bySeverity[severity].line);
      }
      if (badgeType) {
        editor.setDecorations(badgeType, bySeverity[severity].badge);
      }
    }
  }

  clear(editor: vscode.TextEditor): void {
    for (const type of [...this.lineDecors.values(), ...this.badgeDecors.values()]) {
      editor.setDecorations(type, []);
    }
  }

  clearAll(): void {
    for (const editor of vscode.window.visibleTextEditors) {
      this.clear(editor);
    }
  }

  private buildHoverMessage(symbol: SymbolResult): vscode.MarkdownString {
    const alivePct = Math.round((1 - symbol.confidence) * 100);
    const style = STYLES[symbol.severity];
    const md = new vscode.MarkdownString("", true);
    md.isTrusted = true;
    md.supportHtml = true;

    md.appendMarkdown(`### ${style.icon} \`${symbol.name}\` - ${alivePct}% alive confidence\n\n`);
    md.appendMarkdown(
      `**Kind:** ${symbol.kind} &nbsp;|&nbsp; **Severity:** \`${symbol.severity.toUpperCase()}\`\n\n`,
    );
    md.appendMarkdown("---\n\n");
    md.appendMarkdown(`*${symbol.summary}*\n\n`);

    if (symbol.reasonsDead.length) {
      md.appendMarkdown("**Evidence (dead code):**\n");
      symbol.reasonsDead.forEach((reason: string) => md.appendMarkdown(`- ❌ ${reason}\n`));
      md.appendMarkdown("\n");
    }

    if (symbol.reasonsAlive.length) {
      md.appendMarkdown("**Evidence (active code):**\n");
      symbol.reasonsAlive.forEach((reason: string) => md.appendMarkdown(`- ✅ ${reason}\n`));
      md.appendMarkdown("\n");
    }

    md.appendMarkdown("[$(graph) Open Dashboard](command:dcc.openDashboard)");
    return md;
  }

  dispose(): void {
    [...this.lineDecors.values(), ...this.badgeDecors.values()].forEach((decor) => decor.dispose());
  }
}
