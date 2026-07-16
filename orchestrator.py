# -*- coding: utf-8 -*-
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
from database import create_ticket, update_ticket, get_ticket_status, get_tickets_by_email, log_consulta, log_conversacion

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
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            return response.json().get("value", [])
        else:
            print(f"Error al obtener correos: {response.status_code} - {response.text}")
            return []
    except Exception as e:
        print(f"Error de red en fetch_unread_emails: {e}")
        return []

def normalize_intent(raw_intent: str) -> str:
    """Normaliza el valor de intención para tolerar typos del modelo (ej. IGORAR→IGNORAR)."""
    if not raw_intent:
        return "INFORMACION"
    val = raw_intent.strip().upper()
    # Mapa de correcciones conocidas
    corrections = {
        "IGORAR": "IGNORAR",
        "IGONRAR": "IGNORAR",
        "IGNORAR": "IGNORAR",
        "IGNORE": "IGNORAR",
        "SPAM": "IGNORAR",
        "PASSWORD": "PASSWORD_RESET",
        "RESET": "PASSWORD_RESET",
        "PASSWORD RESET": "PASSWORD_RESET",
        "CONTRASENA": "PASSWORD_RESET",
        "SEGUIMENTO": "SEGUIMIENTO",
        "SEGUIMINETO": "SEGUIMIENTO",
        "ANOMALY": "ANOMALIA",
        "ANOMALÍA": "ANOMALIA",
        "INFORMACION": "INFORMACION",
        "INFORMACIÓN": "INFORMACION",
        "INFORMATION": "INFORMACION",
    }
    if val in corrections:
        return corrections[val]
    # Si ya es válido, devolverlo
    valid = {"PASSWORD_RESET", "INFORMACION", "SEGUIMIENTO", "ANOMALIA", "IGNORAR"}
    if val in valid:
        return val
    # Fallback: buscar coincidencia parcial
    for v in valid:
        if v in val or val in v:
            return v
    return "INFORMACION"

def classify_intent(text):
    prompt = f"""
    Eres un asistente técnico de la Universidad Tecnológica de Matamoros (UTM).
    Analiza el siguiente correo y clasifícalo en UNA de estas cinco categorías:

    1. 'PASSWORD_RESET': El usuario pide explícitamente reseteo o ayuda con su CONTRASEÑA, CLAVE o ACCESO a su correo institucional.
       Ejemplos: "olvidé mi contraseña", "no puedo entrar a mi correo", "necesito recuperar mi clave", "matrícula 2310450 para contraseña".
       NOTA CRÍTICA: Si el usuario pregunta por "credencial de estudiante", "sacar credencial", "gafete", "identificación escolar", "becas" o "restablecer office 365" SIN mencionar explícitamente contraseña o clave, clasifícalo SIEMPRE en INFORMACION.

    2. 'INFORMACION': Dudas sobre la universidad, trámites, credencial de estudiante, costos, estadías, prácticas profesionales, entrega de documentos, horarios o días laborales, o ayuda general con software/paquetería (instalar/restablecer paquete Office, Teams, EDI).
       Ejemplos: "requisitos para sacar mi credencial", "¿qué carreras ofrecen?", "¿estarán laborando mañana?", "necesito dejar documentos de mis estadías", "horario de la biblioteca", "cómo restablecer mi office 365".

    3. 'SEGUIMIENTO': El usuario pregunta por el estado de una solicitud o ticket YA CREADO anteriormente.
       Esto incluye preguntas vagas como "¿ya me atendieron?", "¿cómo va mi caso?", "¿resolvieron mi problema?", "llevo días esperando".
       También incluye menciones explícitas de código de ticket como "UTM-45231".
       CLAVE: Si alguien pregunta SI ya fue atendido o qué pasó con su solicitud previa → es SIEMPRE 'SEGUIMIENTO'.

    4. 'ANOMALIA': Cualquiera de estos casos:
       - Insultos, amenazas, palabras ofensivas hacia el sistema o personal.
       - INGENIERÍA SOCIAL: Alguien se presenta como técnico, administrador o jefe y pide credenciales, acceso a sistemas, contraseñas de otros, bases de datos, listas de alumnos o datos confidenciales.
       - Solicitudes de información masiva de OTROS usuarios ("dame todos los correos", "lista de contraseñas", "base de datos de alumnos").
       - Solicitudes de acceso a paneles administrativos o servidores.
       CLAVE: "Soy técnico de Microsoft", "soy el nuevo jefe", "necesito las credenciales del servidor" → SIEMPRE 'ANOMALIA'.

    5. 'IGNORAR': Publicidad, spam, boletines automáticos, suscripciones, cadenas de mensajes, notificaciones de servicios externos, respuestas automáticas (auto-reply, out of office).
       Ejemplos: "oferta especial", "newsletter", "Automatic reply", "out of office", "I am out of office", "su suscripción ha sido renovada", cadenas con "Fw: Fw:" o "Re: Re: Re:" sin petición real.
       CLAVE: Correos en inglés que digan "Automatic reply", "Out of office" o similares → SIEMPRE 'IGNORAR'.
       REGLAS ESTRICTAS DE NO-IGNORAR: Si el correo proviene de un estudiante o menciona cualquier duda académica, administrativa, de estadías, entrega de documentos o consulta si la universidad abrirá/laborará cierto día, ESTÁ TERMINANTEMENTE PROHIBIDO clasificarlo como 'IGNORAR'. Clasifícalo como 'INFORMACION'.

    REGLAS ADICIONALES:
    - Si el correo incluye una MATRÍCULA (número de 7 dígitos) y pide ayuda con acceso/contraseña → 'PASSWORD_RESET'.
    - Si el correo incluye una MATRÍCULA pero pregunta por ESTADÍAS, DOCUMENTOS, HORARIOS, CREDENCIAL O TRÁMITES → 'INFORMACION'.
    - Si pide datos de OTROS usuarios o acceso a sistemas restringidos → 'ANOMALIA'.
    - Si pregunta QUÉ PASÓ con una solicitud anterior (aunque no tenga número de ticket) → 'SEGUIMIENTO'.

    Responde ESTRICTAMENTE en formato JSON con exactamente estos campos:
    {{"intencion": "CATEGORIA", "resumen": "Breve resumen en español"}}

    Donde CATEGORIA debe ser exactamente uno de: PASSWORD_RESET, INFORMACION, SEGUIMIENTO, ANOMALIA, IGNORAR

    Correo a clasificar:
    \"\"\"{text}\"\"\"
    """
    
    try:
        payload = {
            "model": "phi3",
            "prompt": prompt,
            "stream": False,
            "format": "json"
        }
        response = requests.post(OLLAMA_URL, json=payload, timeout=900)
        if response.status_code == 200:
            result = response.json()
            parsed = json.loads(result.get("response", "{}"))
            # Normalizar la intención para tolerar typos del modelo
            raw = parsed.get("intencion") or parsed.get("intención") or ""
            parsed["intencion"] = normalize_intent(raw)
            return parsed
    except Exception as e:
        print(f"Error con Ollama: {e}")
    
    return {"intencion": "INFORMACION", "resumen": "No se pudo clasificar"}

def get_relevant_kb_section(query_text):
    """
    Extrae solo las secciones relevantes del KB basándose en palabras clave.
    Devuelve (secciones_encontradas, es_vaga, matched_numbers).
    """
    query_lower = query_text.lower()

    # Mapa de palabras clave → número de sección en el archivo
    keyword_map = [
        (["club", "clubes", "deporte", "deportes", "fútbol", "futbol", "basket", "voleibol",
          "béisbol", "atletismo", "danza", "rondalla", "teatro", "canto",
          "extracurri", "extracurricular", "paraescolar", "culturales"], "7"),
        (["beca", "becas", "manutención", "movilidad", "intercambio", "mexprotec",
          "alimenticio", "apoyo", "económico"], "6"),
        (["carrera", "carreras", "tsu", "ingeniería", "ingenieria", "programa", "oferta",
          "mecátrónica", "logística", "redes", "robótica", "ia", "inteligencia artificial",
          "plásticos", "manufactura", "negocios", "inglés", "modalidad"], "4"),
        (["reinscripci", "inscripci", "baja", "constancia", "historial", "kardex",
          "revalidaci", "trámite", "tramite", "justificante"], "5"),
        (["ficha", "admisión", "admision", "examen", "nuevo ingreso", "preinscripci",
          "aspirante", "curp", "requisito", "documento", "costo de ficha"], "10"),
        (["reinscripción", "costo", "costos", "pago", "pagar", "cuota", "cuotas", "precio", "monto",
          "recibo", "cobro", "cobro-opd", "finanzas tamaulipas", "maestría", "maestria", "regularización"], "5"),
        (["credencial", "credenciales", "gafete", "identificación estudiante", "identificacion estudiante", "foto credencial"], "5,8,12"),
        (["contraseña", "password", "correo", "office", "teams", "edrp", "portal",
          "plataforma", "365", "microsoft", "edi", "sistema edi", "error en rojo"], "8"),
        (["estadía", "estadia", "servicio social", "titulación", "titulacion",
          "cedula", "cédula", "memoria técnica"], "9"),
        (["módulo 1", "modulo 1", "rectoría", "rectoria", "servicios escolares",
          "abogado", "cobranza", "jefe", "jefes", "encargado", "encargados",
          "coordinador", "rectora", "director académico"], "12"),
        (["módulo 2", "modulo 2", "médico", "medico", "servicio médico", "enfermería",
          "coordinador ingeniería"], "12"),
        (["módulo 3", "modulo 3", "académico", "academico", "tutoría", "tutoria",
          "calificaciones", "itep", "bis"], "12"),
        (["biblioteca", "libro", "préstamo", "prestamo", "uniforme", "impresión",
          "impresion", "imprimir"], "13"),
        (["vinculación", "vinculacion", "estadías empresa", "convenio", "sum",
          "sala usos"], "14"),
        (["acreditación", "acreditacion", "iso", "cacei", "caceca", "conaic",
          "calidad", "certificación"], "2"),
        (["horario", "horarios", "atención", "atencion", "contacto", "contactos", "teléfono",
          "telefono", "telefonos", "cae", "escolares", "finanzas", "directorio",
          "extensión", "extensiones", "correos oficiales"], "3"),
        (["quién", "quien", "información general", "misión", "vision", "historia",
          "ubicación", "ubicacion", "dirección", "direccion", "campus"], "1"),
    ]

    try:
        with open("kb_utm.txt", "r", encoding="utf-8") as f:
            full_kb = f.read()
    except:
        return "Información general de la UTM.", False, set()

    # Separar el KB en secciones numeradas
    import re as _re
    section_pattern = _re.compile(r'(## \d+\..*?)(?=## \d+\.|\Z)', _re.DOTALL)
    sections = section_pattern.findall(full_kb)
    section_dict = {}
    for sec in sections:
        match = _re.match(r'## (\d+)\.', sec)
        if match:
            section_dict[match.group(1)] = sec.strip()

    # Buscar qué secciones son relevantes
    matched_sections = []
    matched_numbers = set()
    for keywords, sec_num in keyword_map:
        if any(kw in query_lower for kw in keywords):
            if sec_num not in matched_numbers and sec_num in section_dict:
                matched_sections.append(section_dict[sec_num])
                matched_numbers.add(sec_num)

    if matched_sections:
        return "\n\n".join(matched_sections), False, matched_numbers
    else:
        return None, True, set()


