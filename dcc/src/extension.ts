/**
 * Dead Code Confidence Checker — Extension Entry Point
 *
 * Wires together:
 *   mockAnalyzer  (Phase 1) → fallback
 *   pythonRunner  (Phase 2) → real ML analysis via analyzer.py
 *   DeadCodeDecorator       → inline editor highlights
 *   DashboardPanel          → WebView dashboard
 *   StatusBarManager        → status bar
 *   Hover provider          → tooltip explanations
 *   dbBridge                → SQLite persistence
 *
 * Features:
 *   - Single file analysis (mock or ML)
 *   - Workspace-wide analysis
 *   - Dead code removal with confirmation
 *   - Analysis history
 *   - Chat assistant
 */

import * as vscode from "vscode";
import * as path from "path";
import { mockAnalyze } from "./mockAnalyzer";
import { DeadCodeDecorator } from "./decorator";
import { DashboardPanel } from "./dashboard";
import { StatusBarManager } from "./statusBar";
import * as dbBridge from "./dbBridge";
import {
  runPythonAnalyzerOnFile,
  mapToAnalysisResult,
} from "./pythonRunner";
import { AnalysisResult, SymbolResult } from "./types";

// ─── Supported languages ──────────────────────────────────────────────────────
const LANGS = [
  "python",
  "javascript",
  "typescript",
  "typescriptreact",
  "javascriptreact",
];

// ─── Module-level state ───────────────────────────────────────────────────────
let decorator: DeadCodeDecorator;
let statusBar: StatusBarManager;
let lastResults: Map<string, AnalysisResult> = new Map();

function supportsRealAnalyzer(document: vscode.TextDocument): boolean {
  return document.languageId === "python";
}

