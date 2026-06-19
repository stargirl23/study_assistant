# Adaptive Study Assistant

An intelligent study companion that turns your notes and PDFs into a personalized quiz experience — and keeps re-testing you on weak areas until you've truly mastered the material.

Built with a RAG (Retrieval-Augmented Generation) pipeline from scratch, without relying on LangChain or any high-level abstraction framework.

---

## Features

- **Upload PDF or paste text** — supports any study material
- **Automatic topic extraction** — LLM identifies 5–10 key concepts from your material
- **Adaptive quizzing** — generates MCQs per topic; subsequent rounds only re-test topics below 80% mastery
- **Fresh questions every round** — never repeats the same question twice
- **Mastery dashboard** — visual progress bar per topic (Weak / In Progress / Mastered)
- **RAG-powered Q&A** — ask questions and get answers grounded strictly in your uploaded material
- **Bullet-point summary** — one-click summary of the entire material
- **Session persistence** — mastery scores saved across sessions; resume anytime without re-uploading
- **User-specific history** — browser-based identity keeps your sessions separate from others

---

## Architecture

```
User uploads PDF / pastes text
          │
          ▼
  Text extracted (PyMuPDF)
          │
          ▼
  Chunked into 500-char pieces with 50-char overlap
          │
          ▼
  Each chunk embedded via HuggingFace Inference API
  (sentence-transformers/all-MiniLM-L6-v2)
          │
          ▼
  Embeddings stored in FAISS index (in-memory)
  Chunks saved to SQLite for session restore
          │
     ┌────┴────┐
     │         │
  Quiz Q&A  Summary
     │         │
     ▼         ▼
  Groq (Llama 3) generates responses
  grounded in retrieved chunks
     │
     ▼
  Answers scored → mastery updated in SQLite
     │
     ▼
  Weak topics (< 80%) → adaptive re-quiz
  with fresh questions each round
     │
     ▼
  All topics ≥ 80% → Mastered 🎉
```

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Backend | Python + Flask | REST API |
| LLM | Groq — Llama 3.3 70B | Topic extraction, quiz generation, Q&A, summary |
| Embeddings | HuggingFace Inference API | Convert text chunks to vectors |
| Vector Store | FAISS (Facebook AI) | Fast similarity search for RAG retrieval |
| Database | SQLite | Session storage, topic mastery, attempt history |
| PDF Parsing | PyMuPDF (fitz) | Extract text from uploaded PDFs |
| Frontend | HTML + CSS + Vanilla JS | UI — no framework, no build step |

---

## How Adaptive Quizzing Works

```
Round 1: Generate 1 MCQ per topic (e.g. 8 topics = 8 questions)
          ↓
         Score answers → update mastery per topic in SQLite
          ↓
         mastery = (correct attempts / total attempts) × 100
          ↓
Round 2: Only re-test topics where mastery < 80%
         Generate NEW questions — not repeats
          ↓
         Repeat until all topics ≥ 80%
          ↓
         "You've mastered this material!" 🎉
```

This mirrors spaced repetition principles — focusing effort where it's needed rather than re-testing what you already know.

---

## Project Structure

```
study_assistant/
│
├── backend/
│   ├── app.py          # Flask API — all routes
│   ├── rag.py          # Chunking, embedding, FAISS retrieval
│   ├── llm.py          # Groq API calls — quiz, summary, Q&A, topics
│   ├── db.py           # SQLite schema and all database queries
│   ├── config.py       # Environment variable loading
│   └── requirements.txt
│
├── frontend/
│   ├── index.html      # Upload, session history, summary, Q&A
│   ├── quiz.html       # Quiz taking, results, mastery dashboard
│   └── style.css       # Shared dark theme styles
│
├── .gitignore
├── render.yaml
└── README.md
```

---

## Running Locally

### Prerequisites
- Python 3.10+
- A [Groq API key](https://console.groq.com) (free)
- A [HuggingFace token](https://huggingface.co/settings/tokens) (free)

### Setup

```bash
# Clone the repo
git clone https://github.com/stargirl23/study_assistant.git
cd study_assistant

# Install dependencies
pip install -r backend/requirements.txt

# Add your API keys to backend/config.py
GROQ_API_KEY = "your_groq_key_here"
HF_TOKEN = "your_hf_token_here"

# Run the backend
cd backend
python3 app.py
```

Then open `http://127.0.0.1:5000` in your browser.

---

## Database Schema

```sql
-- Study sessions per user
sessions (id, name, user_id, created_at)

-- Topics extracted per session
topics (id, session_id, topic_name, mastery_score, attempts, correct)

-- Individual question attempts for history
attempts (id, topic_id, question, user_answer, correct_answer, is_correct, attempted_at)

-- Text chunks for session restore (rebuilds FAISS without re-upload)
chunks (id, session_id, chunk_index, content)
```

---

## Key Design Decisions

**Why RAG instead of just sending the full PDF to the LLM?**
LLMs have context window limits. A 50-page PDF would exceed most limits and cost significantly more tokens. RAG retrieves only the 3 most relevant chunks per query — efficient and accurate.

**Why FAISS instead of a hosted vector DB?**
For a local/lightweight deployment, FAISS runs entirely in-memory with no external service dependency. It supports L2 similarity search over hundreds of chunks in milliseconds.

**Why SQLite instead of MySQL?**
No server required — SQLite is a single file. For a single-user study tool this is the right tradeoff. The schema is identical to MySQL so migration is straightforward if needed.

**Why store chunks in SQLite?**
FAISS indexes are in-memory and lost on server restart. Storing raw chunks in SQLite lets us rebuild the FAISS index on session resume — so users never need to re-upload their material.

**Why Groq + Llama over OpenAI?**
Groq's free tier (100k tokens/day on Llama 3.3 70B) requires no billing details and has no credit card requirement — making this project fully free to run and demo.

---

## 📄 License

MIT License — free to use, modify, and distribute.