def check_should_forward_to_escolares(query_text, has_attachments=False):
    """
    Determina si un correo clasificado como escolar SÍ requiere reenvío (Forward nativo con Alta Importancia)
    y aviso de canalización al estudiante.
    SI el estudiante solo hace una consulta informativa general (ej. costos, fechas, ubicación) donde la IA/KB le da
    solución directa sin requerir un trámite o revisión administrativa de sus documentos, NO se reenvía.
    """
    if not query_text:
        return False
    q_lower = query_text.lower()
    
    # 1. Si adjunta documentos, comprobantes de pago, fotos, actas, o certificados, SÍ o SÍ requiere intervención del personal de Servicios Escolares.
    if has_attachments or "cid:" in q_lower or "<img" in q_lower:
        return True
        
    # 2. Si en su texto solicita explícitamente una ACCIÓN o TRÁMITE administrativo o indica que envía/adjunta documentos:
    acciones_tramite = [
        "adjunto", "envió comprobante", "envio comprobante", "ya pagué", "ya pague", "anexo comprobante", "anexo recibo",
        "programar mi examen", "asignar folio", "mi folio", "confirmar mi examen", "confirmar fecha de examen",
        "solicito constancia", "ocupo constancia", "necesito constancia", "solicito kardex", "ocupo kardex", "necesito kardex",
        "solicito baja", "darme de baja", "baja temporal", "baja definitiva", "reincorporar", "reincorporacion",
        "cambio de carrera", "aclaracion de calificacion", "aclaración de calificación", "solicito certificado", "tramite de inscripcion",
        "estadia", "estadías", "practicas profesionales", "dejar documentos", "dejar unos documentos", "entregar documentos", "revision de documentos"
    ]
    if any(k in q_lower for k in acciones_tramite):
        return True
        
    # 3. Si solo es una consulta de información o pasos ("¿cómo me inscribo?", "¿qué necesito?", "¿cuánto cuesta?", "¿dónde están?"),
    # la IA ya le brinda la solución institucional en el texto y no hay razón para redireccionar/saturar al departamento.
    return False


def get_contact_html(matched_numbers, query="", has_attachments=False):
    """
    Devuelve el bloque HTML de contacto institucional según las palabras clave de la pregunta o las secciones detectadas.
    """
    q_lower = query.lower() if query else ""
    
    # 1. Reglas directas y prioritarias por palabras clave de trámites y canalización
    if any(k in q_lower for k in ["credencial", "credenciales", "lions plus", "gafete", "atencion a alumnos", "atención a alumnos"]):
        nombre = "Departamento de Atención a Alumnos (Trámite de Credencial y Lions Plus)"
        email = "atencion.alumnos@utmatamoros.edu.mx"
        modulo = "Edificio de Vinculación"
    elif any(k in q_lower for k in ["admision", "admisión", "examen diagnostico", "diagnostico", "diagnóstico", "convocatoria", "nuevo ingreso", "aspirante", "segunda fecha", "ficha", "gestión de negocios"]):
        nombre = "Departamento de Servicios Escolares (Admisiones y Examen Diagnóstico)"
        email = "servicios.escolares@utmatamoros.edu.mx"
        modulo = "Módulo 1 - Planta Alta (Tel: 868 810 7634 y 636)"
    elif any(k in q_lower for k in ["club", "clubes", "deport", "extracurricular"]):
        nombre = "Coordinación de Actividades Extracurriculares / Clubs"
        email = "atencion.alumnos@utmatamoros.edu.mx"
        modulo = "Módulo 2 - Planta Baja"
    elif any(k in q_lower for k in ["baja temporal", "baja", "reincorporar", "reincorporacion", "espacio en la carrera", "carrera que mencion", "reinscrip", "kardex", "constancia", "titulacion", "cambio de carrera", "escolares", "calificaciones", "cuatrimestre"]):
        nombre = "Servicios Escolares / Departamento de Área Académica"
        email = "servicios.escolares@utmatamoros.edu.mx"
        modulo = "Módulo 1 Planta Alta (Escolares) / Módulo 3 Planta Baja (Área Académica: dacademica@utmatamoros.edu.mx)"
    elif any(k in q_lower for k in ["estadia", "estadías", "practicas profesionales", "prácticas"]):
        nombre = "Coordinación de Estadías y Prácticas Profesionales (Ing. Irlanda Mata)"
        email = "irlanda.mata@utmatamoros.edu.mx"
        modulo = "Edificio de Vinculación"
    elif any(k in q_lower for k in ["beca", "becas", "vinculacion", "ingreso"]):
        nombre = "Departamento de Vinculación y Promoción"
        email = "vinculacion@utmatamoros.edu.mx"
        modulo = "Edificio de Vinculación"
    elif any(k in q_lower for k in ["biblioteca", "libros"]):
        nombre = "Biblioteca Universitaria"
        email = "biblioteca@utmatamoros.edu.mx"
        modulo = "Edificio de Biblioteca"
    else:
        contact_map = {
            "5":  ("Servicios Escolares", "servicios.escolares@utmatamoros.edu.mx", "Módulo 1 - Planta Alta"),
            "10": ("Servicios Escolares", "servicios.escolares@utmatamoros.edu.mx", "Módulo 1 - Planta Alta"),
            "4":  ("Servicios Escolares", "servicios.escolares@utmatamoros.edu.mx", "Módulo 1 - Planta Alta"),
            "1":  ("Servicios Escolares", "servicios.escolares@utmatamoros.edu.mx", "Módulo 1 - Planta Alta"),
            "2":  ("Servicios Escolares", "servicios.escolares@utmatamoros.edu.mx", "Módulo 1 - Planta Alta"),
            "3":  ("Servicios Escolares", "servicios.escolares@utmatamoros.edu.mx", "Módulo 1 - Planta Alta"),
            "12": ("Servicios Escolares", "servicios.escolares@utmatamoros.edu.mx", "Módulo 1 - Planta Alta"),
            "8":  ("Soporte Técnico - Departamento de Sistemas", "soporte@utmatamoros.edu.mx", "Módulo 3 - Laboratorio de Informática"),
            "6":  ("Departamento de Vinculación y Becas", "vinculacion@utmatamoros.edu.mx", "Edificio de Vinculación"),
            "14": ("Departamento de Vinculación", "vinculacion@utmatamoros.edu.mx", "Edificio de Vinculación"),
            "9":  ("Coordinación de Estadías y Prácticas (Ing. Irlanda Mata)", "irlanda.mata@utmatamoros.edu.mx", "Edificio de Vinculación"),
            "13": ("Biblioteca Universitaria", "biblioteca@utmatamoros.edu.mx", "Edificio de Biblioteca"),
            "7":  ("Actividades Extracurriculares / Clubs", "antonio.castaneda@utmatamoros.edu.mx", "Módulo 2 - Planta Baja"),
        }
        
        default = ("Servicios Escolares", "servicios.escolares@utmatamoros.edu.mx", "Módulo 1 - Planta Alta")
        # Le bajamos la prioridad a Soporte TI (8) para dar prioridad a Escolares y áreas académicas
        prioridad = ["5", "10", "4", "1", "2", "3", "12", "6", "9", "13", "14", "7", "8"]
        
        contact = default
        for sec_id in prioridad:
            if sec_id in matched_numbers and sec_id in contact_map:
                contact = contact_map[sec_id]
                break
        nombre, email, modulo = contact

    if "Credencial" in nombre or any(k in q_lower for k in ["credencial", "credenciales", "lions plus", "gafete"]):
        tip_html = f"""
        <br><br>
        <mark style="background-color: #b9f6ca; color: #000000; padding: 2px 6px; border-radius: 2px;"><b>Pasos Obligatorios para Emisión de tu Credencial:</b></mark><br>
        Para que el Departamento de Atención a Alumnos pueda crear y emitir tu credencial oficial sin demoras:<br>
        1. <b>Sube tu fotografía al Sistema EDI:</b> Ingresa a tu perfil del portal escolar <b>EDI (EDRP)</b> y carga una fotografía formal tipo credencial.<br>
        2. <b>Envía tu comprobante por correo:</b> Escribe un correo desde tu cuenta institucional a <a href="mailto:{email}" style="color: #000000; font-weight: bold; text-decoration: underline;">{email}</a> adjuntando el comprobante de pago de la Cuota Credencial ($100 MXN) e indicando tu <b>Nombre completo y Matrícula</b>.
        """
    elif any(k in q_lower for k in ["admision", "admisión", "examen diagnostico", "diagnostico", "diagnóstico", "convocatoria", "nuevo ingreso", "aspirante", "segunda fecha", "ficha", "gestión de negocios"]):
        tip_html = f"""
        <br><br>
        <mark style="background-color: #b9f6ca; color: #000000; padding: 2px 6px; border-radius: 2px;"><b>Guía Rápida para Solicitantes de Nuevo Ingreso y Examen Diagnóstico:</b></mark><br>
        Para formalizar tu registro y confirmar la fecha y hora programada para tu examen diagnóstico en la universidad:<br>
        1. <b>Pago de Ficha de Ingreso ($600 MXN):</b> Realiza el pago en el portal en línea de Finanzas del Estado (<a href="https://finanzas.tamaulipas.gob.mx/pago-de-contribuciones/cobro-opd.php" style="color: #000000; font-weight: bold; text-decoration: underline;">finanzas.tamaulipas.gob.mx</a>) seleccionando UNIVERSIDAD TECNOLOGICA DE MATAMOROS.<br>
        2. <b>Confirmación con Servicios Escolares:</b> Envía tu comprobante de pago ($600 MXN), acta de nacimiento, CURP y certificado/constancia de estudios al correo <a href="mailto:{email}" style="color: #000000; font-weight: bold; text-decoration: underline;">{email}</a> o llama al (868) 810 7634 / 636 para la asignación exacta de tu folio, fecha y aula de examen.
        """
    elif any(k in q_lower for k in ["baja temporal", "baja", "reincorporar", "reincorporacion", "espacio en la carrera", "carrera que mencion", "reinscrip"]):
        tip_html = f"""
        <br><br>
        <mark style="background-color: #fff2a8; color: #000000; padding: 2px 6px; border-radius: 2px;"><b>Instrucciones para Trámites de Baja, Reincorporación y Cupos:</b></mark><br>
        Para que los departamentos de Servicios Escolares y Área Académica revisen tu expediente en el sistema escolar y confirmen tu espacio, envía tu correo incluyendo:<br>
        1. Tu <b>Nombre Completo</b> y <b>Matrícula</b>.<br>
        2. Tu carrera anterior o cuatrimestre cursado y situación previa (ej. baja temporal).<br>
        3. La nueva carrera o trámite exacto de reincorporación que solicitas.
        """
    else:
        tip_html = f"""
        <br><br>
        <mark style="background-color: #bbdefb; color: #000000; padding: 2px 6px; border-radius: 2px;"><b>¿Cómo redactar tu mensaje al área correspondiente?</b></mark><br>
        Para que el personal administrativo o docente pueda atenderte y darte respuesta directa sin demoras, recuerda enviar tu correo desde tu cuenta <b>@utmatamoros.edu.mx</b> incluyendo siempre:<br>
        1. Tu <b>Nombre Completo</b> y <b>Matrícula</b>.<br>
        2. La carrera, cuatrimestre o grupo actual.<br>
        3. Una explicación clara y detallada de tu solicitud, duda o constancia requerida.
        """

    aviso_canalizacion_escolares = ""
    if email in ("servicios.escolares@utmatamoros.edu.mx", "irlanda.mata@utmatamoros.edu.mx") and check_should_forward_to_escolares(query, has_attachments):
        nombre_area_dest = "Servicios Escolares" if email == "servicios.escolares@utmatamoros.edu.mx" else "Coordinación de Estadías y Prácticas"
        aviso_canalizacion_escolares = f"""
        <br><br>
        <mark style="background-color: #fff2a8; color: #000000; padding: 2px 6px; border-radius: 2px;"><b>📌 AVISO DE CANALIZACIÓN OFICIAL A {nombre_area_dest.upper()}:</b></mark><br>
        Te informamos que desde el Sistema Inteligente de Soporte TI <b>hemos reenviado y canalizado tu correo original directamente a {nombre_area_dest}</b> (<a href="mailto:{email}" style="color: #000000; font-weight: bold; text-decoration: underline;">{email}</a>) para que el personal administrativo tome conocimiento de tu trámite/documentos y te brinde atención personalizada.<br>
        👉 <b>Por favor, mantente muy atento a tu bandeja de entrada y a tu carpeta de correo no deseado / SPAM</b>, ya que el área correspondiente dará seguimiento y respuesta a tu solicitud por ese medio.
        """

    return f"""
    <div style="margin-top: 16px; font-family: Arial, sans-serif; font-size: 14px; color: #000000; line-height: 1.6;">
        <mark style="background-color: #bbdefb; color: #000000; padding: 2px 6px; border-radius: 2px;"><b>Para atención directa y personalizada sobre este tema o trámite:</b></mark><br>
        Te sugerimos acudir presencialmente o enviar un correo al área oficial encargada de tu solicitud:
        <ul style="margin-top: 6px; margin-bottom: 10px;">
            <li><b>Departamento Oficial:</b> {nombre}</li>
            <li><b>Correo Electrónico:</b> <a href="mailto:{email}" style="color: #000000; font-weight: bold; text-decoration: underline;">{email}</a></li>
            <li><b>Ubicación y Horario:</b> {modulo} (Lunes a Viernes)</li>
        </ul>
        {tip_html}
        {aviso_canalizacion_escolares}
    </div>
    """


