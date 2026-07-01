"""
CSV extraction utilities.
"""

def read_csv(filepath: str) -> list:
    """Reads a CSV file into a list of dictionaries."""
    # Mocking a CSV read operation
    return [
        {"id": "1", "value": "100", "status": "ACTIVE"},
        {"id": "2", "value": "BAD_DATA", "status": "pending"},
        {"id": "3", "value": "300", "status": "CLOSED"}
    ]

# DEAD CODE: Unused extraction format
def read_excel(filepath: str) -> list:
    """Reads an Excel file. This function is totally orphaned."""
    raise NotImplementedError("Excel reading not implemented")
