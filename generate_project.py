import os
from pathlib import Path

project_files = {
    "dataprep_magic_project/README.md": """# Dataprep Magic

A mock ETL (Extract, Transform, Load) library used for testing static analysis tools.
This project contains deliberate code smells, dead code, dynamic evaluations, and complex functions.

## Features
* **Extract**: API clients with dynamic method calls and CSV chunk reading.
* **Transform**: Data cleaning with high cyclomatic complexity and `eval()` usage.
* **Load**: Mock database writers.
""",
    
    "dataprep_magic_project/requirements.txt": """requests==2.31.0
pytest==7.4.3
""",

    "dataprep_magic_project/dataprep_magic/__init__.py": """\"\"\"
Dataprep Magic ETL Library.
\"\"\"
from .pipeline import run_pipeline

__all__ = ["run_pipeline"]
""",

    "dataprep_magic_project/dataprep_magic/pipeline.py": """\"\"\"
Main pipeline runner. Coordinates extract, transform, and load.
\"\"\"
from .extract.csv_reader import read_csv
from .transform.cleaners import process_records
from .load.db_writer import write_to_postgres

def run_pipeline(filepath: str, db_uri: str):
    \"\"\"
    Executes the standard ETL pipeline.
    \"\"\"
    print(f"Starting pipeline for {filepath}")
    raw_data = read_csv(filepath)
    clean_data = process_records(raw_data)
    success = write_to_postgres(clean_data, db_uri)
    return success

# DEAD CODE: This alternative runner is never exported or used anywhere.
def _run_legacy_pipeline(filepath: str):
    \"\"\"Legacy pipeline, currently unreferenced.\"\"\"
    pass
""",

    "dataprep_magic_project/dataprep_magic/extract/__init__.py": """# Empty init""",

    "dataprep_magic_project/dataprep_magic/extract/api_client.py": """\"\"\"
API Client for fetching remote datasets.
Demonstrates decorators and dynamic getattr calls.
\"\"\"
import time
import requests

def retry_request(max_retries=3):
    \"\"\"Decorator to retry flaky API calls.\"\"\"
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise e
                    time.sleep(1)
        return wrapper
    return decorator

class HTTPClient:
    def __init__(self, base_url):
        self.base_url = base_url

    @retry_request(max_retries=2)
    def fetch_data(self, endpoint, method="GET", payload=None):
        \"\"\"
        Fetches data using a dynamic requests method call.
        Static analyzers might struggle to track which HTTP methods are actually used.
        \"\"\"
        url = f"{self.base_url}/{endpoint}"
        
        # DYNAMIC CALL: Uses getattr to dynamically call requests.get, requests.post, etc.
        request_func = getattr(requests, method.lower())
        
        if method.upper() in ["POST", "PUT"]:
            response = request_func(url, json=payload)
        else:
            response = request_func(url)
            
        return response.json()

# DEAD CODE: Function is defined but never referenced in the project.
def build_auth_headers(token):
    return {"Authorization": f"Bearer {token}"}
""",

    "dataprep_magic_project/dataprep_magic/extract/csv_reader.py": """\"\"\"
CSV extraction utilities.
\"\"\"

def read_csv(filepath: str) -> list:
    \"\"\"Reads a CSV file into a list of dictionaries.\"\"\"
    # Mocking a CSV read operation
    return [
        {"id": "1", "value": "100", "status": "ACTIVE"},
        {"id": "2", "value": "BAD_DATA", "status": "pending"},
        {"id": "3", "value": "300", "status": "CLOSED"}
    ]

# DEAD CODE: Unused extraction format
def read_excel(filepath: str) -> list:
    \"\"\"Reads an Excel file. This function is totally orphaned.\"\"\"
    raise NotImplementedError("Excel reading not implemented")
""",

    "dataprep_magic_project/dataprep_magic/transform/__init__.py": """# Empty init""",

    "dataprep_magic_project/dataprep_magic/transform/utils.py": """\"\"\"
Internal utility functions for transformations.
\"\"\"

def _sanitize_string(val: str) -> str:
    \"\"\"Internal helper to clean strings.\"\"\"
    return val.strip().upper()

def _is_null(val) -> bool:
    \"\"\"Checks for various null equivalents.\"\"\"
    return val in (None, "", "NULL", "N/A")

# DEAD CODE: Internal helper never called by cleaners.py or aggregators.py
def _format_date(val: str) -> str:
    return val.replace("/", "-")
""",

    "dataprep_magic_project/dataprep_magic/transform/cleaners.py": """\"\"\"
Data cleaning logic.
Demonstrates high cyclomatic complexity and unsafe evaluations.
\"\"\"
from .utils import _sanitize_string, _is_null

def complex_cleaner(record: dict) -> dict:
    \"\"\"
    Cleans a single record.
    High cyclomatic complexity testbed for static analysis.
    \"\"\"
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
    \"\"\"
    Evaluates a dynamic math formula.
    DYNAMIC CALL: Uses eval(). Analyzers should flag this as a security/dynamic risk.
    \"\"\"
    try:
        # Intentionally dangerous code pattern
        return eval(formula_str, {"__builtins__": None}, safe_context)
    except Exception:
        return None

def process_records(records: list) -> list:
    \"\"\"Processes a batch of records.\"\"\"
    return [complex_cleaner(r) for r in records]
""",

    "dataprep_magic_project/dataprep_magic/transform/aggregators.py": """\"\"\"
Aggregation module.
Mostly contains dead code to test tree-shaking capabilities.
\"\"\"

class GroupAggregator:
    \"\"\"Aggregates data. Exported but never imported or instantiated.\"\"\"
    def __init__(self, group_by_col):
        self.group_by = group_by_col
        
    def sum_column(self, data, col):
        # Implementation missing
        pass

# DEAD CODE
def average_records(records, col):
    \"\"\"Calculates average. Never used.\"\"\"
    vals = [r[col] for r in records if col in r and isinstance(r[col], (int, float))]
    return sum(vals) / len(vals) if vals else 0
""",

    "dataprep_magic_project/dataprep_magic/load/__init__.py": """# Empty init""",

    "dataprep_magic_project/dataprep_magic/load/db_writer.py": """\"\"\"
Mock database writing logic.
\"\"\"

def write_to_postgres(data: list, uri: str) -> bool:
    \"\"\"Simulates writing to a postgres database.\"\"\"
    if not data:
        return False
    query = _build_insert_query("target_table", data[0].keys())
    print(f"Executing: {query} to {uri} for {len(data)} rows")
    return True

def _build_insert_query(table: str, columns: list) -> str:
    \"\"\"Internal helper to construct a SQL query.\"\"\"
    cols = ", ".join(columns)
    vals = ", ".join(["%s"] * len(columns))
    return f"INSERT INTO {table} ({cols}) VALUES ({vals})"

# DEAD CODE: Exported but entirely unused.
def write_to_mongodb(data: list, uri: str):
    \"\"\"Simulates writing to Mongo. Unreferenced.\"\"\"
    print(f"Connecting to NoSQL: {uri}")
    return True
""",

    "dataprep_magic_project/tests/__init__.py": """# Empty init""",

    "dataprep_magic_project/tests/test_extract.py": """\"\"\"
Tests for extraction logic.
\"\"\"
from dataprep_magic.extract.csv_reader import read_csv
from dataprep_magic.extract.api_client import HTTPClient

def test_read_csv():
    data = read_csv("dummy_path.csv")
    assert len(data) == 3
    assert data[0]["id"] == "1"

# Note: HTTPClient.fetch_data is hard to test purely because of dynamic requests call without mocking,
# but we instantiate it to ensure the code is "used" from the perspective of an AST analyzer.
def test_api_client_init():
    client = HTTPClient("http://example.com")
    assert client.base_url == "http://example.com"
""",

    "dataprep_magic_project/tests/test_transform.py": """\"\"\"
Tests for transformation logic.
\"\"\"
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
"""
}

def create_project():
    print("Generating dataprep_magic_project...")
    for filepath, content in project_files.items():
        path = Path(filepath)
        # Create directories if they don't exist
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write the file
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Created: {filepath}")
    print("\nProject generation complete! You can now navigate to the 'dataprep_magic_project' folder.")

if __name__ == "__main__":
    create_project()