// ─── Activation ───────────────────────────────────────────────────────────────
export function activate(context: vscode.ExtensionContext) {
  console.log("[DCC] Extension activated");

  // Initialize DB on activation
  dbBridge.initializeDatabase().catch((err) => {
    console.warn("[DCC] DB init warning:", err);
  });

  decorator = new DeadCodeDecorator(context);
  statusBar = new StatusBarManager();

  // ── Commands ────────────────────────────────────────────────────────────

  // 1) Analyze current file
  context.subscriptions.push(
    vscode.commands.registerCommand("dcc.analyzeFile", async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) {
        vscode.window.showWarningMessage("No active editor open.");
        return;
      }
      await runAnalysis(editor.document, context);
    }),
  );

  // 2) Open Dashboard
  context.subscriptions.push(
    vscode.commands.registerCommand("dcc.openDashboard", () => {
      const result = vscode.window.activeTextEditor
        ? lastResults.get(
            vscode.window.activeTextEditor.document.uri.toString(),
          )
        : undefined;
      DashboardPanel.createOrShow(context.extensionUri, result ?? null);
    }),
  );

  // 3) Clear decorations
  context.subscriptions.push(
    vscode.commands.registerCommand("dcc.clearDecorations", () => {
      decorator.clearAll();
      statusBar.idle();
    }),
  );

  // 4) Analyze entire workspace
  context.subscriptions.push(
    vscode.commands.registerCommand("dcc.analyzeWorkspace", async () => {
      await analyzeWorkspace(context);
    }),
  );

  // Auto-analyze when a Python file is opened
  context.subscriptions.push(
    vscode.window.onDidChangeActiveTextEditor(async (editor) => {
      if (!editor) return;
      if (editor.document.languageId === "python") {
        await runAnalysis(editor.document, context);
      }
    }),
  );

  // 6) Remove dead code
  context.subscriptions.push(
    vscode.commands.registerCommand("dcc.removeDeadCode", async () => {
      await removeDeadCode(context);
    }),
  );

  // 7) Show analysis history
  context.subscriptions.push(
    vscode.commands.registerCommand("dcc.showHistory", async () => {
      const projectPath =
        vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || "";
      try {
        const history = await dbBridge.fetchPastAnalysis(projectPath);
        DashboardPanel.createOrShow(context.extensionUri, null);
        // Small delay to ensure panel is ready
        setTimeout(() => {
          DashboardPanel.current?.sendHistory(history);
        }, 500);
      } catch (err) {
        vscode.window.showErrorMessage(
          "Failed to fetch analysis history: " + err,
        );
      }
    }),
  );

  // 8) Open Chat assistant
  context.subscriptions.push(
    vscode.commands.registerCommand("dcc.openChat", async () => {
      DashboardPanel.createOrShow(context.extensionUri, null);
      setTimeout(() => {
        DashboardPanel.current?.sendOpenChat();
      }, 500);
    }),
  );

  // 9) Fetch past analysis (called from dashboard)
  context.subscriptions.push(
    vscode.commands.registerCommand("dcc.fetchPastAnalysis", async () => {
      const projectPath =
        vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || "";
      try {
        const history = await dbBridge.fetchPastAnalysis(projectPath);
        DashboardPanel.current?.sendHistory(history);
      } catch (err) {
        vscode.window.showErrorMessage(
          "Failed to fetch analysis history: " + err,
        );
      }
    }),
  );

  // ── Auto-analyze on save ─────────────────────────────────────────────────

  context.subscriptions.push(
    vscode.workspace.onDidSaveTextDocument(async (doc) => {
      const cfg = vscode.workspace.getConfiguration("dcc");
      if (!cfg.get<boolean>("analyzeOnSave", true)) return;
      if (!LANGS.includes(doc.languageId)) return;
      await runAnalysis(doc, context);
    }),
  );

  // ── Refresh decorations when switching editors ────────────────────────────

  context.subscriptions.push(
    vscode.window.onDidChangeActiveTextEditor((editor) => {
      if (!editor) return;
      const result = lastResults.get(editor.document.uri.toString());
      if (result) {
        decorator.apply(editor, result);
        statusBar.showResult(result);
      } else {
        statusBar.idle();
      }
    }),
  );

  // ── Hover provider — inline explanation on mouse-over ─────────────────────

  context.subscriptions.push(
    vscode.languages.registerHoverProvider(LANGS, {
      provideHover(document, position): vscode.Hover | null {
        const result = lastResults.get(document.uri.toString());
        if (!result) return null;

        const line = position.line + 1;
        const sym = result.symbols.find(
          (s) => line >= s.startLine && line <= s.endLine,
        );
        if (!sym || sym.confidence < 0.15) return null;

        const pct = Math.round(sym.confidence * 100);
        const icons: Record<string, string> = {
          danger: "🚨",
          warning: "⚠️",
          review: "🔍",
          safe: "✅",
        };
        const icon = icons[sym.severity];

        const md = new vscode.MarkdownString("", true);
        md.isTrusted = true;
        md.appendMarkdown(`### ${icon} Dead Code: \`${sym.name}\`\n\n`);
        md.appendMarkdown(
          `**${pct}% confidence** of being dead code — **${sym.severity.toUpperCase()}**\n\n`,
        );
        md.appendMarkdown(`*${sym.summary}*\n\n`);

        if (sym.explanation) {
          md.appendMarkdown(`**Explanation:** ${sym.explanation}\n\n`);
        }

        if (sym.reasonsDead.length) {
          md.appendMarkdown(`**Why it might be dead:**\n`);
          sym.reasonsDead.forEach((r: string) =>
            md.appendMarkdown(`- ❌ ${r}\n`),
          );
          md.appendMarkdown("\n");
        }
        if (sym.reasonsAlive.length) {
          md.appendMarkdown(`**Why it might be active:**\n`);
          sym.reasonsAlive.forEach((r: string) =>
            md.appendMarkdown(`- ✅ ${r}\n`),
          );
          md.appendMarkdown("\n");
        }

        if (sym.topFeatures && sym.topFeatures.length) {
          md.appendMarkdown(`**Top Features:**\n`);
          sym.topFeatures.slice(0, 4).forEach((f) => {
            const arrow = f.direction === "dead" ? "↑" : "↓";
            md.appendMarkdown(
              `- ${f.label}: ${f.value} (${arrow} ${f.contribution > 0 ? "+" : ""}${f.contribution.toFixed(3)})\n`,
            );
          });
          md.appendMarkdown("\n");
        }

        md.appendMarkdown(
          `[$(graph) Open Dashboard](command:dcc.openDashboard)`,
        );
        return new vscode.Hover(md);
      },
    }),
  );

  // ── Auto-analyze active file on startup ──────────────────────────────────

  const activeDoc = vscode.window.activeTextEditor?.document;
  if (activeDoc && LANGS.includes(activeDoc.languageId)) {
    setTimeout(() => runAnalysis(activeDoc, context).catch(() => {}), 800);
  }

  context.subscriptions.push(
    { dispose: () => decorator.dispose() },
    { dispose: () => statusBar.dispose() },
  );

  // Handle messages from the dashboard
  context.subscriptions.push(
    vscode.commands.registerCommand(
      "dcc.handleChatMessage",
      async (query: string, contextFile: string) => {
        await handleChatMessage(query, contextFile);
      },
    ),
  );
}

