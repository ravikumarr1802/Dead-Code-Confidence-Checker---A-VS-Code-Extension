"""
Mock database writing logic.
"""

def write_to_postgres(data: list, uri: str) -> bool:
    """Simulates writing to a postgres database."""
    if not data:
        return False
    query = _build_insert_query("target_table", data[0].keys())
    print(f"Executing: {query} to {uri} for {len(data)} rows")
    return True

def _build_insert_query(table: str, columns: list) -> str:
    """Internal helper to construct a SQL query."""
    cols = ", ".join(columns)
    vals = ", ".join(["%s"] * len(columns))
    return f"INSERT INTO {table} ({cols}) VALUES ({vals})"

# DEAD CODE: Exported but entirely unused.
def write_to_mongodb(data: list, uri: str):
    """Simulates writing to Mongo. Unreferenced."""
    print(f"Connecting to NoSQL: {uri}")
    return True
