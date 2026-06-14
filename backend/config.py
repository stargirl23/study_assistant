import os

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
DB_PATH = "study_assistant.db"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
MASTERY_THRESHOLD = 80.0