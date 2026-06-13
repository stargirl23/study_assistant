import sqlite3
from config import DB_PATH

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript('''
       CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    user_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

        CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            topic_name TEXT,
            mastery_score REAL DEFAULT 0,
            attempts INTEGER DEFAULT 0,
            correct INTEGER DEFAULT 0,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        );

        CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER,
    question TEXT,
    user_answer TEXT,
    correct_answer TEXT,
    is_correct BOOLEAN,
    attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (topic_id) REFERENCES topics(id)
);

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER,
    chunk_index INTEGER,
    content TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);
    ''')

    conn.commit()
    conn.close()

# --- Session functions ---

def create_session(name, user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO sessions (name, user_id) VALUES (?, ?)", (name, user_id))
    conn.commit()
    session_id = cursor.lastrowid
    conn.close()
    return session_id

def get_all_sessions(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sessions WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# --- Topic functions ---

def insert_topics(session_id, topic_names):
    conn = get_connection()
    cursor = conn.cursor()
    for topic in topic_names:
        cursor.execute(
            "INSERT INTO topics (session_id, topic_name) VALUES (?, ?)",
            (session_id, topic)
        )
    conn.commit()
    conn.close()

def get_topics(session_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM topics WHERE session_id = ?", (session_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_weak_topics(session_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM topics WHERE session_id = ? AND mastery_score < ?",
        (session_id, 80.0)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def update_topic_mastery(topic_id, is_correct):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT attempts, correct FROM topics WHERE id = ?", (topic_id,))
    row = cursor.fetchone()

    new_attempts = row["attempts"] + 1
    new_correct = row["correct"] + (1 if is_correct else 0)
    new_mastery = (new_correct / new_attempts) * 100

    cursor.execute(
        "UPDATE topics SET attempts = ?, correct = ?, mastery_score = ? WHERE id = ?",
        (new_attempts, new_correct, new_mastery, topic_id)
    )
    conn.commit()
    conn.close()

# --- Attempt functions ---

def log_attempt(topic_id, question, user_answer, correct_answer, is_correct):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO attempts (topic_id, question, user_answer, correct_answer, is_correct) VALUES (?, ?, ?, ?, ?)",
        (topic_id, question, user_answer, correct_answer, is_correct)
    )
    conn.commit()
    conn.close()
def save_chunks(session_id, chunks):
    conn = get_connection()
    cursor = conn.cursor()
    for i, chunk in enumerate(chunks):
        cursor.execute(
            "INSERT INTO chunks (session_id, chunk_index, content) VALUES (?, ?, ?)",
            (session_id, i, chunk)
        )
    conn.commit()
    conn.close()

def get_chunks(session_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT content FROM chunks WHERE session_id = ? ORDER BY chunk_index",
        (session_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [row["content"] for row in rows]