def get_kb_response(query, has_attachments=False):
    relevant_content, is_vague, matched_numbers = get_relevant_kb_section(query)

    beta_disclaimer = """
    <br><br>
    <div style="font-family: Arial, sans-serif; font-size: 13px; color: #000000; line-height: 1.6;">
        <mark style="background-color: #fff2a8; color: #000000; padding: 2px 6px; border-radius: 2px;"><b>[AVISO] Sistema en Fase de Prueba (BETA)</b></mark><br>
        Las respuestas se generan con base en la información institucional disponible y <b>pueden contener imprecisiones</b>. 
        Verifica cualquier dato importante en el portal oficial: <a href="https://www.utmatamoros.edu.mx" style="color: #000000; font-weight: bold; text-decoration: underline;">www.utmatamoros.edu.mx</a><br>
        Si detectas algún error en el sistema, repórtalo a: <a href="mailto:soporte@utmatamoros.edu.mx" style="color: #000000; font-weight: bold; text-decoration: underline;">soporte@utmatamoros.edu.mx</a>
    </div>
    """

    # Si la pregunta es vaga, devolver menú de aclaración sin llamar a Ollama
    if is_vague:
        return f"""
        <p>Gracias por contactarnos. Para poder ayudarte de manera precisa, ¿podrías indicarme sobre qué tema deseas información?</p>
        <ul>
            <li>🎓 <b>Carreras y Oferta Educativa</b> (TSU, Ingeniería, modalidades)</li>
            <li>💰 <b>Costos</b> (ficha de admisión, reinscripción, pagos)</li>
            <li>🏆 <b>Becas y Apoyos</b> (manutención, movilidad internacional, alimenticio)</li>
            <li>⚽ <b>Clubes y Actividades Extracurriculares</b> (deporte, cultura, académicos)</li>
            <li>📋 <b>Trámites Escolares</b> (constancias, bajas, revalidaciones, historial)</li>
            <li>🏛️ <b>Nuevo Ingreso</b> (requisitos, fechas, examen de admisión)</li>
            <li>💻 <b>Plataformas Digitales</b> (correo institucional, EDRP, Office 365)</li>
            <li>🎓 <b>Titulación y Estadías</b></li>
            <li>🗺️ <b>Instalaciones del Campus</b> (módulos, biblioteca, vinculación)</li>
            <li>📞 <b>Directorio de Contactos</b></li>
        </ul>
        <p>Responde indicando el número o nombre del tema y con gusto te atiendo.</p>
        {beta_disclaimer}
        """

    # Pregunta específica -> solo pasamos la sección relevante a Ollama
    prompt = f"""Eres el asistente de soporte de la Universidad Tecnológica de Matamoros (UTM).
Responde la duda usando SOLO la información del manual. Sé directo y completo.

DUDA: {query}

INSTRUCCIONES ESTRICTAS:
- Responde en español y sé claro y completo.
- Usa TEXTO PLANO solamente. PROHIBIDO usar HTML, etiquetas o formato markdown.
- Para listas usa guión al inicio de cada línea: "- item"
- Si el usuario pregunta por el directorio, teléfonos, correos o contactos, lista los departamentos, nombres y correos exactos proporcionados en el MANUAL.
- Solo si la información solicitada no aparece en absoluto en el MANUAL, di: "No cuento con esa información específica. Puedes contactar al CAE para mayor orientación: atencion.alumnos@utmatamoros.edu.mx"
- NO saludes. NO te despidas. Ve directo a la información.
- NO repitas párrafos ni frases.

MANUAL:
{relevant_content}"""

    try:
        payload = {
            "model": "qwen2.5:7b",
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_ctx": 4096,
                "num_predict": 600,
                "temperature": 0.1,
                "stop": ["\n\n\n", "DUDA:", "MANUAL:", "---"]
            }
        }
        response = requests.post(OLLAMA_URL, json=payload, timeout=600)
        if response.status_code == 200:
            raw_response = response.json().get("response", "Lo siento, hubo un error al generar la respuesta.")

            # Limpiar tokens de fin de texto de Ollama/phi3
            for token in ["<|end_of_text|>", "|end_of_text|", "<|endoftext|>", "</s>", "<s>", "<|assistant|>", "<|user|>"]:
                raw_response = raw_response.replace(token, "")
            raw_response = raw_response.replace("```html", "").replace("```", "").replace("`", "")

            # Detectar y cortar contenido repetido
            lines = raw_response.split("\n")
            seen = []
            unique_lines = []
            for line in lines:
                stripped = line.strip()
                if stripped and stripped in seen:
                    break
                unique_lines.append(line)
                if stripped:
                    seen.append(stripped)
            plain_text = "\n".join(unique_lines).strip()

            # BLINDAJE ANTI-ALUCINACIÓN / RESPUESTA PREDETERMINADA SI FALTA EL DATO:
            frases_sin_info = ["no cuento con esa información", "no tengo esa información", "no se encuentra en el manual", "no dispongo de esa información", "no aparece en el manual", "no está disponible en el manual"]
            if any(f in plain_text.lower() for f in frases_sin_info) or len(plain_text) < 30:
                contact_block = get_contact_html(matched_numbers, query, has_attachments)
                return f"""
                <p style="font-family: Arial, sans-serif; font-size: 14px; color: #111; line-height: 1.6;">
                    Hemos revisado tu consulta en la base de datos institucional; sin embargo, ese requerimiento o dato en particular necesita ser validado o gestionado directamente con el área administrativa o académica correspondiente.
                </p>
                <p style="font-family: Arial, sans-serif; font-size: 14px; color: #111; line-height: 1.6;">
                    Para evitar cualquier imprecisión y asegurar que recibas la respuesta oficial más exacta, por favor comunícate directamente con el departamento encargado siguiendo estas instrucciones:
                </p>
                {contact_block}
                {beta_disclaimer}
                """

            # Convertir texto plano a HTML limpio (sin depender de que Ollama genere HTML)
            html_lines = []
            for line in plain_text.split("\n"):
                stripped = line.strip()
                if not stripped:
                    html_lines.append("<br>")
                elif stripped.startswith("- "):
                    html_lines.append(f"<li>{stripped[2:]}</li>")
                else:
                    html_lines.append(f"<p>{stripped}</p>")
            # Envolver grupos de <li> en <ul>
            html_body = "\n".join(html_lines)
            html_body = html_body.replace("</li>\n<br>\n<li>", "</li>\n<li>")
            import re as _re
            html_body = _re.sub(r'(<li>.*?</li>\n?)+', lambda m: f"<ul>{m.group()}</ul>", html_body, flags=_re.DOTALL)

            contact_block = get_contact_html(matched_numbers, query, has_attachments)
            return f"""
            <p style="font-family: Arial, sans-serif; font-size: 14px; color: #000000;">A continuación te detallo la información institucional sobre tu consulta:</p>
            <div style="font-family: Arial, sans-serif; font-size: 14px; color: #000000; line-height: 1.6;">
            {html_body}
            </div>
            {beta_disclaimer}
            {contact_block}
            """
    except Exception as e:
        print(f"Error o timeout de Ollama al generar respuesta KB: {e}")

    # RESPALDO INSTITUCIONAL SI OLLAMA FALLA POR TIMEOUT O CARGA EN CPU:
    # En lugar de decir "Tu solicitud está siendo revisada por nuestro equipo" (que no guía al alumno),
    # devolvemos el bloque oficial de canalización del departamento que coincide con su consulta.
    contact_block = get_contact_html(matched_numbers if 'matched_numbers' in locals() else set(), query, has_attachments)
    return f"""
    <p style="font-family: Arial, sans-serif; font-size: 14px; color: #111; line-height: 1.6;">
        Hemos recibido y registrado tu consulta en nuestra plataforma institucional de atención.
    </p>
    <p style="font-family: Arial, sans-serif; font-size: 14px; color: #111; line-height: 1.6;">
        Para que puedas realizar tu trámite sin ninguna demora y recibir orientación o gestión directa por parte del personal encargado, te compartimos a continuación los datos del departamento responsable y las instrucciones para contactarles:
    </p>
    {contact_block}
    """



