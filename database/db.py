import json
import os
import sqlite3
from typing import Any, Dict, List, Optional

DB_PATH = os.path.abspath(
    os.getenv(
        "DCC_DB_PATH",
        os.path.join(os.path.dirname(__file__), "..", "dcc", "dcc_analysis.db"),
    )
)


def get_connection(db_path: str = DB_PATH):
    return sqlite3.connect(db_path)


def initialize_database(db_path: str = DB_PATH):
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS analysis_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_path TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            total_files INTEGER
        );
        CREATE TABLE IF NOT EXISTS code_entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            file_name TEXT,
            entity_name TEXT,
            entity_type TEXT,
            start_line INTEGER,
            end_line INTEGER,
            confidence_score REAL,
            FOREIGN KEY(session_id) REFERENCES analysis_sessions(id)
        );
        CREATE TABLE IF NOT EXISTS feature_vectors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_id INTEGER,
            call_count INTEGER,
            is_exported INTEGER,
            used_in_tests INTEGER,
            dynamic_call_risk REAL,
            cyclomatic_complexity INTEGER,
            file_depth INTEGER,
            FOREIGN KEY(entity_id) REFERENCES code_entities(id)
        );
        CREATE TABLE IF NOT EXISTS explanations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_id INTEGER,
            summary TEXT,
            risk_level TEXT,
            confidence_explanation TEXT,
            llm_reasoning TEXT,
            recommendation TEXT,
            action TEXT,
            xai_json TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(entity_id) REFERENCES code_entities(id)
        );
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT,
            response TEXT,
            context_file TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS removal_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_id INTEGER,
            file_name TEXT,
            removed_code TEXT,
            confidence_score REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(entity_id) REFERENCES code_entities(id)
        );
        """
    )
    conn.commit()
    conn.close()


def insert_analysis_session(project_path: str, total_files: int, db_path: str = DB_PATH) -> int:
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO analysis_sessions (project_path, total_files) VALUES (?, ?)
        """,
        (project_path, total_files),
    )
    session_id = cur.lastrowid
    conn.commit()
    conn.close()
    return session_id


def insert_code_entity(
    session_id: int,
    file_name: str,
    entity_name: str,
    entity_type: str,
    start_line: int,
    end_line: int,
    confidence_score: float,
    db_path: str = DB_PATH,
) -> int:
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO code_entities (
            session_id, file_name, entity_name, entity_type,
            start_line, end_line, confidence_score
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (session_id, file_name, entity_name, entity_type, start_line, end_line, confidence_score),
    )
    entity_id = cur.lastrowid
    conn.commit()
    conn.close()
    return entity_id


def insert_feature_vector(
    entity_id: int,
    call_count: int,
    is_exported: int,
    used_in_tests: int,
    dynamic_call_risk: float,
    cyclomatic_complexity: int,
    file_depth: int,
    db_path: str = DB_PATH,
) -> int:
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO feature_vectors (
            entity_id, call_count, is_exported, used_in_tests,
            dynamic_call_risk, cyclomatic_complexity, file_depth
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            entity_id,
            call_count,
            is_exported,
            used_in_tests,
            dynamic_call_risk,
            cyclomatic_complexity,
            file_depth,
        ),
    )
    feature_id = cur.lastrowid
    conn.commit()
    conn.close()
    return feature_id


def insert_xai_explanation(entity_id: int, xai: dict, db_path: str = DB_PATH) -> int:
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO explanations (
            entity_id, summary, risk_level, confidence_explanation,
            llm_reasoning, recommendation, action, xai_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            entity_id,
            xai.get("summary", ""),
            xai.get("risk_level", ""),
            xai.get("confidence_explanation", ""),
            xai.get("llm_reasoning", ""),
            xai.get("recommendation", ""),
            xai.get("action", ""),
            json.dumps(xai),
        ),
    )
    explanation_id = cur.lastrowid
    conn.commit()
    conn.close()
    return explanation_id


def insert_explanation(entity_id: int, explanation_text: str, db_path: str = DB_PATH) -> int:
    return insert_xai_explanation(
        entity_id,
        {
            "summary": explanation_text,
            "risk_level": "",
            "confidence_explanation": "",
            "llm_reasoning": "",
            "recommendation": "",
            "action": "",
        },
        db_path,
    )


def log_chat_query(
    query: str,
    response: str,
    context_file: Optional[str] = None,
    db_path: str = DB_PATH,
) -> int:
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO chat_history (query, response, context_file) VALUES (?, ?, ?)
        """,
        (query, response, context_file),
    )
    chat_id = cur.lastrowid
    conn.commit()
    conn.close()
    return chat_id


def insert_removal_log(
    entity_id: int,
    file_name: str,
    removed_code: str,
    confidence_score: float,
    db_path: str = DB_PATH,
) -> int:
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO removal_logs (entity_id, file_name, removed_code, confidence_score)
        VALUES (?, ?, ?, ?)
        """,
        (entity_id, file_name, removed_code, confidence_score),
    )
    removal_id = cur.lastrowid
    conn.commit()
    conn.close()
    return removal_id


