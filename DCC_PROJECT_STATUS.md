# Dead Code Confidence Checker (DCC) — Project Status

## Overview

The Dead Code Confidence Checker (DCC) is a VS Code extension that uses machine learning to detect dead code in Python (and other languages), providing confidence scores, explanations, and actionable UI. It integrates a Python analyzer, ML model, and a SQLite database for persistent analysis history and advanced features.

---

## Project Structure

- **dcc/** (VS Code extension)
  - `src/` — TypeScript source (extension logic, UI, decorators, dashboard, Python runner, DB bridge)
  - `analyzer.py` — Python AST/ML analyzer
  - `package.json`, `tsconfig.json`, `out/`, etc.
- **database/**
  - `db.py` — SQLite schema and DB functions
  - `dcc_analysis.db` — Analysis results/history
- **ML Part/**
  - `LR model.py`, `dead_code_model.pkl`, `scaler.pkl` — ML model and scaler
  - `Synthetic Dataset generator.py`, `dead_code_dataset.csv` — Data/tools
- **schema.sql** — DB schema
- **python_test.py** — Test file

---

## Key Features

- **Single file & workspace-wide analysis** (mock or ML-powered)
- **Inline badges & highlights** for dead code confidence
- **Dashboard webview** for results, history, and chat
- **Dead code removal** with confirmation and logging
- **Persistent analysis history** (SQLite)
- **Chat assistant** for code insights
- **Auto-analysis on file open/save**
- **Robust Python environment handling**

---

## Core Components

- **extension.ts** — Main extension logic, command registration, triggers, dashboard wiring
- **dashboard.ts/html** — Webview UI, event/message handling
- **pythonRunner.ts** — Runs analyzer.py, manages Python path/env
- **analyzer.py** — AST feature extraction, ML inference, error handling
- **db.py/dbBridge.ts** — SQLite schema, insert/fetch, Node.js bridge
- **decorator.ts** — Applies inline badges/highlights
- **statusBar.ts** — Status bar integration
- **mockAnalyzer.ts** — Fallback/mock analysis
- **types.ts** — Shared types/interfaces

---

## Database Schema

- **analysis_sessions** — Each analysis run
- **code_entities** — Functions/classes analyzed
- **feature_vectors** — ML features per entity
- **explanations** — Human-readable explanations
- **chat_history** — Chat queries/responses
- **removal_logs** — Dead code removals

---

## ML Model

- **Logistic Regression** (scikit-learn)
- Features: cyclomatic complexity, call count, dynamic call risk, is_exported, used_in_tests, file_depth, etc.
- Model/scaler loaded by analyzer.py

---

## Current Status

- ✅ Extension commands, UI, and dashboard fully functional
- ✅ Python analyzer and ML model integrated and robust
- ✅ Database schema and bridge complete
- ✅ Inline badges, hover, and status bar working
- ✅ Auto-analysis on file open/save
- ✅ Dead code removal and logging
- ✅ Environment/path handling robust (quotes, venv, etc.)
- ✅ Build scripts automate dashboard.html copying
- ✅ Project-wide and single-file analysis
- ✅ Chat assistant and history
- ⚠️ UI/UX polish and advanced dashboard features (partially complete)
- ⚠️ Multi-language/project-wide support (Python is primary)

---

## Next Steps

- UI/UX improvements for dashboard
- Advanced chat/history features
- More test projects for ML/analysis validation
- Multi-language support enhancements

---

## Last Updated

April 28, 2026
