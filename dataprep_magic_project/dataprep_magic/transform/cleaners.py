"""
Data cleaning logic.
Demonstrates high cyclomatic complexity and unsafe evaluations.
"""
from .utils import _sanitize_string, _is_null

def complex_cleaner(record: dict) -> dict:
    """
    Cleans a single record.
    High cyclomatic complexity testbed for static analysis.
    """
    cleaned = {}
    for key, val in record.items():
        if _is_null(val):
            cleaned[key] = None
        elif key == "status":
            cleaned[key] = _sanitize_string(val)
        elif key == "value":
            if isinstance(val, str) and val.isdigit():
                cleaned[key] = int(val)
            elif isinstance(val, int):
                if val < 0:
                    cleaned[key] = 0
                elif val > 1000:
                    cleaned[key] = 1000
                else:
                    cleaned[key] = val
            else:
                cleaned[key] = -1 # default error code
        else:
            cleaned[key] = val
    return cleaned

def evaluate_formula(formula_str: str, safe_context: dict):
    """
    Evaluates a dynamic math formula.
    DYNAMIC CALL: Uses eval(). Analyzers should flag this as a security/dynamic risk.
    """
    try:
        # Intentionally dangerous code pattern
        return eval(formula_str, {"__builtins__": None}, safe_context)
    except Exception:
        return None

def process_records(records: list) -> list:
    """Processes a batch of records."""
    return [complex_cleaner(r) for r in records]
