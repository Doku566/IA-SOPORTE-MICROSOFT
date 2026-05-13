import requests
import json
import os

# URL del Demonio de Ollama local (Aislado de internet)
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/generate")

def classify_intent(text):
    """Zero-shot email classifier using local Phi-3 model.
    
    The system prompt must explicitly define the institutional context.
    A generic or incorrect context causes the LLM to conflict with the
    RAG knowledge base and produce misclassified responses.
    """
    prompt = f"""
    You are a technical support assistant for an educational institution.
    Your only context is institutional IT support: account access, enrollment,
    email accounts, and administrative procedures. You have no knowledge or
    authority outside this scope.
    Classify the following email into exactly one category:
    'PASSWORD_RESET', 'INFORMACION', 'ANOMALIA', or 'IGNORAR'.
    Respond STRICTLY in valid JSON format:
    {{"intencion": "CATEGORY", "resumen": "Brief summary"}}

    Email:
    \"\"\"{text}\"\"\"
    """
    
    try:
        payload = {
            "model": "phi3",
            "prompt": prompt,
            "stream": False,
            "format": "json"
        }
        response = requests.post(OLLAMA_URL, json=payload)
        if response.status_code == 200:
            return json.loads(response.json().get("response", "{}"))
    except Exception as e:
        print(f"Inference error: {e}")
    return {"intencion": "INFORMACION", "resumen": "Safety fallback"}

def get_kb_response(query):
    """RAG response generation using a plain-text knowledge base.
    
    Limitation: The full corpus is injected into the prompt. As the knowledge
    base grows, this approach increases latency and may exceed the model's
    context window. Migrating to ChromaDB or FAISS for semantic retrieval
    is recommended once the corpus exceeds a few hundred entries.
    """
    # In production: read from knowledge_base.txt
    try:
        with open("../data/knowledge_base.txt", "r", encoding="utf-8") as f:
            kb_content = f.read()
    except FileNotFoundError:
        kb_content = "Knowledge base not found."
    
    prompt = f"""
    You are the official support assistant for an educational institution.
    Answer using ONLY the information in the KNOWLEDGE BASE below.
    If the answer is not in the knowledge base, respond exactly:
    "I don't have that specific information."
    Do not invent dates, costs, or procedures.

    KNOWLEDGE BASE:
    {kb_content}

    STUDENT QUESTION:
    {query}
    """
    payload = {
        "model": "phi3",
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.05  # Keep deterministic to prevent hallucinations
        }
    }
    try:
        response = requests.post(OLLAMA_URL, json=payload)
        return response.json().get("response", "Inference error.")
    except:
        return "Could not connect to the local inference engine."
