import sqlite3
import os

DB_NAME = "soporte_utm.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Table for tracking email tickets
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        correo_origen TEXT NOT NULL,
        fecha_recibido DATETIME DEFAULT CURRENT_TIMESTAMP,
        intencion TEXT, -- 'INFORMACION', 'PASSWORD_RESET', 'ANOMALIA'
        estado TEXT DEFAULT 'PENDIENTE' -- 'PROCESADO', 'ESCALADO'
    )
    ''')

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

    conn.commit()
    conn.close()
    print(f"Base de datos {DB_NAME} inicializada con éxito.")

if __name__ == "__main__":
    init_db()
