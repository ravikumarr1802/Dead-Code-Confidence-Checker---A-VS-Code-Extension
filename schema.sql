-- =========================================
-- DEAD CODE CONFIDENCE CHECKER DATABASE
-- =========================================

-- 1️⃣ Analysis Sessions
CREATE TABLE analysis_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_path TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    total_files INTEGER
);

-- 2️⃣ Code Entities (functions/classes/variables)
CREATE TABLE code_entities (
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

-- 3️⃣ Feature Vectors (ML Inputs)
CREATE TABLE feature_vectors (
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

-- 4️⃣ Explanations
CREATE TABLE explanations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id INTEGER,
    explanation_text TEXT,

    FOREIGN KEY(entity_id) REFERENCES code_entities(id)
);

-- 5️⃣ Chat History (Copilot-like)
CREATE TABLE chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT,
    response TEXT,
    context_file TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 6️⃣ Dead Code Removal Logs
CREATE TABLE removal_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id INTEGER,
    file_name TEXT,
    removed_code TEXT,
    confidence_score REAL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(entity_id) REFERENCES code_entities(id)
);