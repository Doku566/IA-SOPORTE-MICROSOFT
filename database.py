import sqlite3
import os
import random
import string

DB_NAME = "soporte_utm.db"

def generate_ticket_id():
    """Genera un ID de ticket único en formato UTM-XXXXX (5 dígitos aleatorios)."""
    num = random.randint(10000, 99999)
    return f"UTM-{num}"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Table for tracking email tickets
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id TEXT UNIQUE,
        correo_origen TEXT NOT NULL,
        fecha_recibido DATETIME DEFAULT CURRENT_TIMESTAMP,
        fecha_actualizado DATETIME DEFAULT CURRENT_TIMESTAMP,
        fecha_cerrado DATETIME,
        asunto TEXT,
        intencion TEXT, -- 'INFORMACION', 'PASSWORD_RESET', 'ANOMALIA', 'IGNORAR'
        resumen TEXT,
        estado TEXT DEFAULT 'ABIERTO', -- 'ABIERTO', 'EN_PROCESO', 'RESUELTO', 'ESCALADO', 'CERRADO'
        resolucion TEXT
    )
    ''')

    # Migrar tabla existente si le faltan columnas nuevas
    try:
        cursor.execute("SELECT ticket_id FROM tickets LIMIT 1")
    except sqlite3.OperationalError:
        # Las columnas no existen, agregarlas
        for col_def in [
            "ticket_id TEXT",
            "fecha_actualizado DATETIME DEFAULT CURRENT_TIMESTAMP",
            "fecha_cerrado DATETIME",
            "asunto TEXT",
            "resumen TEXT",
            "resolucion TEXT"
        ]:
            col_name = col_def.split()[0]
            try:
                cursor.execute(f"ALTER TABLE tickets ADD COLUMN {col_def}")
                print(f"  Columna '{col_name}' agregada a tickets.")
            except sqlite3.OperationalError:
                pass  # La columna ya existe
        
        # Crear índice único para ticket_id (SQLite no soporta UNIQUE en ALTER TABLE)
        try:
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_ticket_id ON tickets(ticket_id)")
        except sqlite3.OperationalError:
            pass
        
        conn.commit()  # Commit para que las columnas existan antes de usarlas
        
        # Actualizar estado 'PROCESADO' -> 'RESUELTO' y 'PENDIENTE' -> 'ABIERTO'
        cursor.execute("UPDATE tickets SET estado = 'RESUELTO' WHERE estado = 'PROCESADO'")
        cursor.execute("UPDATE tickets SET estado = 'ABIERTO' WHERE estado = 'PENDIENTE'")
        
        # Asignar ticket_id a registros existentes que no lo tengan
        cursor.execute("SELECT id FROM tickets WHERE ticket_id IS NULL")
        rows = cursor.fetchall()
        for row in rows:
            tid = generate_ticket_id()
            cursor.execute("UPDATE tickets SET ticket_id = ? WHERE id = ?", (tid, row[0]))
        if rows:
            print(f"  {len(rows)} tickets existentes recibieron ticket_id retroactivamente.")

    # Table for password reset tokens
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS reset_tokens (
        token_uuid TEXT PRIMARY KEY,
        correo_institucional TEXT NOT NULL,
        correo_personal TEXT NOT NULL,
        fecha_expiracion DATETIME NOT NULL,
        usado BOOLEAN DEFAULT 0
    )
    ''')

    # Table for OTP verification tokens (External email identity validation)
    # SECURITY: OTP hashes are stored, never the plain-text code.
    # Expiry enforced at application level. 10-minute TTL.
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS otp_tokens (
        correo_origen TEXT PRIMARY KEY,
        otp_hash TEXT NOT NULL,
        expiry DATETIME NOT NULL
    )
    ''')

    # Tabla de consultas informativas (para análisis de preguntas frecuentes)
    # No genera ticket, solo registra qué preguntan los usuarios.
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS consultas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        correo_origen TEXT NOT NULL,
        fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
        asunto TEXT,
        resumen TEXT
    )
    ''')

    # Tabla de conversaciones completas para retroalimentación y auditoría de la IA
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS conversaciones_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        correo_origen TEXT NOT NULL,
        fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
        asunto TEXT,
        intencion TEXT,
        resumen TEXT,
        cuerpo_recibido TEXT,
        respuesta_enviada TEXT
    )
    ''')

    conn.commit()
    conn.close()
    print(f"Base de datos {DB_NAME} inicializada con éxito.")

def create_ticket(correo, asunto, intencion, resumen, estado="ABIERTO"):
    """Crea un nuevo ticket y retorna el ticket_id generado."""
    ticket_id = generate_ticket_id()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Asegurar unicidad del ticket_id
    for _ in range(10):
        try:
            cursor.execute(
                """INSERT INTO tickets 
                   (ticket_id, correo_origen, asunto, intencion, resumen, estado) 
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (ticket_id, correo, asunto, intencion, resumen, estado)
            )
            break
        except sqlite3.IntegrityError:
            ticket_id = generate_ticket_id()
    conn.commit()
    conn.close()
    return ticket_id

def update_ticket(ticket_id, estado=None, resolucion=None):
    """Actualiza el estado y/o resolución de un ticket."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    if estado and resolucion:
        cursor.execute(
            "UPDATE tickets SET estado = ?, resolucion = ?, fecha_actualizado = CURRENT_TIMESTAMP, fecha_cerrado = CASE WHEN ? IN ('RESUELTO','CERRADO') THEN CURRENT_TIMESTAMP ELSE fecha_cerrado END WHERE ticket_id = ?",
            (estado, resolucion, estado, ticket_id)
        )
    elif estado:
        cursor.execute(
            "UPDATE tickets SET estado = ?, fecha_actualizado = CURRENT_TIMESTAMP, fecha_cerrado = CASE WHEN ? IN ('RESUELTO','CERRADO') THEN CURRENT_TIMESTAMP ELSE fecha_cerrado END WHERE ticket_id = ?",
            (estado, estado, ticket_id)
        )
    elif resolucion:
        cursor.execute(
            "UPDATE tickets SET resolucion = ?, fecha_actualizado = CURRENT_TIMESTAMP WHERE ticket_id = ?",
            (resolucion, ticket_id)
        )
    conn.commit()
    conn.close()

def get_ticket_status(ticket_id):
    """Busca un ticket por su ID y retorna sus datos o None."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT ticket_id, correo_origen, fecha_recibido, asunto, intencion, resumen, estado, resolucion, fecha_actualizado, fecha_cerrado FROM tickets WHERE ticket_id = ?",
        (ticket_id,)
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "ticket_id": row[0],
            "correo": row[1],
            "fecha": row[2],
            "asunto": row[3],
            "intencion": row[4],
            "resumen": row[5],
            "estado": row[6],
            "resolucion": row[7],
            "fecha_actualizado": row[8],
            "fecha_cerrado": row[9]
        }
    return None

def get_tickets_by_email(correo, limit=5):
    """Retorna los últimos N tickets de un correo."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT ticket_id, fecha_recibido, intencion, resumen, estado FROM tickets WHERE correo_origen = ? ORDER BY fecha_recibido DESC LIMIT ?",
        (correo, limit)
    )
    rows = cursor.fetchall()
    conn.close()
    return [{"ticket_id": r[0], "fecha": r[1], "intencion": r[2], "resumen": r[3], "estado": r[4]} for r in rows]

def log_consulta(correo, asunto, resumen):
    """Registra una consulta informativa para análisis de preguntas frecuentes."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO consultas (correo_origen, asunto, resumen) VALUES (?, ?, ?)",
        (correo, asunto, resumen)
    )
    conn.commit()
    conn.close()

def get_top_consultas(limit=10):
    """Retorna las consultas más frecuentes agrupadas por resumen."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT resumen, COUNT(*) as total FROM consultas GROUP BY resumen ORDER BY total DESC LIMIT ?",
        (limit,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [{"resumen": r[0], "total": r[1]} for r in rows]

def log_conversacion(correo, asunto, intencion, resumen, cuerpo_recibido, respuesta_enviada):
    """Guarda cada conversación completa en la base de datos y en un archivo JSONL para retroalimentación."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO conversaciones_log (correo_origen, asunto, intencion, resumen, cuerpo_recibido, respuesta_enviada) VALUES (?, ?, ?, ?, ?, ?)",
            (correo, asunto, intencion, resumen, cuerpo_recibido, respuesta_enviada)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error al guardar en BD conversaciones_log: {e}")

    try:
        import json
        from datetime import datetime
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "conversaciones_log.jsonl")
        entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "correo": correo,
            "asunto": asunto,
            "intencion": intencion,
            "resumen": resumen,
            "cuerpo_recibido": cuerpo_recibido,
            "respuesta_enviada": respuesta_enviada
        }
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"Error al escribir en conversaciones_log.jsonl: {e}")

if __name__ == "__main__":
    init_db()
