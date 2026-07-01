/**
 * Dashboard WebView Panel
 *
 * A rich single-page dashboard rendered inside a VSCode WebviewPanel.
 * All UI logic lives in the injected HTML/CSS/JS — no external bundler needed.
 *
 * Features:
 * - Analysis results with stats, filters, sorting, symbol cards
 * - Dead code removal button per symbol
 * - Analysis history tab
 * - Chat assistant panel
 */

import * as vscode from "vscode";
import { AnalysisResult } from "./types";

export class DashboardPanel {
  public static current: DashboardPanel | undefined;
  public readonly panel: vscode.WebviewPanel;
  private disposables: vscode.Disposable[] = [];

  // ── Static factory ──────────────────────────────────────────────────────

  static createOrShow(
    extensionUri: vscode.Uri,
    result?: AnalysisResult | null,
  ): void {
    let col: vscode.ViewColumn = vscode.ViewColumn.Beside;
    if (DashboardPanel.current) {
      col = DashboardPanel.current.panel.viewColumn ?? vscode.ViewColumn.Beside;
    } else if (vscode.window.activeTextEditor) {
      col = vscode.ViewColumn.Beside;
    } else {
      col = vscode.ViewColumn.Two;
    }

    if (DashboardPanel.current) {
      DashboardPanel.current.panel.reveal(col);
      if (result) DashboardPanel.current.send(result);
      return;
    }

    const panel = vscode.window.createWebviewPanel(
      "dccDashboard",
      "⬡ Dead Code Dashboard",
      col,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
        localResourceRoots: [extensionUri],
      },
    );

    DashboardPanel.current = new DashboardPanel(panel, extensionUri);
    if (result) DashboardPanel.current.send(result);
  }

  static update(result: AnalysisResult): void {
    DashboardPanel.current?.send(result);
  }

  // ── Constructor ─────────────────────────────────────────────────────────

  private constructor(panel: vscode.WebviewPanel, extensionUri: vscode.Uri) {
    this.panel = panel;
    this.panel.webview.html = this.getHtml();

    this.panel.onDidDispose(
      () => {
        DashboardPanel.current = undefined;
        this.disposables.forEach((d) => d.dispose());
        this.disposables = [];
      },
      null,
      this.disposables,
    );

    // Messages from the webview
    this.panel.webview.onDidReceiveMessage(
      (msg) => {
        if (msg.type === "jumpToLine") {
          const editor = vscode.window.activeTextEditor;
          if (editor) {
            const line = Math.max(0, (msg.line as number) - 1);
            const pos = new vscode.Position(line, 0);
            editor.selection = new vscode.Selection(pos, pos);
            editor.revealRange(
              new vscode.Range(pos, pos),
              vscode.TextEditorRevealType.InCenter,
            );
            vscode.window.showTextDocument(editor.document, {
              viewColumn: vscode.ViewColumn.One,
              preserveFocus: true,
            });
          }
        }
        if (msg.type === "analyze") {
          vscode.commands.executeCommand("dcc.analyzeFile");
        }
        if (msg.type === "analyzeWorkspace") {
          vscode.commands.executeCommand("dcc.analyzeWorkspace");
        }
        if (msg.type === "removeSymbol") {
          this.handleRemoveSymbol(msg.symbolName, msg.startLine, msg.endLine);
        }
        if (msg.type === "fetchHistory") {
          vscode.commands.executeCommand("dcc.fetchPastAnalysis");
        }
        if (msg.type === "chatMessage") {
          vscode.commands.executeCommand(
            "dcc.handleChatMessage",
            msg.query,
            msg.contextFile || "",
          );
        }
      },
      null,
      this.disposables,
    );
  }

  // ── Handle removal from dashboard ───────────────────────────────────────

  private async handleRemoveSymbol(
    symbolName: string,
    startLine: number,
    endLine: number,
  ): Promise<void> {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
      vscode.window.showWarningMessage("No active editor — cannot remove.");
      return;
    }

    const confirm = await vscode.window.showWarningMessage(
      `Remove \`${symbolName}\` (lines ${startLine}–${endLine})?`,
      { modal: true },
      "Remove",
      "Cancel",
    );

    if (confirm !== "Remove") return;

    const sLine = Math.max(0, startLine - 1);
    const eLine = Math.min(editor.document.lineCount - 1, endLine);
    const removedRange = new vscode.Range(
      sLine,
      0,
      eLine,
      editor.document.lineAt(eLine).text.length,
    );
    const removedCode = editor.document.getText(removedRange);

    const success = await editor.edit((editBuilder) => {
      const deleteEnd =
        eLine + 1 < editor.document.lineCount
          ? new vscode.Position(eLine + 1, 0)
          : new vscode.Position(
              eLine,
              editor.document.lineAt(eLine).text.length,
            );
      editBuilder.delete(
        new vscode.Range(sLine, 0, deleteEnd.line, deleteEnd.character),
      );
    });

    if (success) {
      vscode.window.showInformationMessage(
        `Removed \`${symbolName}\`. Undo with Ctrl+Z.`,
      );
      // Re-analyze
      setTimeout(() => {
        vscode.commands.executeCommand("dcc.analyzeFile");
      }, 500);
    }
  }

  // ── Data bridge ─────────────────────────────────────────────────────────

  send(result: AnalysisResult): void {
    this.panel.webview.postMessage({ type: "result", data: result });
  }

  sendAnalyzing(): void {
    this.panel.webview.postMessage({ type: "analyzing" });
  }

  sendError(message: string): void {
    this.panel.webview.postMessage({ type: "error", message });
  }

  sendHistory(history: any[]): void {
    this.panel.webview.postMessage({ type: "history", data: history });
  }

  sendOpenChat(): void {
    this.panel.webview.postMessage({ type: "openChat" });
  }

  sendChatResponse(query: string, response: string): void {
    this.panel.webview.postMessage({
      type: "chatResponse",
      query,
      response,
    });
  }

  // ── HTML ─────────────────────────────────────────────────────────────────

  private getHtml(): string {
    // Load HTML from external file to avoid template literal parsing issues
    const fs = require("fs");
    const path = require("path");
    const htmlPath = path.join(__dirname, "dashboard.html");
    try {
      return fs.readFileSync(htmlPath, "utf8");
    } catch (err: any) {
      return (
        "<html><body><h1>Error loading dashboard HTML</h1><p>" +
        err.message +
        "</p></body></html>"
      );
    }
  }

  public dispose() {
    this.disposables.forEach((d) => d.dispose());
    this.disposables = [];
  }
}