def fetch_past_analysis(project_path: str, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    conn = get_connection(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM analysis_sessions
        WHERE project_path = ?
        ORDER BY timestamp DESC LIMIT 20
        """,
        (project_path,),
    )
    sessions = [dict(row) for row in cur.fetchall()]
    conn.close()
    return sessions


def fetch_entities_for_session(session_id: int, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    conn = get_connection(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            ce.*,
            e.summary AS explanation_summary,
            e.risk_level,
            e.confidence_explanation,
            e.llm_reasoning,
            e.recommendation,
            e.action,
            e.xai_json,
            fv.call_count,
            fv.is_exported,
            fv.used_in_tests,
            fv.dynamic_call_risk,
            fv.cyclomatic_complexity,
            fv.file_depth
        FROM code_entities ce
        LEFT JOIN explanations e ON e.entity_id = ce.id
        LEFT JOIN feature_vectors fv ON fv.entity_id = ce.id
        WHERE ce.session_id = ?
        ORDER BY ce.confidence_score DESC
        """,
        (session_id,),
    )
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()

    for row in rows:
        xai_json = row.get("xai_json")
        if xai_json:
            try:
                row["xai_explanation"] = json.loads(xai_json)
            except json.JSONDecodeError:
                row["xai_explanation"] = None
        else:
            row["xai_explanation"] = None
    return rows


def fetch_removal_logs(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    conn = get_connection(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM removal_logs ORDER BY timestamp DESC LIMIT 50
        """
    )
    logs = [dict(row) for row in cur.fetchall()]
    conn.close()
    return logs


def fetch_chat_history(limit: int = 50, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    conn = get_connection(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM chat_history ORDER BY timestamp DESC LIMIT ?
        """,
        (limit,),
    )
    chats = [dict(row) for row in cur.fetchall()]
    conn.close()
    return chats


def fetch_analysis_summary(project_path: str, db_path: str = DB_PATH) -> Dict[str, Any]:
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT COUNT(*) as total_sessions
        FROM analysis_sessions
        WHERE project_path = ?
        """,
        (project_path,),
    )
    total_sessions = cur.fetchone()[0]

    cur.execute(
        """
        SELECT COUNT(*) as total_entities,
               AVG(confidence_score) as avg_confidence,
               SUM(CASE WHEN confidence_score >= 0.75 THEN 1 ELSE 0 END) as danger_count,
               SUM(CASE WHEN confidence_score >= 0.55 AND confidence_score < 0.75 THEN 1 ELSE 0 END) as warning_count,
               SUM(CASE WHEN confidence_score >= 0.35 AND confidence_score < 0.55 THEN 1 ELSE 0 END) as review_count,
               SUM(CASE WHEN confidence_score < 0.35 THEN 1 ELSE 0 END) as safe_count
        FROM code_entities ce
        JOIN analysis_sessions a ON a.id = ce.session_id
        WHERE a.project_path = ?
        """,
        (project_path,),
    )
    row = cur.fetchone()
    conn.close()

    return {
        "total_sessions": total_sessions,
        "total_entities": row[0] or 0,
        "avg_confidence": round(row[1] or 0, 4),
        "danger_count": row[2] or 0,
        "warning_count": row[3] or 0,
        "review_count": row[4] or 0,
        "safe_count": row[5] or 0,
    }


if __name__ == "__main__":
    import sys

    def print_and_exit(msg):
        print(msg)
        sys.exit(0)

    if len(sys.argv) == 1:
        initialize_database()
        print("Database initialized.")

    elif sys.argv[1] == "init":
        initialize_database()
        print("Database initialized.")

    elif sys.argv[1] == "insert_analysis_session":
        session_id = insert_analysis_session(sys.argv[2], int(sys.argv[3]))
        print_and_exit(str(session_id))

    elif sys.argv[1] == "insert_code_entity":
        entity_id = insert_code_entity(
            int(sys.argv[2]),
            sys.argv[3],
            sys.argv[4],
            sys.argv[5],
            int(sys.argv[6]),
            int(sys.argv[7]),
            float(sys.argv[8]),
        )
        print_and_exit(str(entity_id))

    elif sys.argv[1] == "insert_feature_vector":
        feature_id = insert_feature_vector(
            int(sys.argv[2]),
            int(sys.argv[3]),
            int(sys.argv[4]),
            int(sys.argv[5]),
            float(sys.argv[6]),
            int(sys.argv[7]),
            int(sys.argv[8]),
        )
        print_and_exit(str(feature_id))

    elif sys.argv[1] == "insert_explanation":
        explanation_id = insert_explanation(int(sys.argv[2]), sys.argv[3])
        print_and_exit(str(explanation_id))

    elif sys.argv[1] == "insert_xai_explanation":
        explanation_id = insert_xai_explanation(int(sys.argv[2]), json.loads(sys.argv[3]))
        print_and_exit(str(explanation_id))

    elif sys.argv[1] == "log_chat":
        context_file = sys.argv[4] if len(sys.argv) > 4 else None
        chat_id = log_chat_query(sys.argv[2], sys.argv[3], context_file)
        print_and_exit(str(chat_id))

    elif sys.argv[1] == "insert_removal_log":
        removal_id = insert_removal_log(
            int(sys.argv[2]),
            sys.argv[3],
            sys.argv[4],
            float(sys.argv[5]),
        )
        print_and_exit(str(removal_id))

    elif sys.argv[1] == "fetch_past_analysis":
        print_and_exit(json.dumps(fetch_past_analysis(sys.argv[2])))

    elif sys.argv[1] == "fetch_entities_for_session":
        print_and_exit(json.dumps(fetch_entities_for_session(int(sys.argv[2]))))

    elif sys.argv[1] == "fetch_removal_logs":
        print_and_exit(json.dumps(fetch_removal_logs()))

    elif sys.argv[1] == "fetch_chat_history":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 50
        print_and_exit(json.dumps(fetch_chat_history(limit)))

    elif sys.argv[1] == "fetch_analysis_summary":
        print_and_exit(json.dumps(fetch_analysis_summary(sys.argv[2])))

    else:
        print("Unknown command: " + sys.argv[1])
        sys.exit(1)