// ─── Core analysis runner ─────────────────────────────────────────────────────

async function runAnalysis(
  document: vscode.TextDocument,
  context: vscode.ExtensionContext,
): Promise<void> {
  const docUri = document.uri.toString();

  statusBar.analyzing();
  DashboardPanel.current?.sendAnalyzing();

  try {
    const cfg = vscode.workspace.getConfiguration("dcc");
    const useMock = cfg.get<boolean>("useMockData", false);

    let result: AnalysisResult;

    if (useMock || !supportsRealAnalyzer(document)) {
      // ── Phase 1: mock ──────────────────────────────────────────────────
      result = await mockAnalyze(document);
    } else {
      // ── Phase 2: real ML analysis via analyzer.py ──────────────────────
      const analyzerPath = context.asAbsolutePath("analyzer.py");
      const filePath = document.uri.fsPath;
      const projectRoot =
        vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || undefined;

      const start = Date.now();
      const rawResults = await runPythonAnalyzerOnFile(
        filePath,
        analyzerPath,
        projectRoot,
      );
      result = mapToAnalysisResult(
        rawResults,
        docUri,
        path.basename(document.fileName),
        document.languageId,
        Date.now() - start,
      );

    }

    await storeAnalysisInDB(result, document.fileName);

    // Cache result
    lastResults.set(docUri, result);

    // Apply decorations to the editor that triggered analysis
    const editor = vscode.window.visibleTextEditors.find(
      (e) => e.document.uri.toString() === docUri,
    );
    if (editor) decorator.apply(editor, result);

    // Update status bar
    statusBar.showResult(result);

    // Push to dashboard if open
    DashboardPanel.update(result);

    // Summary notification for danger/warning
    const urgent = result.dangerCount + result.warningCount;
    if (urgent > 0) {
      vscode.window
        .showInformationMessage(
          `Dead Code: found ${result.dangerCount} danger + ${result.warningCount} warning in ${result.filename}`,
          "Open Dashboard",
          "Dismiss",
        )
        .then((action) => {
          if (action === "Open Dashboard") {
            DashboardPanel.createOrShow(context.extensionUri, result);
          }
        });
    }
  } catch (err: any) {
    console.error("[DCC] Analysis error:", err);
    statusBar.error();
    DashboardPanel.current?.sendError(err.message || String(err));

    vscode.window.showErrorMessage(`Dead Code Checker: ${err.message || err}`);
  }
}

// ─── Workspace Analysis ───────────────────────────────────────────────────────

