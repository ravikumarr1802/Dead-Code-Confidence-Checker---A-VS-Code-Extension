"""
Tests for transformation logic.
"""
from dataprep_magic.transform.cleaners import complex_cleaner, evaluate_formula

def test_complex_cleaner():
    raw_record = {"id": "5", "value": "500", "status": " pending "}
    cleaned = complex_cleaner(raw_record)
    
    assert cleaned["id"] == "5"
    assert cleaned["value"] == 500
    assert cleaned["status"] == "PENDING"

def test_evaluate_formula():
    context = {"x": 10, "y": 5}
    result = evaluate_formula("x * y + 2", context)
    assert result == 52