def send_email(token, to_email, subject, content, importance="normal"):
    url = f"https://graph.microsoft.com/v1.0/users/{SUPPORT_EMAIL}/sendMail"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Firma Institucional para TODOS los correos enviados
    firma_institucional = """
    <br><br>
    <div style="font-family: Arial, sans-serif; font-size: 11px; color: #555; text-align: justify; border-top: 2px solid #005A32; padding-top: 15px; margin-top: 30px;">
        <table width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-bottom: 15px;">
            <tr>
                <td width="200">
                    <img src="https://www.utmatamoros.edu.mx/wp-content/uploads/2017/03/logo-sitio-web-1.png" alt="UTM BIS Logo" style="max-height: 60px;">
                </td>
                <td style="font-family: Arial, sans-serif; font-size: 12px; color: #333; padding-left: 15px; border-left: 1px solid #ccc;">
                    <b>IA-Soporte TI</b><br>
                    <b>Departamento de Informática</b><br>
                    Universidad Tecnológica de Matamoros
                </td>
            </tr>
        </table>
        <div style="font-size: 9px; line-height: 1.3;">
            <b>AVISO DE PRIVACIDAD DEL CORREO ELECTRÓNICO INSTITUCIONAL DE LA UNIVERSIDAD TECNOLOGICA DE MATAMOROS</b><br>
            El contenido de este mensaje por medio electrónico incluyendo datos, texto, imágenes y/o enlaces a otros contenidos tiene el carácter de confidencial y de uso exclusivo de la universidad Tecnologica de Matamoros, así como de las personas y/o empresas a las que se dirige. No se considera oferta, propuesta o acuerdo sino hasta que sea confirmado en documento por escrito que contenga la firma autógrafa del servidor público autorizado legalmente para esta operación. El contenido es de carácter confidencial por lo cual no podrá distribuirse y/o difundirse por ningún medio sin la previa autorización del emisor original. Si usted no es el destinatario se le prohíbe su utilización total o parcial para cualquier fin. Se pone a su disposición el Aviso de privacidad del correo electrónico institucional en el siguiente enlace. <a href="https://www.utmatamoros.edu.mx" style="color: #005A32;">Aviso de Privacidad</a>
            <br><br>
            <b>PRIVACY NOTICE OF THE INSTITUTIONAL ELECTRONIC MAIL OF THE UNIVERSIDAD TECNOLOGICA DE MATAMOROS</b><br>
            The content of this message by electronic means including data, text, images and / or links to other content is confidential and of exclusive use of the Universidad Tecnologica de Matamoros, as well as of the persons and / or companies to which it is direct It is not considered an offer, proposal or agreement until it is confirmed in a written document containing the handwritten signature of the public servant legally authorized for this operation. The content is confidential, so it cannot be distributed and / or disseminated by any means without the prior authorization of the original issuer. If you are not the addressee, you are forbidden to use it totally or partially for any purpose. The Privacy Notice of institutional mail is available at the following link. <a href="https://www.utmatamoros.edu.mx" style="color: #005A32;">Privacy Notice</a>
        </div>
    </div>
    """
    
    # Concatenar firma al final del contenido
    full_content = content + firma_institucional

    payload = {
        "message": {
            "subject": subject,
            "importance": importance,
            "body": {
                "contentType": "HTML",
                "content": full_content
            },
            "toRecipients": [
                {"emailAddress": {"address": to_email}}
            ]
        }
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        return response.status_code == 202
    except Exception as e:
        print(f"Error en send_email: {e}")
        return False

def forward_email_with_attachments(token, message_id, to_email, comment_html, importance="high"):
    """Reenvía (forward) el correo original con todas sus fotografías e identificaciones adjuntas, marcándolo con ALTA IMPORTANCIA."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload_create = {
        "Comment": comment_html,
        "ToRecipients": [
            {"emailAddress": {"address": to_email}}
        ]
    }
    
    # 1. Intentar primero crear el Forward en borrador (createForward) para asignarle Alta Importancia ("importance": "high")
    url_create_fwd = f"https://graph.microsoft.com/v1.0/users/{SUPPORT_EMAIL}/messages/{message_id}/createForward"
    try:
        resp_create = requests.post(url_create_fwd, headers=headers, json=payload_create, timeout=15)
        if resp_create.status_code in (200, 201):
            draft_id = resp_create.json().get("id")
            if draft_id:
                # 2. Asignar Alta Importancia (Importance: High) al borrador reenviado
                url_patch = f"https://graph.microsoft.com/v1.0/users/{SUPPORT_EMAIL}/messages/{draft_id}"
                requests.patch(url_patch, headers=headers, json={"importance": importance}, timeout=10)
                # 3. Enviar el Forward con Alta Importancia
                url_send = f"https://graph.microsoft.com/v1.0/users/{SUPPORT_EMAIL}/messages/{draft_id}/send"
                resp_send = requests.post(url_send, headers=headers, timeout=15)
                if resp_send.status_code == 202:
                    print(f"Reenvío (Forward) con ALTA IMPORTANCIA ({importance}) exitoso a {to_email}")
                    return True
    except Exception as e:
        print(f"Fallo en flujo createForward con alta importancia ({e}), intentando forward directo...")

    # Respaldo: reenvío directo si createForward o PATCH fallan
    url = f"https://graph.microsoft.com/v1.0/users/{SUPPORT_EMAIL}/messages/{message_id}/forward"
    try:
        response = requests.post(url, headers=headers, json=payload_create, timeout=15)
        if response.status_code == 202:
            print(f"Reenvío (Forward) directo exitoso a {to_email}")
            return True
        else:
            print(f"Error al reenviar correo con adjuntos ({response.status_code}): {response.text}")
            return False
    except Exception as e:
        print(f"Excepción en forward_email_with_attachments: {e}")
        return False

def mark_as_read(token, message_id):
    url = f"https://graph.microsoft.com/v1.0/users/{SUPPORT_EMAIL}/messages/{message_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {"isRead": True}
    try:
        response = requests.patch(url, headers=headers, json=payload, timeout=10)
        if response.status_code not in (200, 204):
            print(f"¡ERROR GRAVE! No se pudo marcar como leído: {response.status_code} - {response.text}")
        else:
            print(f"Correo marcado como leído exitosamente en el servidor.")
    except Exception as e:
        print(f"Error de red en mark_as_read: {e}")

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

def handle_external_verification(token, email, classification, ticket_footer=""):
    sender = email.get("from", {}).get("emailAddress", {}).get("address")
    subject = email.get("subject", "Sin Asunto")
    body = email.get("body", {}).get("content", "") or ""

    # Extraer matrícula
    matricula = ""
    match = re.search(r'\b([0-9]{7})\b', body)
    if match:
        matricula = match.group(1)
    else:
        match = re.search(r'(?i)\b(UTM[0-9A-Z-]{8,})\b', body)
        if match:
            matricula = match.group(1)

    inst_email = f"{matricula}@utmatamoros.edu.mx" if matricula else "DESCONOCIDO"

    # Enviar confirmación simple al usuario
    conf_msg = f"""
    <p>Hemos recibido sus documentos para la verificación de identidad.</p>
    <p>Su solicitud ha sido escalada a un agente humano para su revisión y aprobación final.</p>
    <p>Por favor, espere nuestra respuesta por este medio.</p>
    {ticket_footer}
    """
    send_email(token, sender, "Documentos Recibidos - Soporte UTM", conf_msg)

    # Reenviar al administrador y soporte junto con las fotos e identificaciones del alumno
    report_body = f"""
    <h3>Verificacion de Identidad Requerida (Correo Externo)</h3>
    <p>Un usuario solicita reseteo desde correo personal y ha adjuntado documentos/fotografia de identificacion.</p>
    <p><b>PROCESO:</b> Puede revisar a continuacion la fotografia y datos en este correo reenviado. Si la identidad y matricula corresponden, apruebe con la respuesta correspondiente.</p>
    <hr>
    <b>Remitente externo:</b> {sender}<br>
    <b>Matricula detectada:</b> {matricula if matricula else 'No detectada'} ({inst_email})<br>
    <b>Asunto original:</b> {subject}<br>
    <b>Resumen IA:</b> {classification.get('resumen', 'N/A')}<br>
    <hr>
    <b>Contenido del estudiante:</b><br>{body}
    """
    message_id = email.get("id")
    fwd_admin = forward_email_with_attachments(token, message_id, ADMIN_EMAIL, report_body) if message_id else False
    if not fwd_admin:
        send_email(token, ADMIN_EMAIL, f"[REVISIÓN MANUAL] Solicitud Externa: {sender} | {inst_email}", report_body)

    fwd_soporte = forward_email_with_attachments(token, message_id, "soporte@utmatamoros.edu.mx", report_body) if message_id else False
    if not fwd_soporte:
        send_email(token, "soporte@utmatamoros.edu.mx", f"[REVISIÓN MANUAL] Solicitud Externa: {sender} | {inst_email}", report_body)

def handle_password_reset(token, email_obj=None, target_email=None, notify_email=None, ticket_footer=""):
    # Si viene del flujo principal, usamos email_obj
    if email_obj and not target_email:
        sender = email_obj["from"]["emailAddress"]["address"]
        target_email = sender
        notify = sender
    else:
        # Si es un reseteo forzado desde aprobación de administrador
        notify = notify_email if notify_email else target_email

    # ================================================================
    # GUARDIA DE SEGURIDAD (Capa de Software)
    # El Motor IA NUNCA debe ejecutar un PATCH sobre una cuenta que
    # no sea un alumno. Esta verificacion es la segunda linea de
    # defensa despues de la Administrative Unit de Entra ID.
    # Si ambas capas fallan, el sistema no ejecuta ninguna accion.
    # ================================================================
    if not is_student_email(target_email):
        alerta = f"""
        <h3>ALERTA DE SEGURIDAD - Accion bloqueada por Motor IA</h3>
        <p>Se intento ejecutar un reseteo de contrasena sobre una cuenta
        que NO cumple el patron de correo de alumno:</p>
        <p><b>Cuenta objetivo:</b> {target_email}</p>
        <p>El Motor IA se ha negado a ejecutar esta accion por politica de seguridad.
        Verifique si se trata de un intento de escalada de privilegios.</p>
        """
        send_email(token, ADMIN_EMAIL, "[SEGURIDAD] Reseteo bloqueado sobre cuenta no-alumno", alerta)
        print(f"SEGURIDAD: PATCH bloqueado. {target_email} no es cuenta de alumno.")
        return
    # ================================================================
    chars = string.ascii_letters + string.digits
    temp_password = "Utm" + "".join(random.choice(chars) for _ in range(8)) + "1!"
    
    print(f"Ejecutando reseteo directo para {target_email}...")
    
    # 1. Llamar a Graph API para forzar el cambio
    update_url = f"https://graph.microsoft.com/v1.0/users/{target_email}"
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
    
    try:
        response = requests.patch(update_url, headers=headers, json=payload, timeout=15)
    except Exception as e:
        print(f"Error en patch de reseteo: {e}")
        return
    
    # 2. Notificar al usuario basado en el resultado
    if response.status_code == 204:
        msg = f"""
        Estimado usuario,
        <br><br>
        Su solicitud ha sido aprobada. Su contraseña ha sido restablecida exitosamente. A continuación se proporcionan sus nuevas credenciales de acceso temporal:
        <br><br>
        <b>Cuenta Institucional:</b> {target_email}<br>
        <b>Contraseña Temporal:</b> <code>{temp_password}</code>
        <br><br>
        <i>Nota Importante:</i> Al iniciar sesión por primera vez con esta contraseña temporal en office.com o en su correo, Microsoft le pedirá obligatoriamente que cree una nueva contraseña personal y secreta.
        <br><br>
        <div style="background-color: #fff3cd; padding: 15px; border-left: 5px solid #ffc107; color: #856404; font-family: Arial, sans-serif; margin-top: 20px; border-radius: 4px;">
            <b style="font-size: 16px;">Requisito Obligatorio: Autenticación Multifactor (MFA)</b><br><br>
            Por políticas de seguridad de la Universidad, tras cambiar su contraseña, la plataforma le exigirá configurar un método de autenticación adicional para proteger su cuenta.<br><br>
            Le solicitamos descargar y configurar la aplicación <b>Microsoft Authenticator</b> en su dispositivo móvil (Android/iOS) para aprobar sus inicios de sesión.
        </div>
        <br><br>
        Saludos cordiales,<br>
        Soporte Técnico Automatizado UTM
        {ticket_footer}
        """
        send_email(token, notify, "Su nueva contraseña temporal - Soporte UTM", msg)
        print(f"ÉXITO: Contraseña temporal enviada a {notify}")
    else:
        print(f"ERROR Graph API ({response.status_code}): {response.text}")
        print(f"Cuenta posiblemente bloqueada o inhabilitada: {target_email}. Ejecutando protocolo de verificación de cuenta bloqueada...")
        handle_blocked_account_verification(token, email_obj, target_email, ticket_footer=ticket_footer)


def handle_blocked_account_verification(token, email_obj, target_email, ticket_id=None, ticket_footer=""):
    """
    Gestiona cuentas institucionales que se encuentran bloqueadas, inhabilitadas o comprometidas por seguridad (phishing/ataque).
    1. Si el usuario NO adjuntó la foto de su credencial estudiantil/oficial ni datos, solicita los requisitos obligatorios.
    2. Si ya envió la foto y sus datos, escala y reenvía (Forward) el caso a la Administración / Soporte con Alta Importancia
       para su verificación manual y desbloqueo, informando que una vez autorizado se procederá con el reseteo.
    """
    if not email_obj:
        return
    sender = "DESCONOCIDO"
    from_dict = email_obj.get("from")
    if isinstance(from_dict, dict):
        email_addr = from_dict.get("emailAddress")
        if isinstance(email_addr, dict):
            sender = email_addr.get("address") or "DESCONOCIDO"

    has_attachments = email_obj.get("hasAttachments", False)
    
    # También revisamos si hay imágenes o archivos inline
    raw_body = ""
    body_dict = email_obj.get("body")
    if isinstance(body_dict, dict):
        raw_body = body_dict.get("content") or ""
    raw_lower = raw_body.lower()
    is_inline_image = "cid:" in raw_lower or "<img" in raw_lower or "adjunto" in raw_lower or "anexo" in raw_lower

    if has_attachments or is_inline_image:
        print(f"[BLOQUEO DETECTADO] El usuario {sender} ({target_email}) envió documentación para verificar cuenta bloqueada. Escalando a Administración y Soporte...")
        
        # 1. Escalar y reenviar a Administración / Soporte TI (ADMIN_EMAIL / soporte@utmatamoros.edu.mx) con Alta Importancia
        if email_obj.get("id"):
            comentario_escalada = f"""
<div style="font-family: Arial, sans-serif; font-size: 14px; color: #000000; line-height: 1.6;">
    <mark style="background-color: #fff2a8; color: #000000; padding: 2px 6px; border-radius: 2px;"><b>🚨 [ESCALADA A ADMINISTRACIÓN - VERIFICACIÓN Y DESBLOQUEO DE CUENTA]</b></mark><br><br>
    Estimado Administrador / Soporte TI,<br><br>
    El Asistente Inteligente ha identificado que la cuenta estudiantil <b>{target_email}</b> se encuentra o ha sido reportada como <b>BLOQUEADA / INHABILITADA</b> por resguardo de seguridad (ej. vulneración en campaña de phishing o error EDI).<br><br>
    El solicitante ha enviado su información y adjuntado la <b>fotografía de su credencial de estudiante / identificación oficial</b> para corroborar su identidad.<br><br>
    👉 <b>ACCIÓN REQUERIDA POR ADMINISTRACIÓN:</b><br>
    Por favor, verifique la identidad del alumno con los archivos adjuntos en este correo retransmitido. Si todo está en orden, proceda a <b>desbloquear y habilitar la cuenta en Entra ID / Microsoft Graph</b>.<br>
    <b>Nota:</b> Una vez que usted desbloquee el usuario y autorice el restablecimiento en el portal, se podrá proceder con la generación y envío de su nueva contraseña temporal al alumno.<br><br>
    Atentamente,<br>
    <b>Asistente de Soporte Técnico Automatizado</b>
</div>
"""
            forward_email_with_attachments(token, email_obj["id"], ADMIN_EMAIL, comentario_escalada, importance="high")
            
        # 2. Notificar al estudiante que su documentación está siendo revisada para desbloqueo y restablecimiento
        msg_alumno = f"""
<div style="font-family: Arial, sans-serif; font-size: 14px; color: #000000; line-height: 1.6;">
    Estimado usuario,
    <br><br>
    Hemos recibido tu solicitud y la documentación (identificación/datos) adjunta para la cuenta institucional <b>{target_email}</b>.
    <br><br>
    <mark style="background-color: #fff2a8; color: #000000; padding: 2px 6px; border-radius: 2px;"><b>📌 DOCUMENTACIÓN EN VERIFICACIÓN PARA DESBLOQUEO DE CUENTA:</b></mark><br>
    Debido a que tu cuenta se encuentra temporalmente en resguardo o bloqueada por protocolos de seguridad institucional, tus documentos e información han sido turnados directamente con la <b>Administración de Soporte TI</b> para la verificación de tu identidad.
    <br><br>
    Una vez que el Administrador revise tu identificación, proceda a <b>desbloquear tu cuenta</b> en los servidores institucionales de Microsoft y autorice el restablecimiento, procederemos con la asignación y envío de tu nueva contraseña temporal de inmediato a través de este medio.
    <br><br>
    👉 <b>Por favor, mantente muy atento a tu bandeja de entrada y a tu carpeta de correo no deseado (SPAM).</b>
    <br><br>
    Atentamente,
    <br><br>
    <b>Asistente de Soporte Técnico - Departamento de Sistemas</b><br>
    Universidad Tecnológica de Matamoros
    {ticket_footer}
</div>
"""
        send_email(token, sender, "Documentación en Revisión - Desbloqueo y Restablecimiento UTM", msg_alumno, importance="high")
        if ticket_id:
            update_ticket(ticket_id, estado="ESCALADO_BLOQUEO", resolucion="Cuenta bloqueada/comprometida. Documentos turnados a Administración y Soporte TI para verificación manual y posterior desbloqueo.")
    else:
        print(f"[BLOQUEO DETECTADO] El usuario {sender} ({target_email}) no ha mandado foto de credencial. Solicitando requisitos de desbloqueo...")
        msg_requisitos = f"""
<div style="font-family: Arial, sans-serif; font-size: 14px; color: #000000; line-height: 1.6;">
    Estimado usuario,
    <br><br>
    El sistema de monitoreo ha identificado que la cuenta institucional <b>{target_email}</b> se encuentra temporalmente bloqueada, inhabilitada o en resguardo preventivo por seguridad institucional (por ejemplo, tras detectar un intento indebido de acceso o vulneración por <i>phishing</i>).
    <br><br>
    <mark style="background-color: #fff2a8; color: #000000; padding: 2px 6px; border-radius: 2px;"><b>📌 REQUISITOS OBLIGATORIOS PARA DESBLOQUEO Y RESTABLECIMIENTO:</b></mark><br>
    Para que el Administrador de Soporte TI pueda verificar formalmente tu identidad, proceder con el desbloqueo de tu usuario y autorizar el restablecimiento de tu contraseña, debes responder directamente a este correo adjuntando de forma indispensable la siguiente información:
    <ul style="margin-top: 6px; margin-bottom: 14px;">
        <li><b>Nombre Completo</b></li>
        <li><b>Matrícula</b></li>
        <li><b>Foto legible de tu credencial de estudiante de la UTM</b> (o bien, una identificación oficial vigente con fotografía como INE, Pasaporte o Licencia).</li>
    </ul>
    Una vez que adjuntes y envíes tu fotografía y datos, el Asistente transferirá de inmediato tu caso a la Administración para realizar la verificación, desbloquear tu cuenta y generarte tu nueva contraseña temporal.
    <br><br>
    Atentamente,
    <br><br>
    <b>Asistente de Soporte Técnico - Departamento de Sistemas</b><br>
    Universidad Tecnológica de Matamoros
    {ticket_footer}
</div>
"""
        send_email(token, sender, "Acción Requerida - Verificación y Desbloqueo de Cuenta UTM", msg_requisitos, importance="high")
        if ticket_id:
            update_ticket(ticket_id, estado="EN_PROCESO", resolucion="Cuenta bloqueada detectada. Se solicitaron requisitos de nombre, matrícula y foto de credencial al alumno.")

def handle_anomaly(token, email_obj, classification):
    sender = email_obj["from"]["emailAddress"]["address"]
    content = f"""
    <h3>Alerta de Anomalía detectada por IA</h3>
    <p><b>Remitente:</b> {sender}</p>
    <p><b>Resumen IA:</b> {classification.get('resumen')}</p>
    <p><b>Contenido Original:</b></p>
    <pre>{email_obj.get('bodyPreview')}</pre>
    """
    send_email(token, ADMIN_EMAIL, "[URGENTE - IA ESCALADA] Reporte de Anomalía", content, importance="high")

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
    if not text:
        return ""
    text = str(text)
    
    # 0. Cortar desde donde empiece el AVISO DE PRIVACIDAD legal o historiales institucionales repetidos
    privacy_markers = [
        "AVISO DE PRIVACIDAD DEL CORREO ELECTRÓNICO INSTITUCIONAL",
        "PRIVACY NOTICE OF THE INSTITUTIONAL ELECTRONIC MAIL",
        "AVISO DE PRIVACIDAD DEL CORREO ELECTRONICO",
        "Aviso de Privacidad del correo electrónico institucional",
        "UTM BIS Logo\tIA-Soporte TI",
        "UTM BIS Logo    IA-Soporte TI"
    ]
    for marker in privacy_markers:
        if marker in text:
            text = text.split(marker)[0]

    # 1. Eliminar por expresiones regulares disclaimers, recordatorios institucionales y firmas
    disclaimer_patterns = [
        r'(?i)Recordatorio:\s*Soporte.*?(?:inactividad\.|\n|$)',
        r'(?i)Recordatorio:\s*Soporte@utmatamoros\.edu\.mx.*?inactividad\.',
        r'(?i)PRECAUCI[OÓ]N:\s*Este correo proviene de FUERA.*?(?:seguro\.|\n|$)',
        r'(?i)\[CORREO EXTERNO\].*?(?:adjuntos\.|\n|$)',
        r'(?i)AVISO DE SEGURIDAD.*?(?:MFA\.|datos\.|contrase[ñn]a\.|\n|$)',
        r'(?i)Este correo es externo a la UTM.*?(?:seguro\.|\n|$)',
    ]
    for pattern in disclaimer_patterns:
        text = re.sub(pattern, "", text, flags=re.DOTALL)

    # 2. Eliminar línea por línea si contiene palabras clave de advertencia o firmas móviles
    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        line_str = line.strip()
        line_lower = line_str.lower()
        if any(trigger in line_lower for trigger in [
            "obtener outlook para", "enviado desde mi iphone", "enviado desde mi equipo galaxy",
            "enviado desde correo para windows", "get outlook for", "recordatorio: soporte",
            "aviso de seguridad", "precaucion: este correo proviene", "este correo es externo a la utm",
            "nunca usan whatsapp como método de verificación", "deshabilita correos por inactividad",
            "método de verificación ni solicitan", "aviso de privacidad", "privacy notice"
        ]):
            continue
        cleaned_lines.append(line)
        
    return "\n".join(cleaned_lines).strip()

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
        # Extraer remitente de forma segura
        sender = "DESCONOCIDO"
        from_dict = email.get("from")
        if isinstance(from_dict, dict):
            email_addr = from_dict.get("emailAddress")
            if isinstance(email_addr, dict):
                addr = email_addr.get("address")
                if addr:
                    sender = str(addr)

        # Extraer asunto de forma segura
        subject = email.get("subject")
        subject = str(subject) if subject is not None else ""
        
        # Extraer contenido del cuerpo de forma segura
        raw_body_content = ""
        body_dict = email.get("body")
        if isinstance(body_dict, dict):
            raw_body_content = body_dict.get("content") or ""
        body_content = sanitize_email_body(raw_body_content)

        # ================================================================
        # LÓGICA DE APROBACIÓN DE ADMINISTRADOR POR CORREO
        # ================================================================
        if sender.lower() in (ADMIN_EMAIL.lower(), "soporte@utmatamoros.edu.mx"):
            print(f"Procesando correo del Administrador: {subject}")
            body_lower = body_content.lower()
            
            # Buscar palabras clave de aprobación
            is_approval = any(word in body_lower for word in ["validado", "procede", "aceptar", "aprobado", "autorizado", "ok"])
            
            # Buscar si el correo responde a una Solicitud Externa o Revisión Manual
            if is_approval and ("solicitud externa" in subject.lower() or "revisión manual" in subject.lower()):
                print("¡Orden de aprobación detectada por el Administrador!")
                
                # Extraer correos del asunto: "...: alumno_externo@gmail.com | 2500000@utmatamoros.edu.mx"
                match = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\s*\|\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', subject)
                if match:
                    ext_email = match.group(1)
                    inst_email = match.group(2)
                    print(f"Ejecutando aprobación para: {inst_email} (Notificar a {ext_email})")
                    
                    # Llamamos a reset directamente
                    handle_password_reset(token, target_email=inst_email, notify_email=ext_email, ticket_footer="<br>Estado: Aprobado por el Administrador.")
                    
                    # Buscamos si hay tickets abiertos de este correo origen para cerrarlos
                    open_tickets = get_tickets_by_email(ext_email)
                    for t in open_tickets:
                        if t['estado'] in ('ABIERTO', 'EN_PROCESO', 'ESCALADO'):
                            update_ticket(t['ticket_id'], estado="RESUELTO", resolucion="Aprobado manualmente vía correo por Administrador.")
                            print(f"Ticket {t['ticket_id']} marcado como RESUELTO.")
                    
                    # Enviar acuse al administrador que validó
                    send_email(token, sender, f"Re: {subject}", "Orden procesada exitosamente. Contraseña enviada al alumno.")
                else:
                    print("Error: No se pudieron extraer los correos del asunto.")
                    
                mark_as_read(token, email["id"])
                continue

        if is_system_email(sender):
            print(f"Ignorando correo de sistema: {sender}")
            mark_as_read(token, email["id"])
            continue

        # Usar el asunto ya extraído de forma segura al inicio del bucle

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

        raw_body_content = ""
        body_dict = email.get("body")
        if isinstance(body_dict, dict):
            raw_body_content = body_dict.get("content") or ""
        body_preview = email.get("bodyPreview", "")
        # Usamos el cuerpo completo si existe, o el preview
        body_source = raw_body_content if len(raw_body_content) >= len(body_preview) else body_preview
        body = sanitize_email_body(body_source)
        full_content = f"Asunto: {subject}\nCuerpo: {body}"
        
        print(f"Procesando correo de: {sender}")
        
        # LOGICA DE ADMINISTRADOR: Aprobación/Rechazo de verificaciones externas
        if sender.lower() in (ADMIN_EMAIL.lower(), "soporte@utmatamoros.edu.mx") and "[VERIFICACIÓN] Reseteo Externo:" in subject:
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
                    send_email(token, sender, "Error: Falta Matrícula", "La IA no detectó la matrícula en el correo original. Por favor responde de nuevo con: APROBAR [MATRÍCULA] (ej. APROBAR 2010145)")
                    mark_as_read(token, email["id"])
                    continue
                    
                print(f"ADMIN APROBÓ el reseteo para {inst_email} vía {target_email}")
                mock_email = {"from": {"emailAddress": {"address": inst_email}}}
                handle_password_reset(token, mock_email, notify_email=target_email)
                send_email(token, sender, f"[OK] Aprobado: {inst_email}", f"El enlace de reseteo fue generado y enviado exitosamente al correo externo: {target_email}")
            elif "rechazar" in body.lower() or "denegado" in body.lower():
                print(f"ADMIN RECHAZÓ el reseteo para {target_email}")
                send_email(token, target_email, "Verificación Rechazada - Soporte UTM", "Estimado usuario, su solicitud de reseteo de contraseña ha sido rechazada debido a que los documentos proporcionados no son válidos o no coinciden con nuestros registros. Por favor, acuda presencialmente al departamento.")
                send_email(token, sender, f"❌ Rechazado: {target_email}", "Se ha notificado al usuario externo sobre el rechazo de su solicitud.")
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

        # DETECCIÓN DE FALLAS EN LABORATORIOS / SOPORTE TÉCNICO FÍSICO / HARDWARE
        body_subject_lower = f"{subject} {full_content}".lower()
        lab_hw_triggers = [
            "laboratorio", "laboratorios", "taller", "talleres", "inventor", "solidworks", "autocad",
            "proyector", "proyecto descompuesto", "proyector descompuesto", "descompuest", "roto", "dañado",
            "las computadoras", "las pc", "equipo del laboratorio", "cable de red", "aire acondicionado",
            "falla física", "instalar programa", "instalar software", "mantenimiento al laboratorio",
            "falla en el salón", "falla en el salon", "equipo no enciende", "pc no enciende",
            "computadora no enciende", "pc no sirve", "no hay internet en el salón", "software de inventor"
        ]
        if any(trigger in body_subject_lower for trigger in lab_hw_triggers):
            print(f"REDIRECCIÓN TÉCNICA: {sender} reportó falla de laboratorio/hardware. Redireccionando a soporte@utmatamoros.edu.mx...")
            
            # Verificar si el correo ya iba dirigido a soporte@utmatamoros.edu.mx (en To o Cc)
            all_recipients = []
            for r in (email.get("toRecipients", []) + email.get("ccRecipients", [])):
                if isinstance(r, dict):
                    addr = r.get("emailAddress", {}).get("address", "")
                    if addr:
                        all_recipients.append(addr.lower())
            
            already_to_official_support = any("soporte@utmatamoros.edu.mx" in r for r in all_recipients)
            
            if not already_to_official_support:
                print(f"CANALIZACIÓN IA: El reporte iba SOLO a la IA. Reenviando copia del caso de infraestructura a soporte@utmatamoros.edu.mx...")
                copy_subject = f"[Canalización IA - Falla Técnica] {subject}"
                copy_content = f"""
                <h3>Reporte de Falla en Laboratorio / Infraestructura canalizado por Inteligencia Artificial</h3>
                <p><b>Remitente original:</b> {sender}</p>
                <p><b>Asunto original:</b> {subject}</p>
                <div style="background-color: #f9f9f9; border-left: 4px solid #005A32; padding: 12px; margin: 12px 0;">
                    <b>Cuerpo del reporte:</b><br><br>
                    {body_content or 'Sin texto en el cuerpo.'}
                </div>
                <p style="font-size: 11px; color: #666;">
                    * Nota del sistema: Este correo fue recibido en soporte-ia@utmatamoros.edu.mx y canalizado automáticamente al departamento presencial de Informática/Sistemas para su atención oportuna.
                </p>
                """
                send_email(token, "soporte@utmatamoros.edu.mx", copy_subject, copy_content)
                
                aviso_canalizacion = """
                <div style="background-color: #e8f5e9; border-left: 4px solid #2e7d32; padding: 12px; margin: 12px 0; font-size: 13px; color: #1b5e20;">
                    <b>[OK] Información enviada al Departamento de Informática</b><br><br>
                    Te informamos que <b>ya hemos reenviado automáticamente toda la información de tu reporte al Departamento de Informática / Sistemas (soporte@utmatamoros.edu.mx)</b> para que el personal técnico correspondiente tome conocimiento y pueda atender la incidencia en el laboratorio o módulo indicado.
                </div>
                """
            else:
                print(f"CANALIZACIÓN IA: El correo ya iba dirigido también a soporte@utmatamoros.edu.mx. No se enviará copia duplicada al departamento.")
                aviso_canalizacion = """
                <div style="background-color: #e8f5e9; border-left: 4px solid #2e7d32; padding: 12px; margin: 12px 0; font-size: 13px; color: #1b5e20;">
                    <b>[OK] Reporte recibido en el Departamento de Informática</b><br><br>
                    Hemos verificado que en tu correo ya incluiste como destinatario al <b>Departamento de Informática / Sistemas (soporte@utmatamoros.edu.mx)</b>. El personal técnico asignado en el Módulo 3 ya ha recibido tu solicitud directamente en su buzón.
                </div>
                """

            redirect_msg = f"""
            <p>Estimado usuario / profesor,</p>
            <p>Hemos recibido su reporte relacionado con fallas técnicas, mantenimiento o requerimientos en laboratorios/instalaciones del campus.</p>
            {aviso_canalizacion}
            <div style="background-color: #fff8e1; border-left: 4px solid #f0a500; padding: 14px; margin: 14px 0; font-size: 13px; color: #5a4000;">
                <b>[AVISO] Recordatorio sobre el Alcance de Soporte IA</b><br><br>
                Le recordamos que la dirección <b>soporte-ia@utmatamoros.edu.mx</b> es un asistente automatizado con Inteligencia Artificial diseñado exclusivamente para:
                <ul style="margin-top: 6px; margin-bottom: 6px;">
                    <li>ℹ️ <b>Información general</b> de la universidad (carreras, admisiones, trámites, becas)</li>
                    <li>🔑 <b>Restablecimiento de contraseñas</b> institucionales (Office 365 / Teams / EDRP)</li>
                    <li>🎓 <b>Orientación y apoyo estudiantil</b> en consultas académicas frecuentes</li>
                </ul>
                Para futuras fallas en computadoras de laboratorios, proyectores, red/internet en salones, instalación de software especializado o problemas físicos de hardware, le sugerimos enviar su reporte directamente al correo oficial del Departamento de Informática / Sistemas:
                <br><br>
                👉 <a href="mailto:soporte@utmatamoros.edu.mx" style="font-size: 15px; font-weight: bold; color: #003366;">soporte@utmatamoros.edu.mx</a>
                <br><i>(Atención presencial: Módulo 3, Lunes a Viernes de 8:00 AM a 5:00 PM con el Ing. Tomás Gilberto Cantú González)</i>
            </div>
            <br>
            <p style="font-size: 12px; color: #666;">Atentamente,<br><b>Asistente IA de Información y Apoyo Estudiantil UTM</b></p>
            """
            send_email(token, sender, "Re: Reporte de Laboratorio / Soporte Técnico Físico - Canalización UTM", redirect_msg)
            mark_as_read(token, email["id"])
            continue

        # REGLA DE USUARIO: Desactivado el envío automático de estado/historial de ticket para evitar confusión o loops con historiales en correos respondidos.
        # (El flujo continúa a verificar si es un saludo o clasificar la consulta para dar orientación)

        # GUARDIA DE SALUDOS Y TEXTOS CORTOS (Evitar alucinaciones de historial o reseteo en saludos como "Hola")
        texto_limpio_eval = re.sub(r'(?i)^(asunto:\s*|cuerpo:\s*)+', '', full_content).strip()
        texto_solo_palabras = re.sub(r'[^\w\s]', '', texto_limpio_eval).strip().lower()
        
        saludos_cortos = {
            "", "hola", "buenos dias", "buenos días", "buenas tardes", "buenas noches",
            "buenas", "que tal", "qué tal", "saludos", "hi", "hello", "ayuda", "info",
            "informacion", "información", "hola soporte", "buenas noches soporte",
            "buenos dias soporte", "buenas tardes soporte", "hola buenas tardes",
            "hola buenos dias", "hola buenos días", "buen dia", "buen día"
        }
        
        if texto_solo_palabras in saludos_cortos or len(texto_solo_palabras) < 8:
            print(f"SALUDO DETECTADO de {sender}: '{texto_solo_palabras}'. Enviando bienvenida y guía de uso...")
            bienvenida_msg = """
            <p style="font-family: Arial, sans-serif; font-size: 14px; color: #111; line-height: 1.6;">¡Hola, <b>León de la UTM</b>! [UTM]</p>
            <p style="font-family: Arial, sans-serif; font-size: 14px; color: #111; line-height: 1.6;">Bienvenido al <b>Asistente Inteligente Institucional 24/7</b> de la Universidad Tecnológica de Matamoros.</p>
            <p style="font-family: Arial, sans-serif; font-size: 14px; color: #111; line-height: 1.6;">Hemos recibido tu mensaje. Para poder darte la orientación exacta y ayudarte de manera oportuna, por favor <b>descríbenos tu duda o solicitud con tus propias palabras respondiendo a este correo</b>.</p>
            <p style="font-family: Arial, sans-serif; font-size: 14px; color: #000; font-weight: bold; margin-top: 18px;">💡 ¿En qué temas podemos apoyarte de inmediato?</p>
            <ul style="font-family: Arial, sans-serif; font-size: 14px; color: #111; line-height: 1.6;">
                <li><b>📄 Trámites y Cuotas Escolares:</b> Requisitos para constancias de estudio, certificados, titulación e historiales en <b>Servicios Escolares</b>, así como la consulta de cuotas oficiales y la guía para generar recibos de pago en línea.</li>
                <li><b>🔄 Bajas y Reinscripciones:</b> Orientación sobre procesos escolares y canalización con el <b>Departamento del Área Académica</b> correspondiente.</li>
                <li><b>🔑 Restablecimiento de Contraseñas:</b> Soporte automatizado para la recuperación de accesos a <b>Correo Institucional, Office 365</b> y asistencia paso a paso para el portal escolar <b>EDI (EDRP)</b>.</li>
                <li><b>📍 Directorio y Servicios Universitarios:</b> Ubicaciones, horarios y extensiones actualizadas de Biblioteca, Centro de Atención Estudiantil (CAE), Servicio Médico, Actividades Extracurriculares y Departamento de Informática.</li>
            </ul>
            <p style="font-family: Arial, sans-serif; font-size: 13px; color: #333; line-height: 1.6; margin-top: 22px;">Quedamos atentos a tu respuesta para atenderte.</p>
            """
            send_email(token, sender, "Bienvenido al Asistente Inteligente UTM - ¿En qué podemos ayudarte?", bienvenida_msg)
            mark_as_read(token, email["id"])
            continue

        classification = classify_intent(full_content)
        
        # LÓGICA DE PRIORIDAD: Si es respuesta a verificación, forzar PASSWORD_RESET
        if "re: acción requerida" in subject.lower() or "verificación de identidad" in subject.lower():
            classification = {"intencion": "PASSWORD_RESET", "resumen": "Respuesta a verificación de identidad externa."}
        
        print(f"Respuesta Raw de IA: {classification}")
        intent = normalize_intent(classification.get("intencion") or classification.get("intención") or "")
        
        # GUARDIA DE REDIRECCIÓN DE TRÁMITES Y CONSULTAS GENERALES (Para evitar que la IA confunda "credencial", "beca" o "inscripción" con PASSWORD_RESET o SEGUIMIENTO)
        texto_limpio_para_guardia = f"{subject} {full_content}".lower()
        palabras_tramites_o_kb = [
            "credencial", "gafete", "identificacion", "identificación", "beca", "becas",
            "club", "clubes", "inscripción", "inscripcion", "reincorporación", "reincorporacion",
            "cuota", "cuotas", "pago", "pagos", "baja", "constancia", "certificado", "kardex", "historial",
            "estadia", "estadía", "estadias", "estadías", "práctica", "practica", "prácticas", "practicas",
            "documento", "documentos", "dejar documentos", "laborando", "trabajando", "horario", "viernes", "mañana"
        ]
        if intent in ("PASSWORD_RESET", "SEGUIMIENTO") and any(p in texto_limpio_para_guardia for p in palabras_tramites_o_kb):
            palabras_claras_password = ["contraseña", "contrasena", "password", "clave", "nip", "código temporal", "codigo temporal"]
            if not any(pc in texto_limpio_para_guardia for pc in palabras_claras_password):
                print(f"REDIRECCIÓN DE TRÁMITE/KB: La IA clasificó erróneamente en {intent} una consulta sobre trámite ('{subject} / {full_content[:30]}'). Redirigiendo automáticamente a INFORMACION.")
                intent = "INFORMACION"

        if not intent:
            print(f"No se pudo clasificar el correo de {sender}. Saltando...")
            continue

        print(f"Intención detectada: {intent}")
        
        # Crear ticket SOLO para intenciones que requieren seguimiento
        resumen_ia = classification.get("resumen", "Sin resumen")
        
        if intent in ("PASSWORD_RESET", "ANOMALIA", "SEGUIMIENTO"):
            ticket_estado = "ESCALADO" if intent == "ANOMALIA" else "ABIERTO"
            ticket_id = create_ticket(sender, subject, intent, resumen_ia, ticket_estado)
            print(f"Ticket creado: {ticket_id}")
            
            # Pie de ticket para incluir en respuestas con seguimiento
            ticket_footer = f"""
            <br><hr style="border-top: 1px solid #ccc;">
            <p style="font-size: 11px; color: #666;">
                <b>Ticket de seguimiento:</b> {ticket_id}<br>
                Guarde este número para consultar el estado de su solicitud en cualquier momento 
                respondiendo a este correo con su número de ticket.
            </p>
            """
        
        if intent == "SEGUIMIENTO":
            # REGLA ESTRICTA DE USUARIO: NUNCA responder con historial de seguimiento ni tabla de solicitudes previas.
            # Convertir a orientación/bienvenida para que el alumno describa qué trámite o duda tiene realmente.
            print(f"SEGUIMIENTO detectado de {sender}. Por instrucción del usuario, NO se envía historial. Tratando como orientación general.")
            bienvenida_msg = f"""
            <p style="font-family: Arial, sans-serif; font-size: 14px; color: #111; line-height: 1.6;">¡Hola, <b>León de la UTM</b>! [UTM]</p>
            <p style="font-family: Arial, sans-serif; font-size: 14px; color: #111; line-height: 1.6;">Hemos recibido tu mensaje en el <b>Asistente Inteligente Institucional 24/7</b>.</p>
            <p style="font-family: Arial, sans-serif; font-size: 14px; color: #111; line-height: 1.6;">Para poder atenderte y darte la solución o guía oficial exacta que necesitas, por favor <b>descríbenos tu duda, trámite o problema con tus propias palabras respondiendo a este correo</b>.</p>
            <p style="font-family: Arial, sans-serif; font-size: 14px; color: #000; font-weight: bold; margin-top: 18px;">💡 ¿En qué temas podemos apoyarte?</p>
            <ul style="font-family: Arial, sans-serif; font-size: 14px; color: #111; line-height: 1.6;">
                <li><b>📄 Trámites y Cuotas Escolares:</b> Requisitos para constancias de estudio, certificados, titulación e historiales en <b>Servicios Escolares</b>, así como la consulta de cuotas oficiales y la guía para generar recibos de pago en línea.</li>
                <li><b>🔄 Bajas y Reinscripciones:</b> Orientación sobre procesos escolares y canalización con el <b>Departamento del Área Académica</b> correspondiente.</li>
                <li><b>🔑 Restablecimiento de Contraseñas:</b> Soporte automatizado para la recuperación de accesos a <b>Correo Institucional, Office 365</b> y asistencia paso a paso para el portal escolar <b>EDI (EDRP)</b>.</li>
                <li><b>📍 Directorio y Servicios Universitarios:</b> Ubicaciones, horarios y extensiones actualizadas de Biblioteca, Centro de Atención Estudiantil (CAE), Servicio Médico, Actividades Extracurriculares y Departamento de Informática.</li>
            </ul>
            <p style="font-family: Arial, sans-serif; font-size: 13px; color: #333; line-height: 1.6; margin-top: 22px;">Quedamos atentos a tu respuesta por este mismo medio para ayudarte de inmediato.</p>
            {ticket_footer}
            """
            send_email(token, sender, "Asistente Inteligente UTM - ¿En qué podemos ayudarte?", bienvenida_msg)
            log_conversacion(sender, subject, intent, resumen_ia, full_content, bienvenida_msg)
            update_ticket(ticket_id, estado="RESUELTO", resolucion="Atendido con orientación sin enviar historial por regla de usuario.")
        elif intent == "PASSWORD_RESET":
            # GUARDIA DE AMBIGÜEDAD Y ESPECIFICIDAD
            # Si el usuario NO menciona explícitamente palabras claras de contraseña/clave
            # (ej. "¿Cómo puedo restablecer mi office 365?", "ayuda con office/teams/word"),
            # NO damos por sentado el reseteo y le pedimos especificar mostrándole lo que puede solicitar.
            texto_evaluar = f"{subject} {full_content}".lower()
            palabras_claras_password = [
                "contraseña", "contrasena", "password", "clave", "nip",
                "olvide mi correo", "olvidé mi correo", "no puedo entrar a mi correo",
                "no puedo entrar al correo", "no puedo abrir mi correo", "no puedo iniciar sesión",
                "no puedo entrar a mi cuenta", "cuenta bloqueada", "correo bloqueado",
                "recuperar contraseña", "recuperar mi contraseña", "restablecer contraseña",
                "restablecer mi contraseña", "cambiar contraseña", "código temporal", "codigo temporal"
            ]
            es_explicito_password = any(p in texto_evaluar for p in palabras_claras_password)

            if not es_explicito_password:
                print(f"AMBIGÜEDAD DETECTADA en {sender}: '{subject}' / '{full_content}'. Solicitando especificación.")
                msg_aclaracion = f"""
                <p style="font-family: Arial, sans-serif; font-size: 14px; color: #111; line-height: 1.6;">¡Hola, <b>León de la UTM</b>! [UTM]</p>
                <p style="font-family: Arial, sans-serif; font-size: 14px; color: #111; line-height: 1.6;">Hemos recibido tu consulta, pero para darte la ayuda exacta y no modificar tus accesos por error, necesitamos que <b>especifiques un poco mejor</b> tu solicitud.</p>
                <p style="font-family: Arial, sans-serif; font-size: 14px; color: #000; font-weight: bold; margin-top: 16px;">💡 Por favor indícanos cuál de estas opciones necesitas exactamente:</p>
                <ul style="font-family: Arial, sans-serif; font-size: 14px; color: #111; line-height: 1.6;">
                    <li><b>🔑 Restablecer tu CONTRASEÑA del Correo Institucional / Office 365:</b><br>Si olvidaste tu clave de acceso, respóndenos a este correo escribiendo textualmente: <i>"Necesito restablecer mi contraseña"</i> junto con tu <b>Nombre completo y Matrícula</b>.</li>
                    <li><b>💻 Acceso y uso de Office 365 Web (Word, Excel, PowerPoint, Teams):</b><br>Si tu consulta es sobre el uso de la paquetería Office, te recordamos que tu licencia estudiantil es <b>Office 365 A1 (versión Web / Online)</b>. Puedes utilizar Word, Excel, PowerPoint y Teams directamente desde tu navegador en <b>www.office.com</b> iniciando sesión con tu correo institucional <b>@utmatamoros.edu.mx</b>. (Nota: Al ser licencia A1 Web, no incluye ni permite descargar instaladores de paquetería de escritorio en PC o Mac).</li>
                    <li><b>📍 Trámites Escolares, Cuotas o Portal EDI (EDRP):</b><br>Si necesitas constancias, historiales, información de pagos o recuperar tu acceso escolar en el portal EDI, descríbenos tu situación para enviarte la guía oficial paso a paso.</li>
                </ul>
                <p style="font-family: Arial, sans-serif; font-size: 13px; color: #333; line-height: 1.6; margin-top: 20px;">Quedamos atentos a tu respuesta por este mismo medio para brindarte la solución oportuna.</p>
                {ticket_footer}
                """
                send_email(token, sender, "Aclaración de solicitud - Asistente Inteligente UTM", msg_aclaracion)
                log_conversacion(sender, subject, intent, resumen_ia, full_content, msg_aclaracion)
                update_ticket(ticket_id, estado="RESUELTO", resolucion="Solicitud ambigua de Office/software. Se solicitó especificación al alumno.")
                mark_as_read(token, email["id"])
                continue

            # INTERCEPCIÓN PROACTIVA DE BLOQUEO / COMPROMISO DE CUENTA
            palabras_bloqueo = ["bloquead", "inhabilitad", "comprometid", "vulnerad", "phishing", "enlace malicioso", "error en rojo", "cuenta ya no está activa", "desbloque"]
            es_reporte_bloqueo = any(b in texto_evaluar for b in palabras_bloqueo)

            if es_reporte_bloqueo:
                print(f"[INTERCEPCIÓN BLOQUEO] El usuario {sender} reporta cuenta bloqueada o comprometida. Iniciando verificación...")
                # Buscar si mencionó su cuenta institucional específica en el texto o usar el remitente
                target_blq = sender
                for palabra in full_content.split():
                    if "@utmatamoros.edu.mx" in palabra.lower():
                        target_blq = palabra.strip(".,;:()[]\"'")
                        break
                handle_blocked_account_verification(token, email, target_blq, ticket_id=ticket_id, ticket_footer=ticket_footer)
                mark_as_read(token, email["id"])
                continue

            # SEGURIDAD: Si es alumno con correo institucional, proceder directo
            if is_student_email(sender):
                print(f"Generando link de reseteo para alumno: {sender}")
                update_ticket(ticket_id, estado="EN_PROCESO")
                handle_password_reset(token, email, ticket_footer=ticket_footer)
                update_ticket(ticket_id, estado="RESUELTO", resolucion="Contraseña temporal generada y enviada al alumno.")
            elif sender.lower().endswith("@utmatamoros.edu.mx"):
                # Cuenta institucional pero NO es alumno (maestro/administrativo)
                print(f"REDIRIGIDO: {sender} es cuenta institucional no-alumno (staff/docente).")
                msg = f"""
                Estimado usuario,
                <br><br>
                El Motor de Soporte Automatizado está diseñado exclusivamente para atender 
                solicitudes de restablecimiento de contraseña de <b>cuentas de alumnos</b>.
                <br><br>
                Su cuenta ha sido identificada como personal <b>docente o administrativo</b>, 
                por lo que su solicitud debe ser atendida directamente por el equipo de Soporte Técnico.
                <br><br>
                Por favor, envíe su solicitud al siguiente correo:
                <br>
                <b><a href="mailto:soporte@utmatamoros.edu.mx">soporte@utmatamoros.edu.mx</a></b>
                <br><br>
                Su caso será atendido por un técnico de forma personalizada.
                {ticket_footer}
                """
                send_email(token, sender, "Solicitud Transferida - Soporte UTM", msg, importance="high")
                log_conversacion(sender, subject, intent, resumen_ia, full_content, msg)
                update_ticket(ticket_id, estado="CERRADO", resolucion="Cuenta no-alumno. Redirigido a soporte humano.")
            else:
                # Si es correo externo (Gmail, Hotmail, etc.), verificar si ya envió los requisitos
                has_attachments = email.get("hasAttachments", False)
                # También revisamos si hay mención de imágenes en el cuerpo HTML
                raw_body = ""
                body_dict_temp = email.get("body")
                if isinstance(body_dict_temp, dict):
                    raw_body = body_dict_temp.get("content") or ""
                raw_body_lower = raw_body.lower()
                is_inline_image = "cid:" in raw_body_lower or "<img" in raw_body_lower
                
                print(f"DEBUG: Correo externo de {sender} | Adjuntos: {has_attachments} | Imagen Inline: {is_inline_image}")

                # Buscamos patrones de matrícula y nombre en el cuerpo
                has_matricula = any(char.isdigit() for char in body) and len(body) > 5
                
                if (has_attachments or is_inline_image) and has_matricula:
                    print(f"REVISIÓN MANUAL REQUERIDA: Datos recibidos de correo externo {sender}")
                    handle_external_verification(token, email, classification, ticket_footer=ticket_footer)
                    update_ticket(ticket_id, estado="ESCALADO", resolucion="Documentos recibidos. Esperando aprobación del administrador.")
                else:
                    print(f"SOLICITANDO REQUISITOS: Correo externo {sender}")
                    msg = f"""
                    Estimado usuario, para procesar una solicitud de contraseña desde un correo <b>personal</b>, 
                    por seguridad es obligatorio que responda a este correo adjuntando la siguiente información:
                    <br><br>
                    1. <b>Nombre Completo</b><br>
                    2. <b>Matrícula</b><br>
                    3. <b>Foto de tu credencial de estudiante</b> (o identificación oficial INE/Pasaporte).
                    <br><br>
                    Una vez recibida y validada la información, procederemos con su solicitud.
                    {ticket_footer}
                    """
                    send_email(token, sender, "Acción Requerida - Verificación de Identidad UTM", msg)
                    log_conversacion(sender, subject, intent, resumen_ia, full_content, msg)
                    update_ticket(ticket_id, estado="EN_PROCESO", resolucion="Esperando documentos de verificación del usuario externo.")
        elif intent == "ANOMALIA":
            handle_anomaly(token, email, classification)
            update_ticket(ticket_id, estado="ESCALADO", resolucion="Anomalía escalada al administrador.")
        elif intent == "IGNORAR":
            # No genera ticket ni registro, simplemente se ignora
            print(f"IA decidió IGNORAR este correo: {sender}")
        else:
            # INFORMACION: Respuesta usando la base de conocimientos (sin ticket, solo registro FAQ)
            log_consulta(sender, subject, resumen_ia)
            has_att = email.get("hasAttachments", False)
            content = get_kb_response(full_content, has_attachments=has_att)
            send_email(token, sender, "Re: Consulta de Soporte UTM", content)
            log_conversacion(sender, subject, intent, resumen_ia, full_content, content)
            print(f"CONSULTA registrada para análisis FAQ: {resumen_ia}")
            
            # REENVÍO AUTOMÁTICO (FORWARD) A DEPARTAMENTO ESCOLAR O ADMINISTRATIVO SI NO ES DE SOPORTE TI:
            q_fwd = f"{subject} {full_content}".lower()
            dept_destino = None
            dept_nombre = None
            
            # Nota: Por solicitud del administrador, el reenvío automático (Forward) se activa ÚNICAMENTE para Servicios Escolares
            # y SOLO si el usuario adjunta documentos o requiere una gestión/trámite que no se resuelve con pura información:
            if any(k in q_fwd for k in ["admision", "admisión", "examen diagnostico", "diagnostico", "diagnóstico", "convocatoria", "nuevo ingreso", "aspirante", "segunda fecha", "ficha", "gestión de negocios", "baja temporal", "baja", "reincorporar", "reincorporacion", "espacio en la carrera", "carrera que mencion", "reinscrip", "kardex", "constancia", "titulacion", "cambio de carrera", "escolares", "calificaciones"]):
                if check_should_forward_to_escolares(full_content, has_att):
                    dept_destino = "servicios.escolares@utmatamoros.edu.mx"
                    dept_nombre = "Departamento de Servicios Escolares"
                else:
                    print(f"[ACLARACIÓN] Consulta de {sender} resuelta con información de la IA. No requiere reenvío a Servicios Escolares.")
            elif any(k in q_fwd for k in ["estadia", "estadía", "estadias", "estadías", "practicas profesionales", "prácticas", "dejar documentos", "entregar documentos"]):
                if check_should_forward_to_escolares(full_content, has_att):
                    dept_destino = "irlanda.mata@utmatamoros.edu.mx"
                    dept_nombre = "Coordinación de Estadías y Prácticas Profesionales"
                else:
                    print(f"[ACLARACIÓN] Consulta de {sender} resuelta con información de Estadías. No requiere reenvío.")
            # Los siguientes departamentos se habilitarán paulatinamente en el futuro:
            # elif any(k in q_fwd for k in ["credencial", "credenciales", "lions plus", "gafete", "club", "clubes", "deport", "extracurricular"]):
            #     dept_destino = "atencion.alumnos@utmatamoros.edu.mx"
            # elif any(k in q_fwd for k in ["biblioteca", "libros"]):
            #     dept_destino = "biblioteca@utmatamoros.edu.mx"
                
            if dept_destino and email.get("id"):
                print(f"Canalizando y reenviando correo de {sender} automáticamente a {dept_destino}...")
                comentario_fwd = f"""
<div style="font-family: Arial, sans-serif; font-size: 14px; color: #000000; line-height: 1.6;">
    <b>[CANALIZACIÓN AUTOMÁTICA DE SOPORTE UTM -> {dept_nombre.upper()}]</b><br><br>
    Estimado personal del <b>{dept_nombre}</b>,<br><br>
    Se reenvía (Forward) el correo original del usuario/aspirante <b>{sender}</b> recibido en el portal de Soporte Técnico para su oportuna atención y seguimiento directo por parte de su área.<br><br>
    El Asistente Inteligente ya ha orientado y proporcionado los datos de contacto de su departamento al solicitante.<br><br>
    Atentamente,<br>
    <b>Asistente de Soporte Técnico - Departamento de Sistemas</b><br>
    Universidad Tecnológica de Matamoros
</div>
"""
                forward_email_with_attachments(token, email["id"], dept_destino, comentario_fwd)
        
        try:
            mark_as_read(token, email["id"])
        except Exception:
            pass

if __name__ == "__main__":
    import traceback
    while True:
        try:
            process_emails()
        except Exception as e:
            print(f"Error en el orquestador: {e}")
            traceback.print_exc()
        
        print("Esperando 30 segundos...")
        time.sleep(30)