async function analyzeWorkspace(
  context: vscode.ExtensionContext,
): Promise<void> {
  const workspaceFolders = vscode.workspace.workspaceFolders;
  if (!workspaceFolders || workspaceFolders.length === 0) {
    vscode.window.showWarningMessage("No workspace folder open.");
    return;
  }

  const rootPath = workspaceFolders[0].uri.fsPath;
  const cfg = vscode.workspace.getConfiguration("dcc");
  const useMock = cfg.get<boolean>("useMockData", false);

  // Find all supported files
  const fileExtensions = useMock ? ["py", "js", "ts", "jsx", "tsx"] : ["py"];
  const excludePatterns = [
    "node_modules",
    ".git",
    "__pycache__",
    "venv",
    ".venv",
    "dist",
    "build",
    "out",
    ".next",
  ];

  const allFiles: vscode.Uri[] = [];
  for (const ext of fileExtensions) {
    const pattern = `**/*.${ext}`;
    const files = await vscode.workspace.findFiles(
      pattern,
      `{${excludePatterns.map((e) => `**/${e}/**`).join(",")}}`,
      500, // limit
    );
    allFiles.push(...files);
  }

  if (allFiles.length === 0) {
    vscode.window.showInformationMessage(
      "No supported files found in workspace.",
    );
    return;
  }

  // Show progress
  await vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: "Dead Code: Analyzing Workspace",
      cancellable: true,
    },
    async (progress, token) => {
      let analyzed = 0;
      let allSymbols: AnalysisResult[] = [];

      for (const fileUri of allFiles) {
        if (token.isCancellationRequested) break;

        progress.report({
          message: `${analyzed + 1}/${allFiles.length}: ${path.basename(fileUri.fsPath)}`,
          increment: (1 / allFiles.length) * 100,
        });

        try {
          const doc = await vscode.workspace.openTextDocument(fileUri);

          if (useMock || !supportsRealAnalyzer(doc)) {
            const result = await mockAnalyze(doc);
            lastResults.set(doc.uri.toString(), result);
            allSymbols.push(result);
          } else {
            const analyzerPath = context.asAbsolutePath("analyzer.py");
            const start = Date.now();
            const rawResults = await runPythonAnalyzerOnFile(
              fileUri.fsPath,
              analyzerPath,
              rootPath,
            );
            const result = mapToAnalysisResult(
              rawResults,
              doc.uri.toString(),
              path.basename(doc.fileName),
              doc.languageId,
              Date.now() - start,
            );
            lastResults.set(doc.uri.toString(), result);
            allSymbols.push(result);

          }

          await storeAnalysisInDB(allSymbols[allSymbols.length - 1], doc.fileName);
        } catch (err) {
          console.warn(`[DCC] Failed to analyze ${fileUri.fsPath}:`, err);
        }

        analyzed++;
      }

      // Build aggregate result for dashboard
      const totalDanger = allSymbols.reduce((s, r) => s + r.dangerCount, 0);
      const totalWarning = allSymbols.reduce((s, r) => s + r.warningCount, 0);
      const totalReview = allSymbols.reduce((s, r) => s + r.reviewCount, 0);
      const totalSafe = allSymbols.reduce((s, r) => s + r.safeCount, 0);
      const totalSymbolCount = allSymbols.reduce(
        (s, r) => s + r.totalSymbols,
        0,
      );

      // Apply decorations to currently visible editors
      for (const editor of vscode.window.visibleTextEditors) {
        const result = lastResults.get(editor.document.uri.toString());
        if (result) {
          decorator.apply(editor, result);
        }
      }

      vscode.window
        .showInformationMessage(
          `Workspace Analysis Complete: ${analyzed} files, ${totalSymbolCount} symbols ` +
            `(${totalDanger} danger, ${totalWarning} warning, ${totalReview} review, ${totalSafe} safe)`,
          "Open Dashboard",
        )
        .then((action) => {
          if (action === "Open Dashboard") {
            // Show last analyzed file's result in dashboard, or first with issues
            const resultWithIssues = allSymbols.find(
              (r) => r.dangerCount + r.warningCount > 0,
            );
            DashboardPanel.createOrShow(
              context.extensionUri,
              resultWithIssues || allSymbols[0] || null,
            );
          }
        });
    },
  );
}

// ─── Dead Code Removal ────────────────────────────────────────────────────────

async function removeDeadCode(context: vscode.ExtensionContext): Promise<void> {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    vscode.window.showWarningMessage("No active editor open.");
    return;
  }

  const docUri = editor.document.uri.toString();
  const result = lastResults.get(docUri);
  if (!result) {
    vscode.window.showWarningMessage(
      "No analysis results for this file. Run analysis first.",
    );
    return;
  }

  // Find symbols at or near the cursor
  const cursorLine = editor.selection.active.line + 1;
  const sym = result.symbols.find(
    (s) => cursorLine >= s.startLine && cursorLine <= s.endLine,
  );

  if (!sym) {
    // Show a quick pick of all removable symbols
    const removable = result.symbols.filter((s) => s.confidence >= 0.55);
    if (removable.length === 0) {
      vscode.window.showInformationMessage(
        "No high-confidence dead code found to remove.",
      );
      return;
    }

    const items = removable.map((s) => ({
      label: `$(trash) ${s.name}`,
      description: `${Math.round(s.confidence * 100)}% — ${s.severity}`,
      detail: `Lines ${s.startLine}–${s.endLine}: ${s.summary}`,
      symbol: s,
    }));

    const picked = await vscode.window.showQuickPick(items, {
      placeHolder: "Select dead code to remove",
      title: "Remove Dead Code",
    });

    if (picked) {
      await performRemoval(editor, picked.symbol);
    }
  } else {
    await performRemoval(editor, sym);
  }
}

async function performRemoval(
  editor: vscode.TextEditor,
  sym: SymbolResult,
): Promise<void> {
  const pct = Math.round(sym.confidence * 100);

  const confirm = await vscode.window.showWarningMessage(
    `Remove \`${sym.name}\` (${pct}% dead confidence)?\n\nLines ${sym.startLine}–${sym.endLine}`,
    { modal: true },
    "Remove",
    "Cancel",
  );

  if (confirm !== "Remove") return;

  const startLine = Math.max(0, sym.startLine - 1);
  const endLine = Math.min(editor.document.lineCount - 1, sym.endLine);

  // Get the code being removed for logging
  const removedRange = new vscode.Range(
    startLine,
    0,
    endLine,
    editor.document.lineAt(endLine).text.length,
  );
  const removedCode = editor.document.getText(removedRange);

  // Perform the edit
  const success = await editor.edit((editBuilder) => {
    // Also remove the trailing newline if present
    const deleteEnd =
      endLine + 1 < editor.document.lineCount
        ? new vscode.Position(endLine + 1, 0)
        : new vscode.Position(
            endLine,
            editor.document.lineAt(endLine).text.length,
          );
    editBuilder.delete(
      new vscode.Range(startLine, 0, deleteEnd.line, deleteEnd.character),
    );
  });

  if (success) {
    // Log removal to database
    try {
      await dbBridge.insertRemovalLog(
        0, // entity_id — 0 for ad-hoc removals
        editor.document.fileName,
        removedCode,
        sym.confidence,
      );
    } catch (err) {
      console.warn("[DCC] Failed to log removal:", err);
    }

    vscode.window.showInformationMessage(
      `Removed \`${sym.name}\` (${sym.startLine}–${sym.endLine}). Undo with Ctrl+Z if needed.`,
    );

    // Re-run analysis after removal
    const doc = editor.document;
    setTimeout(async () => {
      await vscode.commands.executeCommand("dcc.analyzeFile");
    }, 500);
  }
}

// ─── Chat Message Handler ─────────────────────────────────────────────────────

async function handleChatMessage(
  query: string,
  contextFile: string,
): Promise<void> {
  const qLower = query.toLowerCase().trim();
  let response = "";

  // Get current analysis context
  const activeEditor = vscode.window.activeTextEditor;
  const currentResult = activeEditor
    ? lastResults.get(activeEditor.document.uri.toString())
    : undefined;

  // Rule-based chat responses using analysis data
  if (
    qLower.includes("how many") &&
    (qLower.includes("dead") || qLower.includes("danger"))
  ) {
    if (currentResult) {
      response =
        `In **${currentResult.filename}**, I found:\n` +
        `• 🚨 **${currentResult.dangerCount}** danger (≥75% confidence)\n` +
        `• ⚠️ **${currentResult.warningCount}** warnings (55–75%)\n` +
        `• 🔍 **${currentResult.reviewCount}** need review (35–55%)\n` +
        `• ✅ **${currentResult.safeCount}** appear safe (<35%)\n` +
        `\nTotal: **${currentResult.totalSymbols}** symbols analyzed.`;
    } else {
      response =
        "No analysis loaded. Run **Dead Code: Analyze Current File** first.";
    }
  } else if (
    qLower.includes("safe to remove") ||
    qLower.includes("can i remove") ||
    qLower.includes("should i remove")
  ) {
    if (currentResult) {
      const safe = currentResult.symbols.filter((s) => s.confidence >= 0.75);
      if (safe.length > 0) {
        response =
          `These symbols are **safe to remove** (≥75% confidence):\n\n` +
          safe
            .map(
              (s) =>
                `• \`${s.name}\` — ${Math.round(s.confidence * 100)}% dead (L${s.startLine}–${s.endLine})\n  _${s.summary}_`,
            )
            .join("\n\n") +
          `\n\nUse the **🗑 Remove** button on each card, or run **Dead Code: Remove Dead Code at Cursor**.`;
      } else {
        response =
          "No symbols have high enough confidence (≥75%) to be safely removed without manual review.";
      }
    } else {
      response = "Run an analysis first to get removal recommendations.";
    }
  } else if (qLower.includes("explain") || qLower.includes("why")) {
    // Try to find a specific function name in the query
    if (currentResult) {
      const matchedSym = currentResult.symbols.find((s) =>
        qLower.includes(s.name.toLowerCase()),
      );
      if (matchedSym) {
        response =
          `### \`${matchedSym.name}\` — ${Math.round(matchedSym.confidence * 100)}% dead\n\n` +
          `**${matchedSym.summary}**\n\n` +
          (matchedSym.explanation
            ? `**Explanation:** ${matchedSym.explanation}\n\n`
            : "") +
          (matchedSym.reasonsDead.length
            ? `**Dead code signals:**\n${matchedSym.reasonsDead.map((r) => `• ❌ ${r}`).join("\n")}\n\n`
            : "") +
          (matchedSym.reasonsAlive.length
            ? `**Active code signals:**\n${matchedSym.reasonsAlive.map((r) => `• ✅ ${r}`).join("\n")}\n\n`
            : "") +
          (matchedSym.topFeatures && matchedSym.topFeatures.length
            ? `**Feature contributions:**\n${matchedSym.topFeatures.map((f) => `• ${f.label}: ${f.value} (${f.direction === "dead" ? "↑" : "↓"} ${f.contribution > 0 ? "+" : ""}${f.contribution.toFixed(3)})`).join("\n")}`
            : "");
      } else {
        response =
          "I couldn't find that specific function. Available symbols:\n" +
          currentResult.symbols
            .map((s) => `• \`${s.name}\` — ${Math.round(s.confidence * 100)}%`)
            .join("\n") +
          "\n\nTry asking: _explain [function_name]_";
      }
    } else {
      response = "No analysis loaded. Run analysis first to get explanations.";
    }
  } else if (qLower.includes("summary") || qLower.includes("overview")) {
    if (currentResult) {
      const topDead = currentResult.symbols
        .filter((s) => s.confidence > 0.5)
        .sort((a, b) => b.confidence - a.confidence)
        .slice(0, 5);

      response =
        `### Analysis Summary for \`${currentResult.filename}\`\n\n` +
        `**Language:** ${currentResult.language}\n` +
        `**Analyzed:** ${new Date(currentResult.analyzedAt).toLocaleString()}\n` +
        `**Duration:** ${currentResult.durationMs}ms\n\n` +
        `| Severity | Count |\n|----------|-------|\n` +
        `| 🚨 Danger | ${currentResult.dangerCount} |\n` +
        `| ⚠️ Warning | ${currentResult.warningCount} |\n` +
        `| 🔍 Review | ${currentResult.reviewCount} |\n` +
        `| ✅ Safe | ${currentResult.safeCount} |\n\n` +
        (topDead.length > 0
          ? `**Top suspected dead code:**\n` +
            topDead
              .map(
                (s) => `• \`${s.name}\` — ${Math.round(s.confidence * 100)}%`,
              )
              .join("\n")
          : "No significant dead code detected! 🎉");
    } else {
      response =
        "No analysis loaded. Save a file or run **Analyze Current File**.";
    }
  } else if (qLower.includes("help") || qLower.includes("what can")) {
    response =
      `### Dead Code Chat Assistant — Help\n\n` +
      `I can answer questions about your dead code analysis. Try:\n\n` +
      `• **"How many dead functions?"** — Get counts by severity\n` +
      `• **"What's safe to remove?"** — List high-confidence dead code\n` +
      `• **"Explain [function_name]"** — Get detailed reasoning for a specific function\n` +
      `• **"Summary"** — Overview of current analysis\n` +
      `• **"What is dead code?"** — Learn about dead code detection\n\n` +
      `_Tip: Run an analysis first (Ctrl+S or Analyze File) for context-aware answers._`;
  } else if (
    qLower.includes("what is dead code") ||
    qLower.includes("what is a dead code")
  ) {
    response =
      `### What is Dead Code?\n\n` +
      `Dead code refers to code that is **never executed** during program runtime. ` +
      `This includes:\n\n` +
      `• **Unreachable code** — code after a return/throw statement\n` +
      `• **Unused functions** — functions that are never called\n` +
      `• **Deprecated modules** — old code kept "just in case"\n` +
      `• **Debug/temp code** — logging or test code left behind\n\n` +
      `**Why remove it?**\n` +
      `• Reduces maintenance burden\n` +
      `• Improves code readability\n` +
      `• Reduces binary/bundle size\n` +
      `• Eliminates potential security vulnerabilities`;
  } else {
    response =
      `I'm not sure how to answer that. Here are things I can help with:\n\n` +
      `• **"How many dead functions?"**\n` +
      `• **"What's safe to remove?"**\n` +
      `• **"Explain [function_name]"**\n` +
      `• **"Summary"**\n` +
      `• **"Help"**`;
  }

  // Save to DB
  try {
    await dbBridge.logChatQuery(query, response, contextFile || undefined);
  } catch (err) {
    console.warn("[DCC] Failed to log chat:", err);
  }

  // Send response to dashboard
  DashboardPanel.current?.sendChatResponse(query, response);
}

// ─── DB Storage Helper ────────────────────────────────────────────────────────

async function storeAnalysisInDB(
  result: AnalysisResult,
  filePath: string,
): Promise<void> {
  try {
    const projectPath =
      vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || "";
    const sessionId = await dbBridge.insertAnalysisSession(projectPath, 1);

    for (const sym of result.symbols) {
      const entityId = await dbBridge.insertCodeEntity(
        sessionId,
        filePath,
        sym.name,
        sym.kind,
        sym.startLine,
        sym.endLine,
        sym.confidence,
      );

      if (sym.features) {
        await dbBridge.insertFeatureVector(
          entityId,
          sym.features.call_count || 0,
          sym.features.is_exported || 0,
          sym.features.used_in_tests || 0,
          sym.features.dynamic_call_risk || 0,
          sym.features.cyclomatic_complexity || 0,
          sym.features.file_depth || 0,
        );
      }

      if (sym.xai_explanation) {
        await dbBridge.insertXaiExplanation(entityId, sym.xai_explanation);
      } else if (sym.explanation) {
        await dbBridge.insertExplanation(entityId, sym.explanation);
      }
    }
  } catch (err) {
    console.warn("[DCC] Failed to store analysis in DB:", err);
  }
}

// ─── Deactivation ─────────────────────────────────────────────────────────────
export function deactivate() {
  decorator?.clearAll();
}
