import ast
import json
import os
import sys
import warnings
from collections import defaultdict
from typing import Dict, List, Optional

import joblib
import numpy as np

sys.path.append(os.path.dirname(__file__))

try:
    from llm_pipeline import deepseek_analysis, generate_xai_explanation, should_use_deepseek
except ImportError:
    deepseek_analysis = None
    generate_xai_explanation = None
    should_use_deepseek = None

DATABASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "database"))
if DATABASE_DIR not in sys.path:
    sys.path.append(DATABASE_DIR)

try:
    from db import (
        DB_PATH,
        initialize_database,
        insert_analysis_session,
        insert_code_entity,
        insert_feature_vector,
        insert_xai_explanation,
    )
except ImportError:
    DB_PATH = None
    initialize_database = None
    insert_analysis_session = None
    insert_code_entity = None
    insert_feature_vector = None
    insert_xai_explanation = None


class CallVisitor(ast.NodeVisitor):
    def __init__(self):
        self.calls: List[str] = []

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            self.calls.append(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            self.calls.append(node.func.attr)
        self.generic_visit(node)


class ExplainableReasoner:
    @staticmethod
    def generate(features: dict, confidence: float) -> dict:
        reasons_dead = []
        reasons_alive = []
        explanation_parts = []

        call_count = features["call_count"]
        is_exported = features["is_exported"]
        used_in_tests = features["used_in_tests"]
        dynamic_call_risk = features["dynamic_call_risk"]
        cyclomatic_complexity = features["cyclomatic_complexity"]
        file_depth = features["file_depth"]
        name = features["function_name"]

        if call_count == 0:
            reasons_dead.append("Never called within the analyzed scope (0 references found)")
            explanation_parts.append(f"'{name}' has zero call references in the codebase")
        elif call_count == 1:
            reasons_dead.append("Only called 1 time - possibly a self-reference or single-use")
            explanation_parts.append(f"'{name}' has only 1 call reference")
        else:
            reasons_alive.append(f"Called {call_count} times within the codebase - actively referenced")
            explanation_parts.append(f"'{name}' is referenced {call_count} times")

        if is_exported == 0:
            reasons_dead.append("Not exported (private/underscore-prefixed) - only visible locally")
            explanation_parts.append("Function is private (starts with '_')")
        else:
            reasons_alive.append("Exported (public) - accessible to external modules and imports")
            explanation_parts.append("Function is public and importable")

        if used_in_tests == 0:
            reasons_dead.append("No test coverage found - not referenced in any test files")
            explanation_parts.append("No test files reference this function")
        else:
            reasons_alive.append("Referenced in test files - actively tested code")
            explanation_parts.append("Function is covered by tests")

        if dynamic_call_risk == 1:
            reasons_alive.append("Uses dynamic invocation patterns (eval/exec/getattr) - may be called indirectly")
            explanation_parts.append("Dynamic invocation patterns detected - unsafe to remove automatically")
        elif call_count == 0:
            reasons_dead.append("No dynamic invocation risk - removal is safer")

        if cyclomatic_complexity <= 2:
            reasons_dead.append(
                f"Low cyclomatic complexity ({cyclomatic_complexity}) - likely a stub or simple wrapper"
            )
            explanation_parts.append(f"Simple logic (complexity: {cyclomatic_complexity})")
        elif cyclomatic_complexity >= 8:
            reasons_alive.append(
                f"High cyclomatic complexity ({cyclomatic_complexity}) - contains significant business logic"
            )
            explanation_parts.append(f"Complex logic (complexity: {cyclomatic_complexity})")
        else:
            explanation_parts.append(f"Moderate complexity ({cyclomatic_complexity})")

        if file_depth > 5:
            reasons_dead.append(
                f"Located deep in the directory tree (depth {file_depth}) - possibly orphaned in a legacy module"
            )
        elif file_depth <= 2:
            reasons_alive.append(f"Located at a shallow directory level (depth {file_depth}) - likely a core module")

        lower_name = name.lower()
        deprecated_markers = ["old", "unused", "deprecated", "legacy", "temp", "todo", "backup", "bak"]
        for marker in deprecated_markers:
            if marker in lower_name:
                reasons_dead.append(f"Name contains '{marker}' - suggests deprecated or temporary code")
                break

        if lower_name.startswith("_") and not lower_name.startswith("__"):
            reasons_dead.append("Single-underscore prefix convention indicates internal/private use only")

        if confidence >= 0.75:
            severity = "danger"
        elif confidence >= 0.55:
            severity = "warning"
        elif confidence >= 0.35:
            severity = "review"
        else:
            severity = "safe"

        pct = int(confidence * 100)
        if severity == "danger":
            summary = f"'{name}' is {pct}% likely dead - strong unused-code signals detected."
        elif severity == "warning":
            summary = f"'{name}' shows strong dead code signals ({pct}%) - verify before removing."
        elif severity == "review":
            summary = f"'{name}' has ambiguous signals ({pct}%) - manual review recommended."
        else:
            summary = f"'{name}' appears active ({pct}% dead confidence) - no action needed."

        full_explanation = "; ".join(explanation_parts) + f". Overall dead code confidence: {pct}%."

        feature_labels = {
            "call_count": "Call Frequency",
            "is_exported": "Export Visibility",
            "used_in_tests": "Test Coverage",
            "dynamic_call_risk": "Dynamic Invocation Risk",
            "cyclomatic_complexity": "Cyclomatic Complexity",
            "file_depth": "File Depth",
        }

        return {
            "reasons_dead": reasons_dead,
            "reasons_alive": reasons_alive,
            "severity": severity,
            "summary": summary,
            "explanation": full_explanation,
            "feature_labels": feature_labels,
        }


class CodeAnalyzer:
    def __init__(self, file_path: str, project_root: Optional[str] = None):
        self.file_path = os.path.abspath(file_path)
        self.project_root = os.path.abspath(project_root or os.path.dirname(file_path))
        self.call_graph = defaultdict(int)
        self.test_usage = set()

    def scan_test_usage(self):
        test_patterns = ["test_", "_test", "tests", "spec"]
        for root, _, files in os.walk(self.project_root):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                is_test_file = any(p in fname.lower() for p in test_patterns) or any(
                    p in root.lower() for p in test_patterns
                )
                if not is_test_file:
                    continue
                try:
                    fpath = os.path.join(root, fname)
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as handle:
                        tree = ast.parse(handle.read())
                    visitor = CallVisitor()
                    visitor.visit(tree)
                    for call in visitor.calls:
                        self.test_usage.add(call)
                except Exception:
                    continue

    def scan_cross_file_calls(self):
        for root, _, files in os.walk(self.project_root):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as handle:
                        tree = ast.parse(handle.read())
                    visitor = CallVisitor()
                    visitor.visit(tree)
                    for call in visitor.calls:
                        self.call_graph[call] += 1
                except Exception:
                    continue

    def analyze(self):
        try:
            with open(self.file_path, "r", encoding="utf-8") as handle:
                source = handle.read()
            tree = ast.parse(source)
        except Exception as exc:
            print(json.dumps({"error": f"Failed to parse file: {exc}"}))
            sys.exit(1)

        if not self.call_graph:
            visitor = CallVisitor()
            visitor.visit(tree)
            for call in visitor.calls:
                self.call_graph[call] += 1

        results = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                features = self.extract_features(node, source)
                if features:
                    results.append(features)
            elif isinstance(node, ast.ClassDef):
                features = self.extract_class_features(node, source)
                if features:
                    results.append(features)
        return results

    def compute_complexity(self, node):
        complexity = 1
        for child in ast.walk(node):
            if isinstance(
                child,
                (
                    ast.If,
                    ast.For,
                    ast.While,
                    ast.And,
                    ast.Or,
                    ast.ExceptHandler,
                    ast.With,
                    ast.Assert,
                    ast.ListComp,
                    ast.SetComp,
                    ast.DictComp,
                    ast.GeneratorExp,
                ),
            ):
                complexity += 1
        return complexity

    def dynamic_call_check(self, node):
        dynamic_patterns = {"eval", "exec", "getattr", "setattr", "globals", "locals", "__import__", "importlib"}
        for child in ast.walk(node):
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
                if child.func.id in dynamic_patterns:
                    return 1
        return 0

    def _relative_file_depth(self) -> int:
        try:
            rel_path = os.path.relpath(self.file_path, self.project_root).replace("\\", "/")
        except ValueError:
            rel_path = self.file_path.replace("\\", "/")
        return rel_path.count("/")

    def extract_features(self, node, source):
        name = node.name
        call_count = self.call_graph.get(name, 0)
        is_exported = int(not name.startswith("_"))
        used_in_tests = int(name in self.test_usage)
        dynamic_call_risk = self.dynamic_call_check(node)
        cyclomatic_complexity = self.compute_complexity(node)
        file_depth = self._relative_file_depth()
        start_line = node.lineno
        end_line = getattr(node, "end_lineno", start_line)
        snippet = ast.get_source_segment(source, node) or ""
        if len(snippet) > 500:
            snippet = snippet[:500] + "..."

        return {
            "function_name": name,
            "entity_type": "function",
            "call_count": call_count,
            "is_exported": is_exported,
            "used_in_tests": used_in_tests,
            "dynamic_call_risk": dynamic_call_risk,
            "cyclomatic_complexity": cyclomatic_complexity,
            "file_depth": file_depth,
            "start_line": start_line,
            "end_line": end_line,
            "snippet": snippet,
        }

    def extract_class_features(self, node, source):
        name = node.name
        call_count = self.call_graph.get(name, 0)
        is_exported = int(not name.startswith("_"))
        used_in_tests = int(name in self.test_usage)
        dynamic_call_risk = 0
        method_count = sum(1 for child in ast.walk(node) if isinstance(child, ast.FunctionDef))
        cyclomatic_complexity = max(1, method_count)
        file_depth = self._relative_file_depth()
        start_line = node.lineno
        end_line = getattr(node, "end_lineno", start_line)
        lines = source.split("\n")
        snippet = lines[start_line - 1].strip() if start_line <= len(lines) else ""

        return {
            "function_name": name,
            "entity_type": "class",
            "call_count": call_count,
            "is_exported": is_exported,
            "used_in_tests": used_in_tests,
            "dynamic_call_risk": dynamic_call_risk,
            "cyclomatic_complexity": cyclomatic_complexity,
            "file_depth": file_depth,
            "start_line": start_line,
            "end_line": end_line,
            "snippet": snippet,
        }


def parse_arguments(argv: List[str]) -> Dict[str, Optional[str]]:
    if len(argv) < 2:
        print(json.dumps({"error": "No file provided"}))
        sys.exit(1)

    options: Dict[str, Optional[str]] = {
        "file_path": argv[1],
        "project_root": None,
        "db_path": None,
        "store_db": False,
    }

    index = 2
    while index < len(argv):
        arg = argv[index]
        if arg == "--project-root" and index + 1 < len(argv):
            options["project_root"] = argv[index + 1]
            index += 2
        elif arg == "--db-path" and index + 1 < len(argv):
            options["db_path"] = argv[index + 1]
            index += 2
        elif arg == "--store-db":
            options["store_db"] = True
            index += 1
        else:
            index += 1

    return options


def count_python_files(project_root: str) -> int:
    total = 0
    for root, _, files in os.walk(project_root):
        for fname in files:
            if fname.endswith(".py"):
                total += 1
    return total


def persist_results(project_root: str, file_path: str, results: List[Dict], db_path: Optional[str]) -> Optional[int]:
    if not all(
        [initialize_database, insert_analysis_session, insert_code_entity, insert_feature_vector, insert_xai_explanation]
    ):
        return None

    resolved_db_path = db_path or os.getenv("DCC_DB_PATH") or DB_PATH
    initialize_database(resolved_db_path)
    session_id = insert_analysis_session(project_root, count_python_files(project_root), resolved_db_path)

    for result in results:
        entity_id = insert_code_entity(
            session_id,
            file_path,
            result["function_name"],
            result.get("entity_type", "function"),
            result["start_line"],
            result["end_line"],
            result["confidence"],
            resolved_db_path,
        )
        features = result.get("features", {})
        insert_feature_vector(
            entity_id,
            int(features.get("call_count", 0)),
            int(features.get("is_exported", 0)),
            int(features.get("used_in_tests", 0)),
            float(features.get("dynamic_call_risk", 0)),
            int(features.get("cyclomatic_complexity", 0)),
            int(features.get("file_depth", 0)),
            resolved_db_path,
        )
        xai_payload = result.get("xai_explanation") or {"summary": result.get("explanation", "")}
        insert_xai_explanation(entity_id, xai_payload, resolved_db_path)

    return session_id


def main():
    options = parse_arguments(sys.argv)
    file_path = os.path.abspath(str(options["file_path"]))
    project_root = os.path.abspath(str(options["project_root"] or os.path.dirname(file_path)))
    cross_file = bool(options["project_root"])

    script_dir = os.path.dirname(os.path.abspath(__file__))
    ml_dir = os.path.join(script_dir, "..", "ML Part")
    model_path = os.path.join(ml_dir, "dead_code_model.pkl")
    scaler_path = os.path.join(ml_dir, "scaler.pkl")

    warnings.filterwarnings("ignore", category=UserWarning, module="sklearn")
    warnings.filterwarnings("ignore", category=FutureWarning, module="sklearn")

    try:
        model = joblib.load(model_path)
        scaler = joblib.load(scaler_path)
    except Exception as exc:
        print(json.dumps({"error": f"Failed to load ML model: {exc}"}))
        sys.exit(1)

    analyzer = CodeAnalyzer(file_path, project_root)
    if cross_file:
        analyzer.scan_cross_file_calls()
        analyzer.scan_test_usage()

    features_list = analyzer.analyze()
    results = []
    reasoner = ExplainableReasoner()

    for features in features_list:
        X = np.array(
            [[
                features["call_count"],
                features["is_exported"],
                features["used_in_tests"],
                features["dynamic_call_risk"],
                features["cyclomatic_complexity"],
                features["file_depth"],
            ]]
        )
        X_scaled = scaler.transform(X)
        confidence = float(model.predict_proba(X_scaled)[0][1])

        explanations = reasoner.generate(features, confidence)
        top_features = []
        feature_keys = [
            "call_count",
            "is_exported",
            "used_in_tests",
            "dynamic_call_risk",
            "cyclomatic_complexity",
            "file_depth",
        ]

        try:
            coefficients = model.coef_[0]
            scaled_values = X_scaled[0]
            for idx, key in enumerate(feature_keys):
                contribution = float(coefficients[idx] * scaled_values[idx])
                top_features.append(
                    {
                        "name": key,
                        "label": explanations["feature_labels"].get(key, key),
                        "value": float(features[key]),
                        "contribution": round(contribution, 4),
                        "direction": "dead" if contribution > 0 else "live",
                    }
                )
            top_features.sort(key=lambda item: abs(item["contribution"]), reverse=True)
        except Exception:
            pass

        if generate_xai_explanation:
            use_deepseek = bool(deepseek_analysis and should_use_deepseek and should_use_deepseek())
            if use_deepseek:
                try:
                    deepseek_out = deepseek_analysis(features.get("snippet", ""), features)
                except Exception as exc:
                    deepseek_out = {"is_unused": None, "reasoning": f"DeepSeek error: {exc}", "key_observations": []}
            else:
                deepseek_out = {
                    "is_unused": None,
                    "reasoning": "DeepSeek disabled for the current provider configuration.",
                    "key_observations": [],
                }

            try:
                lr_output = {"is_dead": confidence > 0.5, "confidence": confidence}
                entity_info = {"name": features["function_name"], "type": features.get("entity_type", "function")}
                xai_explanation = generate_xai_explanation(entity_info, features, lr_output, deepseek_out)
            except Exception as exc:
                xai_explanation = {
                    "summary": f"LLM provider error: {exc}",
                    "risk_level": "Medium",
                    "confidence": confidence,
                    "confidence_explanation": "ML-only confidence.",
                    "factors": [],
                    "llm_reasoning": "",
                    "recommendation": "Review manually.",
                    "action": "review",
                }
        else:
            deepseek_out = {"is_unused": None, "reasoning": "LLM pipeline unavailable", "key_observations": []}
            xai_explanation = {
                "summary": "LLM pipeline unavailable",
                "risk_level": "Medium",
                "confidence": confidence,
                "confidence_explanation": "ML-only confidence.",
                "factors": [],
                "llm_reasoning": "",
                "recommendation": "Review manually.",
                "action": "review",
            }

        results.append(
            {
                "function_name": features["function_name"],
                "entity_type": features.get("entity_type", "function"),
                "confidence": round(confidence, 4),
                "severity": explanations["severity"],
                "reasons_dead": explanations["reasons_dead"],
                "reasons_alive": explanations["reasons_alive"],
                "summary": explanations["summary"],
                "explanation": explanations["explanation"],
                "top_features": top_features,
                "features": {
                    "call_count": features["call_count"],
                    "is_exported": features["is_exported"],
                    "used_in_tests": features["used_in_tests"],
                    "dynamic_call_risk": features["dynamic_call_risk"],
                    "cyclomatic_complexity": features["cyclomatic_complexity"],
                    "file_depth": features["file_depth"],
                },
                "start_line": features["start_line"],
                "end_line": features["end_line"],
                "snippet": features["snippet"],
                "deepseek_analysis": deepseek_out,
                "xai_explanation": xai_explanation,
            }
        )

    if options["store_db"]:
        session_id = persist_results(project_root, file_path, results, options["db_path"])
        output = {"session_id": session_id, "results": results}
    else:
        output = results

    print(json.dumps(output))


if __name__ == "__main__":
    main()
