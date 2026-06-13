from groq import Groq
from config import GROQ_API_KEY
import json
import re
import random
import string

client = Groq(api_key=GROQ_API_KEY)
MODEL = "llama-3.1-8b-instant"

def extract_json(text):
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    return text.strip()

def call_groq(prompt, temperature=0.3):
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=2048
    )
    return response.choices[0].message.content

def extract_topics(full_text):
    trimmed = full_text[:8000]
    prompt = f"""
You are an expert educator. Read the study material below and extract the main topics or concepts covered.

Rules:
- Return ONLY a JSON array of strings
- Each string is a topic name, concise and clear (3-6 words max)
- Extract between 5 and 10 topics
- No preamble, no explanation, no markdown — just the raw JSON array

Example output:
["Gradient Descent", "Overfitting and Underfitting", "Bayes Theorem", "Neural Network Layers"]

Study Material:
{trimmed}
"""
    response = call_groq(prompt)
    cleaned = extract_json(response)
    try:
        topics = json.loads(cleaned)
        return [t for t in topics if isinstance(t, str)]
    except json.JSONDecodeError:
        lines = [line.strip().strip('"-,[]') for line in cleaned.split('\n') if line.strip()]
        return [l for l in lines if l][:10]

def generate_quiz(full_text, topics):
    trimmed = full_text[:8000]
    topic_list = ", ".join(topics)
    prompt = f"""
You are an expert educator creating a multiple choice quiz.

Study Material:
{trimmed}

Topics to test: {topic_list}

Rules:
- Generate exactly one MCQ per topic listed
- Each question must be directly based on the study material
- Each question has exactly 4 options labeled A, B, C, D
- Only one option is correct
- Return ONLY a JSON array, no preamble, no markdown, no explanation
- Vary the question style each time — use different formats such as:
  "Which of the following...", "What is the primary reason...", 
  "In the context of [topic]...", "A student observes that... what explains this?"
- Never ask the most obvious definitional question — go deeper

Each object in the array must have exactly these fields:
{{
  "topic": "exact topic name from the list",
  "question": "the question text",
  "options": {{
    "A": "option text",
    "B": "option text",
    "C": "option text",
    "D": "option text"
  }},
  "correct_answer": "A or B or C or D",
  "explanation": "one sentence explaining why this is correct"
}}

Return only the JSON array.
"""
    response = call_groq(prompt, temperature=0.9)
    cleaned = extract_json(response)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return []

def generate_adaptive_quiz(full_text, weak_topics):
    trimmed = full_text[:8000]
    topic_list = ", ".join(weak_topics)
    prompt = f"""
You are an expert educator creating a follow-up quiz to help a student improve on weak areas.

Study Material:
{trimmed}

Weak topics to re-test: {topic_list}

Rules:
- Generate exactly one NEW MCQ per weak topic — different from any previous question
- Questions must be based strictly on the study material
- Each question has exactly 4 options labeled A, B, C, D
- Only one option is correct
- Return ONLY a JSON array, no preamble, no markdown, no explanation

Each object must have exactly these fields:
{{
  "topic": "exact topic name from the list",
  "question": "the question text",
  "options": {{
    "A": "option text",
    "B": "option text",
    "C": "option text",
    "D": "option text"
  }},
  "correct_answer": "A or B or C or D",
  "explanation": "one sentence explaining why this is correct"
}}

Return only the JSON array.
"""
    response = call_groq(prompt)
    cleaned = extract_json(response)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return []

def generate_summary(full_text):
    trimmed = full_text[:8000]
    prompt = f"""
You are an expert educator. Summarize the study material below clearly and concisely.

Rules:
- Return a JSON object with a single key "summary"
- The summary should be a list of bullet points as an array of strings
- Each bullet point is one key concept or fact
- Maximum 10 bullet points
- No preamble, no markdown, just the raw JSON object

Example output:
{{"summary": ["First key concept here", "Second key concept here"]}}

Study Material:
{trimmed}
"""
    # Inject random seed to force variation
    seed = ''.join(random.choices(string.ascii_lowercase, k=6))
    prompt += f"\n\nVariation seed (ignore this, just ensures variety): {seed}"
    response = call_groq(prompt)
    cleaned = extract_json(response)
    try:
        data = json.loads(cleaned)
        return data.get("summary", [])
    except json.JSONDecodeError:
        lines = [line.strip().lstrip('-•* ') for line in cleaned.split('\n') if line.strip()]
        return lines[:10]

def answer_question(context_chunks, question):
    context = "\n\n".join(context_chunks)
    prompt = f"""
    You are a helpful study assistant. 

    First try to answer using the context below. If the context 
    contains relevant information, use it and stay grounded to it.
    If the context is insufficient, answer from your general knowledge
    but clearly say "This is from general knowledge, not your material."

    Context:
    {context}

    Question: {question}

Give a clear, concise answer in 2-4 sentences.
"""
    return call_groq(prompt).strip()