"""
Main pipeline runner. Coordinates extract, transform, and load.
"""
from .extract.csv_reader import read_csv
from .transform.cleaners import process_records
from .load.db_writer import write_to_postgres

def run_pipeline(filepath: str, db_uri: str):
    """
    Executes the standard ETL pipeline.
    """
    print(f"Starting pipeline for {filepath}")
    raw_data = read_csv(filepath)
    clean_data = process_records(raw_data)
    success = write_to_postgres(clean_data, db_uri)
    return success

# DEAD CODE: This alternative runner is never exported or used anywhere.
def _run_legacy_pipeline(filepath: str):
    """Legacy pipeline, currently unreferenced."""
    pass
