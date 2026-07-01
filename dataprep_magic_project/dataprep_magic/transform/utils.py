"""
Internal utility functions for transformations.
"""

def _sanitize_string(val: str) -> str:
    """Internal helper to clean strings."""
    return val.strip().upper()

def _is_null(val) -> bool:
    """Checks for various null equivalents."""
    return val in (None, "", "NULL", "N/A")

# DEAD CODE: Internal helper never called by cleaners.py or aggregators.py
def _format_date(val: str) -> str:
    return val.replace("/", "-")
