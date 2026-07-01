/**
 * Status bar item that shows live analysis state.
 */

import * as vscode from 'vscode';
import { AnalysisResult } from './types';

export class StatusBarManager {
  private item: vscode.StatusBarItem;

  constructor() {
    this.item = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 200);
    this.item.command = 'dcc.openDashboard';
    this.idle();
    this.item.show();
  }

  idle(): void {
    this.item.text = '$(search) Dead Code';
    this.item.tooltip = 'Click to open Dead Code Dashboard';
    this.item.backgroundColor = undefined;
    this.item.color = undefined;
  }

  analyzing(): void {
    this.item.text = '$(sync~spin) Analyzing…';
    this.item.tooltip = 'Running dead code analysis…';
    this.item.backgroundColor = undefined;
    this.item.color = undefined;
  }

  showResult(result: AnalysisResult): void {
    const { dangerCount, warningCount, reviewCount, totalSymbols } = result;

    if (dangerCount > 0) {
      this.item.text = `$(error) ${dangerCount} dead`;
      this.item.tooltip = `${dangerCount} danger, ${warningCount} warning — click to review`;
      this.item.backgroundColor = new vscode.ThemeColor('statusBarItem.errorBackground');
      this.item.color = undefined;
    } else if (warningCount > 0) {
      this.item.text = `$(warning) ${warningCount} warning`;
      this.item.tooltip = `${warningCount} warnings, ${reviewCount} to review — click to open dashboard`;
      this.item.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
      this.item.color = undefined;
    } else if (reviewCount > 0) {
      this.item.text = `$(info) ${reviewCount} to review`;
      this.item.tooltip = `${reviewCount} symbols need review — click to open dashboard`;
      this.item.backgroundColor = undefined;
      this.item.color = new vscode.ThemeColor('statusBarItem.prominentForeground');
    } else {
      this.item.text = `$(check) Clean (${totalSymbols})`;
      this.item.tooltip = `All ${totalSymbols} symbols look active — click to open dashboard`;
      this.item.backgroundColor = undefined;
      this.item.color = undefined;
    }
  }

  error(): void {
    this.item.text = '$(error) Dead Code (error)';
    this.item.tooltip = 'Analysis failed — check Output panel';
    this.item.backgroundColor = new vscode.ThemeColor('statusBarItem.errorBackground');
    this.item.color = undefined;
  }

  dispose(): void {
    this.item.dispose();
  }
}