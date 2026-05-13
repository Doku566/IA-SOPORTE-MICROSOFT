import time
import re
from m365_api import get_access_token, fetch_unread_emails, send_email, handle_password_reset
from nlp_engine import classify_intent, get_kb_response

def process_emails():
    """Ciclo Principal de Orquestación del Motor IA."""
    print("Obteniendo token OAuth (Flujo Client Credentials)...")
    token = get_access_token()
    if not token:
        print("Error crítico: Imposible autenticar con MS Graph.")
        return

    emails = fetch_unread_emails(token)
    for email in emails:
        sender = email['sender']['emailAddress']['address']
        subject = email['subject']
        body = email['bodyPreview']
        
        print(f"Procesando correo entrante de: {sender}")
        
        # 1. Filtros Anti-Bucle (Mail Loops)
        if any(term in subject.lower() for term in ["automatic reply", "ausencia", "out of office"]):
            print("Correo descartado por filtro Anti-Bucle.")
            continue
            
        # 2. Inferencia Cognitiva
        classification = classify_intent(body)
        intent = classification.get("intencion")
        
        # 3. Árbol de Decisión (Enrutador Lógico)
        if intent == "PASSWORD_RESET":
            print("Intención detectada: PASSWORD_RESET")
            
            # Verificación regex estricta para correos externos
            matricula_match = re.search(r'\b([0-9]{7})\b', body)
            if not matricula_match:
                print("Escalando para validación manual: Falta matrícula en texto.")
                continue
                
            print("Ejecutando parche en Graph API para forzar rotación de contraseña...")
            # LÓGICA DE PRODUCCIÓN COMENTADA POR SEGURIDAD EN REPOSITORIO PÚBLICO
            # new_pass = handle_password_reset(token, matricula_match.group(1))
            
            # send_email(token, sender, "Tu nueva credencial de acceso", 
            #   f"Contraseña temporal: {new_pass}. DEBES configurar Microsoft Authenticator en tu primer inicio de sesión.")
        
        elif intent == "INFORMACION":
            print("Intención detectada: INFORMACION (Ejecutando RAG)")
            response_html = get_kb_response(body)
            # send_email(token, sender, "Respuesta Automatizada - Soporte UTM", response_html)
            
        elif intent == "ANOMALIA":
            print("Intención detectada: ANOMALIA (Escalando a Soporte Nivel 2)")
            # Enviar notificación al administrador de TI
            
        elif intent == "IGNORAR":
            print("Descartando spam o correo sin acción requerida.")

if __name__ == "__main__":
    print("Iniciando Daemon de Motor Soporte IA UTM...")
    while True:
        try:
            process_emails()
            time.sleep(30) # Polling de la API cada 30 segundos
        except Exception as e:
            print(f"Error irrecuperable en el ciclo: {e}")
            time.sleep(60) # Backoff
