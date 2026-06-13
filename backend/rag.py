import fitz  # PyMuPDF
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from config import CHUNK_SIZE, CHUNK_OVERLAP

# Load embedding model once at startup — this takes 5-10 seconds first time
model = SentenceTransformer('all-MiniLM-L6-v2')

# In-memory store — holds chunks and FAISS index per session
session_store = {}

# --- Text Extraction ---

def extract_text_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    full_text = ""
    for page in doc:
        full_text += page.get_text()
    doc.close()
    return full_text.strip()

def extract_text_from_string(text):
    return text.strip()

# --- Chunking ---

def chunk_text(text):
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk)
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks

# --- Embedding + FAISS Indexing ---

def build_index(session_id, text):
    chunks = chunk_text(text)
    
    if not chunks:
        return 0

    embeddings = model.encode(chunks, show_progress_bar=False)
    embeddings = np.array(embeddings).astype('float32')

    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings)

    # Store everything in memory keyed by session_id
    session_store[session_id] = {
        "chunks": chunks,
        "index": index,
        "full_text": text
    }

    return len(chunks)

# --- Retrieval ---

def retrieve_chunks(session_id, query, top_k=3):
    if session_id not in session_store:
        return []

    store = session_store[session_id]
    query_embedding = model.encode([query], show_progress_bar=False)
    query_embedding = np.array(query_embedding).astype('float32')

    distances, indices = store["index"].search(query_embedding, top_k)

    retrieved = []
    for idx in indices[0]:
        if idx < len(store["chunks"]):
            retrieved.append(store["chunks"][idx])

    return retrieved

# --- Full Text Access (for quiz gen and summary) ---

def get_full_text(session_id):
    if session_id not in session_store:
        return ""
    return session_store[session_id]["full_text"]

# --- Utility ---

def session_exists(session_id):
    return session_id in session_store
def rebuild_index(session_id, chunks):
    if not chunks:
        return False

    embeddings = model.encode(chunks, show_progress_bar=False)
    embeddings = np.array(embeddings).astype('float32')

    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings)

    full_text = " ".join(chunks)

    session_store[session_id] = {
        "chunks": chunks,
        "index": index,
        "full_text": full_text
    }

    return True