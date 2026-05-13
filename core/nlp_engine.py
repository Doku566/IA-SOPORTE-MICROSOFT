import requests
import json
import os

# URL del Demonio de Ollama local (Aislado de internet)
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/generate")

def classify_intent(text):
    """Clasificador Zero-Shot con modelo local Phi-3 (NLP)."""
    prompt = f"""
    Eres un asistente técnico de la Universidad Tecnológica de Matamoros (UTM).
    Analiza el siguiente correo y clasifícalo en: 'PASSWORD_RESET', 'INFORMACION', 'ANOMALIA', 'IGNORAR'.
    Responde ESTRICTAMENTE en formato JSON:
    {{"intencion": "CATEGORIA", "resumen": "Breve resumen"}}

    Correo:
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
        print(f"Error AI: {e}")
    return {"intencion": "INFORMACION", "resumen": "Fallback de seguridad"}

def get_kb_response(query):
    """Generación de respuestas con arquitectura RAG (Retrieval-Augmented Generation)."""
    kb_content = "Corpus de Conocimiento de UTM..." # En producción, lee de knowledge_base.txt
    
    prompt = f"""
    Eres el asistente oficial de Soporte UTM. 
    Responde estrictamente usando la BASE DE CONOCIMIENTOS. 
    Si la información solicitada no existe, responde: "No cuento con esa información específica".
    
    BASE DE CONOCIMIENTOS:
    {kb_content}
    
    DUDA DEL ESTUDIANTE:
    {query}
    """
    payload = {
        "model": "phi3",
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.05 # Límite determinista estricto para evitar alucinaciones
        } 
    }
    try:
        response = requests.post(OLLAMA_URL, json=payload)
        return response.json().get("response", "Lo siento, ocurrió un error en la inferencia.")
    except:
        return "Error de conexión con el motor cognitivo."
