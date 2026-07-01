# Project Codebase Documentation

## Overview

This document provides a comprehensive explanation of all code development completed so far in the project, including the structure, purpose, and key features of each major component.

---

## 1. dataprep_magic_project

### Purpose

A mock ETL (Extract, Transform, Load) library designed for testing static analysis tools. It intentionally includes code smells, dead code, dynamic calls, and complex logic to challenge analyzers.

### Structure

- **pipeline.py**: Orchestrates the ETL process by coordinating extraction, transformation, and loading.
- **extract/**
  - `api_client.py`: API client with decorators and dynamic method calls (e.g., `getattr` on `requests`).
  - `csv_reader.py`: Mocks CSV reading; includes dead code for Excel extraction.
- **transform/**
  - `cleaners.py`: Data cleaning with high cyclomatic complexity and unsafe `eval()` usage.
  - `aggregators.py`: Contains dead code for aggregation (never used).
  - `utils.py`: Internal helpers for string sanitization and null checks.
- **load/**
  - `db_writer.py`: Simulates writing to a database; includes dead code for MongoDB.

### Notable Features

- **Dead Code**: Several functions/classes are intentionally unreferenced.
- **Dynamic Calls**: Uses `getattr` and `eval()` to test static analysis.
- **Complexity**: Functions with high cyclomatic complexity for tool evaluation.

---

## 2. database

### Purpose

Handles all database operations for analysis results, using SQLite.

### Structure

- **db.py**: Defines schema, connection logic, and CRUD operations for:
  - Analysis sessions
  - Code entities
  - Feature vectors

### Notable Features

- Modular functions for initializing and interacting with the database.
- Used as a backend for the VS Code extension's persistence layer.

---

## 3. dcc (VS Code Extension)

### Purpose

Implements the Dead Code Confidence Checker as a VS Code extension, integrating ML/AST analysis, UI, and database.

### Structure

- **analyzer.py**: AST-based analysis, feature extraction, and explainable reasoning for code entities.
- **llm_pipeline.py**: Integrates DeepSeek and OpenAI APIs for explainable AI (XAI) and combines ML/AST features.
- **src/**
  - `dashboard.ts`: Renders the dashboard WebView panel in VS Code, showing analysis results and history.
  - `dbBridge.ts`: Node.js bridge to interact with the Python SQLite backend.
  - `extension.ts`: Main entry point; wires together all extension features (analysis, UI, persistence, chat, etc.).
  - Other files: Decorators, status bar, mock analyzer, Python runner, and type definitions.

### Notable Features

- **Hybrid Analysis**: Combines static (AST/ML) and LLM-based reasoning.
- **WebView Dashboard**: Rich UI for results, history, and chat.
- **Dead Code Removal**: Inline and dashboard-based dead code removal.
- **Persistence**: Stores analysis sessions and results in SQLite via Python backend.

---

## 4. ML Part (docs/ML Part/)

### Purpose

Contains datasets and scripts for ML model development and synthetic data generation.

### Structure

- **dead_code_dataset.csv**: Dataset for training/testing dead code detection models.
- **LR model.py**: Logistic Regression model for code analysis.
- **Synthetic Dataset generator.py**: Script to generate synthetic datasets for experiments.

---

## 5. Testing

### Purpose

Unit and integration tests for ETL and analysis modules.

### Structure

- **tests/**
  - `test_extract.py`: Tests for extraction logic.
  - `test_transform.py`: Tests for transformation logic.

---

## 6. Miscellaneous

- **generate_project.py**: Script to scaffold the project structure and boilerplate files.
- **schema.sql**: SQL schema for database initialization.
- **README.md**: High-level project overview and usage instructions.

---

## Summary

This project demonstrates a full-stack approach to code analysis, combining Python ETL, ML, explainable AI, and a VS Code extension with a rich UI and persistent storage. The codebase is intentionally complex to facilitate research and tool evaluation in static/dynamic code analysis and explainability.
