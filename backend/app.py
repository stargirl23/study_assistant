from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import uuid

from config import DB_PATH
from db import init_db, create_session, get_all_sessions, insert_topics, get_topics, get_weak_topics, update_topic_mastery, log_attempt, save_chunks, get_chunks
from rag import extract_text_from_pdf, extract_text_from_string, build_index, retrieve_chunks, get_full_text, session_exists, rebuild_index
from llm import extract_topics, generate_quiz, generate_adaptive_quiz, generate_summary, answer_question

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize database on startup
init_db()

# ─── Upload & Process ───────────────────────────────────────────────

@app.route('/upload', methods=['POST'])
def upload():
    try:
        session_name = request.form.get('session_name', 'Untitled Session')
        user_id = request.form.get('user_id', 'anonymous')
        text = ""
        if 'file' in request.files:
            file = request.files['file']
            if file.filename.endswith('.pdf'):
                filepath = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}.pdf")
                file.save(filepath)
                text = extract_text_from_pdf(filepath)
                os.remove(filepath)  # Clean up after extraction
            else:
                return jsonify({"error": "Only PDF files supported"}), 400

        elif 'text' in request.form:
            text = extract_text_from_string(request.form['text'])

        else:
            return jsonify({"error": "No file or text provided"}), 400

        if not text:
            return jsonify({"error": "Could not extract text from material"}), 400

        # Create session in DB
        session_id = create_session(session_name, user_id)

# Build FAISS index
        num_chunks = build_index(session_id, text)

# Save chunks to SQLite for session restore
        from rag import session_store
        chunks = session_store[session_id]["chunks"]
        save_chunks(session_id, chunks)
        # Extract topics via Gemini
        topics = extract_topics(text)
        if not topics:
            return jsonify({"error": "Could not extract topics from material"}), 400

        # Store topics in DB
        insert_topics(session_id, topics)

        # Pre-generate summary and cache it
        summary = generate_summary(text)

        return jsonify({
            "session_id": session_id,
            "session_name": session_name,
            "num_chunks": num_chunks,
            "topics": topics,
            "summary": summary
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── Sessions ────────────────────────────────────────────────────────

@app.route('/sessions', methods=['GET'])
def sessions():
    try:
        user_id = request.args.get('user_id', 'anonymous')
        all_sessions = get_all_sessions(user_id)
        return jsonify({"sessions": all_sessions})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
# ─── Restore Session ─────────────────────────────────────────────────

@app.route('/restore/<int:session_id>', methods=['POST'])
def restore_session(session_id):
    try:
        # Already in memory — no need to restore
        if session_exists(session_id):
            return jsonify({"status": "already_loaded"})

        # Load chunks from SQLite and rebuild FAISS
        chunks = get_chunks(session_id)
        if not chunks:
            return jsonify({"error": "No chunks found for this session"}), 404

        success = rebuild_index(session_id, chunks)
        if not success:
            return jsonify({"error": "Failed to rebuild index"}), 500

        return jsonify({"status": "restored", "num_chunks": len(chunks)})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─── Topics & Dashboard ──────────────────────────────────────────────

@app.route('/dashboard/<int:session_id>', methods=['GET'])
def dashboard(session_id):
    try:
        topics = get_topics(session_id)
        weak = [t for t in topics if t['mastery_score'] < 80.0]
        mastered = [t for t in topics if t['mastery_score'] >= 80.0]

        return jsonify({
            "topics": topics,
            "weak_count": len(weak),
            "mastered_count": len(mastered),
            "total_count": len(topics),
            "all_mastered": len(weak) == 0
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── Quiz Generation ─────────────────────────────────────────────────

@app.route('/generate-quiz/<int:session_id>', methods=['GET'])
def generate_quiz_route(session_id):
    try:
        if not session_exists(session_id):
            return jsonify({"error": "Session not found. Please re-upload your material."}), 404

        full_text = get_full_text(session_id)
        topics = get_topics(session_id)

        # First round — test all topics
        # Subsequent rounds — only weak topics
        weak_topics = get_weak_topics(session_id)
        all_attempted = all(t['attempts'] > 0 for t in topics)

        if not all_attempted:
            # Initial quiz — all topics
            topic_names = [t['topic_name'] for t in topics]
            quiz = generate_quiz(full_text, topic_names)
            quiz_type = "initial"
        else:
            # Adaptive quiz — weak topics only
            if not weak_topics:
                return jsonify({
                    "all_mastered": True,
                    "message": "You have mastered all topics!"
                })
            topic_names = [t['topic_name'] for t in weak_topics]
            quiz = generate_adaptive_quiz(full_text, topic_names)
            quiz_type = "adaptive"

        # Attach topic_id to each question for tracking
        topic_map = {t['topic_name'].lower(): t['id'] for t in topics}
        for question in quiz:
            matched_id = topic_map.get(question.get('topic', '').lower())
            question['topic_id'] = matched_id

        return jsonify({
            "quiz": quiz,
            "quiz_type": quiz_type,
            "weak_count": len(weak_topics)
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── Submit Answers ──────────────────────────────────────────────────

@app.route('/submit-answers', methods=['POST'])
def submit_answers():
    try:
        data = request.get_json()
        answers = data.get('answers', [])
        # answers = [{ topic_id, question, user_answer, correct_answer }, ...]

        results = []
        for ans in answers:
            topic_id = ans['topic_id']
            question = ans['question']
            user_answer = ans['user_answer']
            correct_answer = ans['correct_answer']
            is_correct = user_answer.strip().upper() == correct_answer.strip().upper()

            # Update mastery in DB
            update_topic_mastery(topic_id, is_correct)

            # Log the attempt
            log_attempt(topic_id, question, user_answer, correct_answer, is_correct)

            results.append({
                "topic_id": topic_id,
                "question": question,
                "user_answer": user_answer,
                "correct_answer": correct_answer,
                "is_correct": is_correct
            })

        correct_count = sum(1 for r in results if r['is_correct'])

        return jsonify({
            "results": results,
            "correct": correct_count,
            "total": len(results),
            "score_percent": round((correct_count / len(results)) * 100, 1) if results else 0
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── Q&A ─────────────────────────────────────────────────────────────

@app.route('/ask', methods=['POST'])
def ask():
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        question = data.get('question', '').strip()

        if not question:
            return jsonify({"error": "No question provided"}), 400

        if not session_exists(session_id):
            return jsonify({"error": "Session not found. Please re-upload your material."}), 404

        chunks = retrieve_chunks(session_id, question, top_k=3)
        answer = answer_question(chunks, question)

        return jsonify({"answer": answer})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── Summary ─────────────────────────────────────────────────────────

@app.route('/summary/<int:session_id>', methods=['GET'])
def summary(session_id):
    try:
        if not session_exists(session_id):
            return jsonify({"error": "Session not found. Please re-upload your material."}), 404

        full_text = get_full_text(session_id)
        summary = generate_summary(full_text)

        return jsonify({"summary": summary})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── Run ─────────────────────────────────────────────────────────────

if __name__ == '__main__':
    app.run(debug=True, port=5000)