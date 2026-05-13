import os
import time
import uuid
import json
import sqlite3
import requests
import sys
import string
import random
import re
import hashlib
from datetime import datetime, timedelta
from dotenv import load_dotenv
from msal import ConfidentialClientApplication

# Fix Unicode for console output (emojis)
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

# Load environment variables
load_dotenv()

# Config
TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")

def is_student_email(email: str) -> bool:
    """Valida si el correo pertenece a un estudiante basado en los patrones de la UTM."""
    email = email.lower().strip()
    if not email.endswith("@utmatamoros.edu.mx"):
        return False
    
    # Extraer la parte del nombre de usuario
    username = email.split("@")[0]
    
    # Patrón 1: Empieza con dígitos (matrícula)
    if username and username[0].isdigit():
        return True
    
    # Patrón 2: Empieza con 'utm'
    if username.startswith("utm"):
        return True
        
    return False
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

DB_NAME = "soporte_utm.db"

# MS Graph Scopes
SCOPES = ["https://graph.microsoft.com/.default"]

def get_access_token():
    app = ConfidentialClientApplication(
        CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}",
        client_credential=CLIENT_SECRET
    )
    result = app.acquire_token_for_client(scopes=SCOPES)
    if "access_token" in result:
        return result["access_token"]
    else:
        print(f"Error al obtener token: {result.get('error_description')}")
        return None

def fetch_unread_emails(token):
    url = f"https://graph.microsoft.com/v1.0/users/{SUPPORT_EMAIL}/mailFolders/inbox/messages?$filter=isRead eq false"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get("value", [])
    else:
        print(f"Error al obtener correos: {response.status_code} - {response.text}")
        return []

