import json
import requests
import os
from dotenv import load_dotenv

load_dotenv()

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")

def get_kb_response(query):
    try:
        with open("kb_utm.txt", "r", encoding="utf-8") as f:
            kb_content = f.read()
    except Exception as e:
        return f"Error al leer KB: {e}"

    prompt = f"""
    Eres el asistente oficial de Soporte de la Universidad Tecnológica de Matamoros. 
    Usa la siguiente BASE DE CONOCIMIENTOS para responder la duda del usuario de forma amable, profesional y concisa.
    Si la información no está en la base, pide al usuario que se comunique a los teléfonos oficiales.

    BASE DE CONOCIMIENTOS:
    {kb_content}

    DUDA DEL USUARIO:
    {query}

    RESPUESTA:
    """
    
    try:
        payload = {
            "model": "phi3",
            "prompt": prompt,
            "stream": False
        }
        response = requests.post(OLLAMA_URL, json=payload)
        if response.status_code == 200:
            return response.json().get("response", "Lo siento, hubo un error al generar la respuesta.")
        else:
            return f"Error de Ollama (Status {response.status_code}): {response.text}"
    except Exception as e:
        return f"Error al conectar con Ollama: {e}"
    
    return "Gracias por contactar a Soporte UTM."

if __name__ == "__main__":
    print("-" * 30)
    print("SIMULACIÓN DE PRUEBA - IA UTM")
    print("-" * 30)
    
    test_queries = [
        "¿Cuáles son los números de Servicios Escolares?",
        "¿Qué necesito para la beca de manutención?",
        "¿Cuándo es el pre-registro para 2026?"
    ]
    
    for query in test_queries:
        print(f"\nPREGUNTA: {query}")
        print("PROCESANDO...")
        respuesta = get_kb_response(query)
        print(f"RESPUESTA IA:\n{respuesta}")
        print("-" * 20)