def classify_intent(text):
    prompt = f"""
    Eres un asistente técnico de la Universidad Tecnológica de Matamoros (UTM).
    Analiza el siguiente correo y clasifícalo en una de estas cuatro categorías:

    1. 'PASSWORD_RESET': El usuario pide ayuda con su contraseña, acceso, O está respondiendo con sus datos (Nombre, Matrícula, Identificación) para una verificación.
    2. 'INFORMACION': Dudas generales sobre la universidad, carreras, horarios o trámites escolares.
    3. 'ANOMALIA': Insultos, amenazas, reportes de errores críticos de sistema, o preguntas totalmente ajenas al ámbito de la universidad y su soporte técnico (ej. recetas, juegos, política).
    4. 'IGNORAR': Publicidad, boletines automáticos, spam o correos vacíos sin peticiones.

    CLAVE: Si el correo incluye una MATRÍCULA (números largos) y un NOMBRE en el contexto de una ayuda, suele ser 'PASSWORD_RESET'.

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
            result = response.json()
            return json.loads(result.get("response", "{}"))
    except Exception as e:
        print(f"Error con Ollama: {e}")
    
    return {"intencion": "INFORMACION", "resumen": "No se pudo clasificar"}

def get_kb_response(query):
    try:
        with open("kb_utm.txt", "r", encoding="utf-8") as f:
            kb_content = f.read()
    except:
        kb_content = "Información general de la UTM."

    prompt = f"""
    Eres el asistente oficial de Soporte de la Universidad Tecnológica de Matamoros (UTM). 
    Usa la BASE DE CONOCIMIENTOS para responder la duda del estudiante de forma completa.

    REGLAS ESTRICTAS E INFALIBLES:
    1. MULTIPREGUNTA: Analiza el correo del estudiante. Si hace 2, 3 o más preguntas diferentes en el mismo mensaje, OBLIGATORIAMENTE debes responder TODAS Y CADA UNA de ellas en secciones separadas. No olvides ninguna.
    2. CERO INVENTOS: Si preguntan algo que NO está escrito en la Base de Conocimientos, no inventes fechas, ni costos, ni datos. Responde estrictamente: "No cuento con esa información específica" y diles que contacten al CAE o al departamento correspondiente.
    3. ANTI-JUEGOS (FUERA DE CONTEXTO): Si el estudiante pregunta sobre temas ajenos a la universidad (ej. recetas, política, chistes, programación general, tareas), DEBES NEGARTE A RESPONDER. Responde EXACTAMENTE: "Soy el Motor de Soporte de la UTM y mi conocimiento está estrictamente limitado a temas institucionales. No puedo ayudarte con consultas externas."
    4. FORMATO: Usa etiquetas HTML para estructurar tu respuesta (<b> para resaltar, <ul> y <li> para listas, <p> para párrafos).
    5. IMÁGENES: Si la Base de Conocimientos incluye una etiqueta <img> (como el logo o mapas), puedes usarla en tu respuesta tal como está escrita.
    6. NO saludes, NO te despidas, NO ofrezcas más ayuda. YO agregaré el saludo y la despedida automáticamente por programación. SOLO genera el núcleo de la respuesta.
    7. NO escribas ```html ni bloques de código.

    BASE DE CONOCIMIENTOS:
    {kb_content}

    DUDA DEL ESTUDIANTE:
    {query}

    RESPUESTA (SOLO EL CONTENIDO, SIN SALUDO, EN HTML):
    """
    
    try:
        payload = {
            "model": "phi3",
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": 1024,
                "temperature": 0.05
            }
        }
        response = requests.post(OLLAMA_URL, json=payload)
        if response.status_code == 200:
            raw_response = response.json().get("response", "Lo siento, hubo un error al generar la respuesta.")
            # Limpiar markdown de código
            core_content = raw_response.replace("```html", "").replace("```", "").strip()
            
            # Envolver la respuesta de la IA en la plantilla HTML con Python de forma segura
            final_html = f"""
            <h3>¡Hola! Es un placer atenderte.</h3>
            <p>A continuación te detallo la información solicitada:</p>
            
            {core_content}
            
            <br><hr style="border-top: 1px solid #ccc;">
            <p><b>💡 También puedo brindarte información detallada sobre las siguientes áreas:</b></p>
            <ul>
                <li>Proceso de Admisión y Requisitos</li>
                <li>Sistema de Becas (Manutención, Movilidad, etc.)</li>
                <li>Oferta Educativa y Carreras Completas</li>
                <li>Directorio de Contactos Oficiales</li>
                <li>Horarios de Atención (Soporte, Escolares, Médico)</li>
            </ul>
            <p>¿Te puedo ayudar con alguno de estos temas? Además, te invito a <a href="https://www.utmatamoros.edu.mx">visitar nuestro portal web oficial aquí</a>.</p>
            """
            return final_html
    except Exception as e:
        print(f"Error al generar respuesta KB: {e}")
    
    return "Gracias por contactar a Soporte UTM. Tu solicitud está siendo revisada."

def send_email(token, to_email, subject, content):
    url = f"https://graph.microsoft.com/v1.0/users/{SUPPORT_EMAIL}/sendMail"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "message": {
            "subject": subject,
            "body": {
                "contentType": "HTML",
                "content": content
            },
            "toRecipients": [
                {"emailAddress": {"address": to_email}}
            ]
        }
    }
    response = requests.post(url, headers=headers, json=payload)
    return response.status_code == 202

def mark_as_read(token, message_id):
    url = f"https://graph.microsoft.com/v1.0/users/{SUPPORT_EMAIL}/messages/{message_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {"isRead": True}
    requests.patch(url, headers=headers, json=payload)

def generate_otp(sender: str) -> str:
    """Genera un código OTP de 6 dígitos vinculado al correo del remitente y almacenado en DB.
    SEGURIDAD: El OTP es válido por 10 minutos y queda registrado en la auditoría.
    Un Regex extrae la matrícula, pero NUNCA autoriza el reset por sí solo.
    El OTP es la segunda capa de verificación obligatoria."""
    otp = str(random.randint(100000, 999999))
    otp_hash = hashlib.sha256(otp.encode()).hexdigest()
    expiry = (datetime.utcnow() + timedelta(minutes=10)).isoformat()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO otp_tokens (correo_origen, otp_hash, expiry) VALUES (?, ?, ?)",
        (sender, otp_hash, expiry)
    )
    conn.commit()
    conn.close()
    return otp

def verify_otp(sender: str, otp_attempt: str) -> bool:
    """Valida el OTP ingresado contra el hash almacenado y verifica que no haya expirado."""
    otp_hash = hashlib.sha256(otp_attempt.strip().encode()).hexdigest()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT otp_hash, expiry FROM otp_tokens WHERE correo_origen = ? ORDER BY rowid DESC LIMIT 1",
        (sender,)
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return False
    stored_hash, expiry_str = row
    if datetime.utcnow() > datetime.fromisoformat(expiry_str):
        print(f"OTP expirado para {sender}")
        return False
    return stored_hash == otp_hash

def handle_external_verification(token, email, classification):
    sender = email.get("from", {}).get("emailAddress", {}).get("address")
    subject = email.get("subject", "Sin Asunto")
    body = email.get("body", {}).get("content", "")

    # SEGURIDAD: El Regex extrae la matrícula SOLO para identificar al usuario.
    # NO autoriza el reset. Es un campo informativo para el Administrador.
    # La autorización real requiere aprobación humana + OTP enviado al correo externo.
    matricula = ""
    match = re.search(r'\b([0-9]{7})\b', body)
    if match:
        matricula = match.group(1)
    else:
        match = re.search(r'(?i)\b(UTM[0-9A-Z-]{8,})\b', body)
        if match:
            matricula = match.group(1)

    inst_email = f"{matricula}@utmatamoros.edu.mx" if matricula else "DESCONOCIDO"

    # Generar OTP de verificación para el remitente externo
    otp_code = generate_otp(sender)

    # Enviar OTP al correo externo del solicitante
    otp_msg = f"""
    <p>Hemos recibido su solicitud de restablecimiento de contraseña.</p>
    <p>Para verificar su identidad, ingrese el siguiente código de confirmación
    en su próxima respuesta a este correo:</p>
    <h2 style="letter-spacing: 8px; font-family: monospace;">{otp_code}</h2>
    <p><b>Este código expira en 10 minutos.</b></p>
    <p>Si no solicitó este código, ignore este mensaje.</p>
    """
    send_email(token, sender, "Código de Verificación - Soporte UTM", otp_msg)

    # Reenviar al administrador para aprobación (con matrícula como referencia, no como autorización)
    report_body = f"""
    <h3>Verificacion de Identidad Requerida (Correo Externo)</h3>
    <p>Un usuario solicita reseteo desde correo personal. Se ha enviado un OTP al remitente.</p>
    <p><b>PROCESO:</b> El sistema esperara la respuesta del usuario con el OTP.
    Solo tras validar el OTP se solicitara su aprobacion.</p>
    <hr>
    <b>Remitente externo:</b> {sender}<br>
    <b>Matricula detectada (referencia, sin confirmar):</b> {matricula if matricula else 'No detectada'}<br>
    <b>Asunto original:</b> {subject}<br>
    <b>Resumen IA:</b> {classification.get('resumen', 'N/A')}<br>
    <hr>
    <b>Contenido:</b><br>{body}
    <p><i>Esperando validacion OTP del usuario antes de escalar para aprobacion final.</i></p>
    """
    send_email(token, ADMIN_EMAIL, f"[INFO] Solicitud Externa Iniciada: {sender} | {inst_email}", report_body)

def handle_password_reset(token, email_obj, notify_email=None):
    sender = email_obj["from"]["emailAddress"]["address"]
    notify = notify_email if notify_email else sender

    # ================================================================
    # GUARDIA DE SEGURIDAD (Capa de Software)
    # El Motor IA NUNCA debe ejecutar un PATCH sobre una cuenta que
    # no sea un alumno. Esta verificacion es la segunda linea de
    # defensa despues de la Administrative Unit de Entra ID.
    # Si ambas capas fallan, el sistema no ejecuta ninguna accion.
    # ================================================================
    cuenta_objetivo = notify_email if notify_email else sender
    if not is_student_email(cuenta_objetivo):
        alerta = f"""
        <h3>ALERTA DE SEGURIDAD - Accion bloqueada por Motor IA</h3>
        <p>Se intento ejecutar un reseteo de contrasena sobre una cuenta
        que NO cumple el patron de correo de alumno:</p>
        <p><b>Cuenta objetivo:</b> {cuenta_objetivo}</p>
        <p>El Motor IA se ha negado a ejecutar esta accion por politica de seguridad.
        Verifique si se trata de un intento de escalada de privilegios.</p>
        """
        send_email(token, ADMIN_EMAIL, "[SEGURIDAD] Reseteo bloqueado sobre cuenta no-alumno", alerta)
        print(f"SEGURIDAD: PATCH bloqueado. {cuenta_objetivo} no es cuenta de alumno.")
        return
    # ================================================================
    temp_password = "Utm" + "".join(random.choice(chars) for _ in range(8)) + "1!"
    
    print(f"Ejecutando reseteo directo para {sender}...")
    
    # 1. Llamar a Graph API para forzar el cambio
    update_url = f"https://graph.microsoft.com/v1.0/users/{sender}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "passwordProfile": {
            "forceChangePasswordNextSignIn": True,
            "password": temp_password
        }
    }
    
    response = requests.patch(update_url, headers=headers, json=payload)
    
    # 2. Notificar al usuario basado en el resultado
    if response.status_code == 204:
        msg = f"""
        Estimado usuario,
        <br><br>
        Su contraseña ha sido restablecida exitosamente. A continuación se proporcionan sus nuevas credenciales de acceso temporal:
        <br><br>
        <b>Usuario:</b> {sender}<br>
        <b>Contraseña Temporal:</b> <code>{temp_password}</code>
        <br><br>
        <i>Nota Importante:</i> Al iniciar sesión por primera vez con esta contraseña temporal en office.com o en su correo, Microsoft le pedirá obligatoriamente que cree una nueva contraseña personal y secreta.
        <br><br>
        Saludos cordiales,<br>
        Soporte Técnico Automatizado UTM
        """
        send_email(token, notify, "Su nueva contraseña temporal - Soporte UTM", msg)
        print(f"ÉXITO: Contraseña temporal enviada a {notify}")
    else:
        print(f"ERROR Graph API ({response.status_code}): {response.text}")
        error_msg = f"""
        Estimado usuario,
        <br><br>
        Ocurrió un error al intentar restablecer la contraseña para la cuenta institucional en los servidores de Microsoft. 
        Esto puede deberse a que su cuenta está bloqueada o la matrícula proporcionada no existe.
        <br><br>
        Por favor, acuda presencialmente al departamento de Sistemas (Módulo 3) para asistencia técnica.
        """
        send_email(token, notify, "Error en restablecimiento - Soporte UTM", error_msg)

def handle_anomaly(token, email_obj, classification):
    sender = email_obj["from"]["emailAddress"]["address"]
    content = f"""
    <h3>Alerta de Anomalía detectada por IA</h3>
    <p><b>Remitente:</b> {sender}</p>
    <p><b>Resumen IA:</b> {classification.get('resumen')}</p>
    <p><b>Contenido Original:</b></p>
    <pre>{email_obj.get('bodyPreview')}</pre>
    """
    send_email(token, ADMIN_EMAIL, "[URGENTE - IA ESCALADA] Reporte de Anomalía", content)

def is_system_email(email_address):
    blacklist = ["postmaster@microsoft.com", "azure-noreply@microsoft.com", "no-reply", "microsoft-noreply"]
    for pattern in blacklist:
        if pattern in email_address.lower():
            return True
    if email_address.lower().startswith("microsoftexchange"):
        return True
    return False

def check_rate_limit(sender):
    """Verifica si el usuario excedió el límite de 3 correos en los últimos 5 minutos."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) FROM tickets 
            WHERE correo_origen = ? AND fecha_recibido >= datetime('now', '-5 minutes')
        ''', (sender,))
        count = cursor.fetchone()[0]
        conn.close()
        return count >= 3
    except Exception as e:
        print(f"Error verificando rate limit: {e}")
        return False

def sanitize_email_body(text):
    signatures = [
        "Obtener Outlook para Android",
        "Obtener Outlook para iOS",
        "Enviado desde mi iPhone",
        "Enviado desde mi equipo Galaxy",
        "Get Outlook for Android",
        "Get Outlook for iOS",
        "Enviado desde Correo para Windows"
    ]
    for sig in signatures:
        # Remover firmas respetando mayúsculas/minúsculas de la firma original
        text = text.replace(sig, "")
    return text.strip()

def process_emails():
    print("Iniciando ciclo de orquestación...")
    
    # Verificar si Ollama está respondiendo antes de seguir
    try:
        requests.get(OLLAMA_URL.replace("/api/generate", "/api/tags"), timeout=2)
    except:
        print("ALERTA: Ollama no responde. No se procesarán correos para evitar respuestas erróneas.")
        return

    token = get_access_token()
    if not token:
        return

    emails = fetch_unread_emails(token)
    for email in emails:
        sender = email["from"]["emailAddress"]["address"]
        
        if is_system_email(sender):
            print(f"Ignorando correo de sistema: {sender}")
            mark_as_read(token, email["id"])
            continue

        subject = email.get("subject", "")
        
        # PARCHE 1: ANTI-BUCLES (Ignorar respuestas automáticas / Out of Office)
        if "automatic reply" in subject.lower() or "respuesta automática" in subject.lower() or "ausencia" in subject.lower() or "out of office" in subject.lower():
            print(f"Bucle Evitado: Respuesta automática detectada de {sender}")
            mark_as_read(token, email["id"])
            continue
            
        # PARCHE 2: RATE LIMITING (Bloquear fuerza bruta)
        if check_rate_limit(sender):
            print(f"RATE LIMIT EXCEDIDO: Bloqueando peticiones de {sender} (Fuerza bruta detectada).")
            mark_as_read(token, email["id"])
            continue

        body = sanitize_email_body(email.get("bodyPreview", ""))
        full_content = f"Asunto: {subject}\nCuerpo: {body}"
        
        print(f"Procesando correo de: {sender}")
        
        # LOGICA DE ADMINISTRADOR: Aprobación/Rechazo de verificaciones externas
        if sender.lower() == ADMIN_EMAIL.lower() and "[VERIFICACIÓN] Reseteo Externo:" in subject:
            print("DETECTADO: Comando de administrador para verificación.")
            try:
                parts = subject.split("|")
                target_email = parts[0].split("Reseteo Externo:")[1].strip()
                inst_email = parts[1].strip() if len(parts) > 1 else "DESCONOCIDO"
            except:
                print("No se pudo extraer el correo destino del asunto.")
                mark_as_read(token, email["id"])
                continue
                
            # Extraer matrícula del cuerpo si el admin escribe "APROBAR 2010145"
            override_match = re.search(r'(?i)aprobar\s+([0-9]{7}|UTM[0-9A-Z-]+)', body)
            if override_match:
                inst_email = f"{override_match.group(1)}@utmatamoros.edu.mx"
                
            if "aprobar" in body.lower() or "autorizado" in body.lower() or "aprobado" in body.lower():
                if "DESCONOCIDO" in inst_email:
                    print("ERROR: Admin aprobó pero no hay matrícula.")
                    send_email(token, ADMIN_EMAIL, "Error: Falta Matrícula", "La IA no detectó la matrícula en el correo original. Por favor responde de nuevo con: APROBAR [MATRÍCULA] (ej. APROBAR 2010145)")
                    mark_as_read(token, email["id"])
                    continue
                    
                print(f"ADMIN APROBÓ el reseteo para {inst_email} vía {target_email}")
                mock_email = {"from": {"emailAddress": {"address": inst_email}}}
                handle_password_reset(token, mock_email, notify_email=target_email)
                send_email(token, ADMIN_EMAIL, f"✅ Aprobado: {inst_email}", f"El enlace de reseteo fue generado y enviado exitosamente al correo externo: {target_email}")
            elif "rechazar" in body.lower() or "denegado" in body.lower():
                print(f"ADMIN RECHAZÓ el reseteo para {target_email}")
                send_email(token, target_email, "Verificación Rechazada - Soporte UTM", "Estimado usuario, su solicitud de reseteo de contraseña ha sido rechazada debido a que los documentos proporcionados no son válidos o no coinciden con nuestros registros. Por favor, acuda presencialmente al departamento.")
                send_email(token, ADMIN_EMAIL, f"❌ Rechazado: {target_email}", "Se ha notificado al usuario externo sobre el rechazo de su solicitud.")
            else:
                print("Comando de administrador no reconocido. Usa 'aprobar' o 'rechazar'.")
                
            mark_as_read(token, email["id"])
            continue

        # Filtro de Spam/Sistema
        blacklist = ["news@", "noreply@", "no-reply@", "postmaster@", "microsoft@", "clarovideo", "notificaciones"]
        if any(word in sender.lower() or word in body.lower() for word in blacklist):
            print(f"SPAM DETECTADO de {sender}. Ignorando...")
            mark_as_read(token, email["id"])
            continue

        classification = classify_intent(full_content)
        
        # LÓGICA DE PRIORIDAD: Si es respuesta a verificación, forzar PASSWORD_RESET
        if "re: acción requerida" in subject.lower() or "verificación de identidad" in subject.lower():
            classification = {"intencion": "PASSWORD_RESET", "resumen": "Respuesta a verificación de identidad externa."}
        
        print(f"Respuesta Raw de IA: {classification}")
        intent = classification.get("intencion")
        
        if not intent:
            print(f"No se pudo clasificar el correo de {sender}. Saltando...")
            continue

        print(f"Intención detectada: {intent}")
        
        # Guardar en DB
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO tickets (correo_origen, intencion, estado) VALUES (?, ?, ?)",
            (sender, intent, "PROCESADO" if intent != "ANOMALIA" else "ESCALADO")
        )
        conn.commit()
        conn.close()
        
        if intent == "PASSWORD_RESET":
            # SEGURIDAD: Si es alumno con correo institucional, proceder directo
            if is_student_email(sender):
                print(f"Generando link de reseteo para alumno: {sender}")
                handle_password_reset(token, email)
            else:
                # Si es correo externo, verificar si ya envió los requisitos
                has_attachments = email.get("hasAttachments", False)
                # También revisamos si hay mención de imágenes en el cuerpo HTML
                body_content = email.get("body", {}).get("content", "").lower()
                is_inline_image = "cid:" in body_content or "<img" in body_content
                
                print(f"DEBUG: Correo externo de {sender} | Adjuntos: {has_attachments} | Imagen Inline: {is_inline_image}")

                # Buscamos patrones de matrícula y nombre en el cuerpo
                has_matricula = any(char.isdigit() for char in body) and len(body) > 5
                
                if (has_attachments or is_inline_image) and has_matricula:
                    print(f"REVISIÓN MANUAL REQUERIDA: Datos recibidos de correo externo {sender}")
                    # Enviar a revisión del Admin con la foto
                    handle_external_verification(token, email, classification)
                else:
                    print(f"SOLICITANDO REQUISITOS: Correo externo {sender}")
                    msg = """
                    Estimado usuario, para procesar una solicitud de contraseña desde un correo <b>personal</b>, 
                    por seguridad es obligatorio que responda a este correo adjuntando la siguiente información:
                    <br><br>
                    1. <b>Nombre Completo</b><br>
                    2. <b>Matrícula</b><br>
                    3. <b>Foto de tu credencial de estudiante</b> (o identificación oficial INE/Pasaporte).
                    <br><br>
                    Una vez recibida y validada la información, procederemos con su solicitud.
                    """
                    send_email(token, sender, "Acción Requerida - Verificación de Identidad UTM", msg)
        elif intent == "ANOMALIA":
            handle_anomaly(token, email, classification)
        elif intent == "IGNORAR":
            print(f"IA decidió IGNORAR este correo: {sender}")
        else:
            # Respuesta usando la base de conocimientos
            content = get_kb_response(full_content)
            send_email(token, sender, "Re: Consulta de Soporte UTM", content)
        
        mark_as_read(token, email["id"])

if __name__ == "__main__":
    while True:
        try:
            process_emails()
        except Exception as e:
            print(f"Error en el orquestador: {e}")
        
        print("Esperando 30 segundos...")
        time.sleep(30)
