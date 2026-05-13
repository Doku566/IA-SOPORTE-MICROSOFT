import os
import sqlite3
import requests
from datetime import datetime
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv
from msal import ConfidentialClientApplication

load_dotenv()

app = FastAPI()

# Config
TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL")
DB_NAME = "soporte_utm.db"

# MS Graph Scopes
SCOPES = ["https://graph.microsoft.com/.default"]

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

def get_access_token():
    msal_app = ConfidentialClientApplication(
        CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}",
        client_credential=CLIENT_SECRET
    )
    result = msal_app.acquire_token_for_client(scopes=SCOPES)
    if "access_token" in result:
        return result["access_token"]
    return None

def validate_token(token_uuid):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT correo_institucional, fecha_expiracion, usado FROM reset_tokens WHERE token_uuid = ?",
        (token_uuid,)
    )
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return None, "Token inválido."
    
    email, expiration_str, usado = row
    
    # BLINDAJE DE SEGURIDAD: Solo alumnos
    if not is_student_email(email):
        print(f"ALERTA DE SEGURIDAD: Intento de acceso a reseteo para cuenta NO ESTUDIANTIL: {email}")
        return None, "Acceso Denegado: Esta herramienta es exclusiva para estudiantes."

    expiration = datetime.strptime(expiration_str, "%Y-%m-%d %H:%M:%S")
    
    if usado:
        return None, "Este enlace ya ha sido utilizado."
    if datetime.now() > expiration:
        return None, "El enlace ha expirado (límite de 15 minutos)."
    
    return email, None

@app.get("/reset", response_class=HTMLResponse)
async def reset_page(token: str):
    email, error = validate_token(token)
    
    if error:
        return f"""
        <html>
            <head>
                <title>Error - Soporte UTM</title>
                <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap" rel="stylesheet">
                <style>
                    body {{ font-family: 'Inter', sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; background: #f4f7f6; margin: 0; }}
                    .card {{ background: white; padding: 2rem; border-radius: 12px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); text-align: center; max-width: 400px; }}
                    h2 {{ color: #e74c3c; }}
                    p {{ color: #555; }}
                </style>
            </head>
            <body>
                <div class="card">
                    <h2>Error de Acceso</h2>
                    <p>{error}</p>
                    <a href="mailto:soporte@utmatamoros.edu.mx" style="color: #0078d4;">Contactar a Soporte</a>
                </div>
            </body>
        </html>
        """

    return f"""
    <html>
        <head>
            <title>Restablecer Contraseña - UTM</title>
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap" rel="stylesheet">
            <style>
                body {{ font-family: 'Inter', sans-serif; background: linear-gradient(135deg, #004b23 0%, #007236 100%); display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
                .card {{ background: white; padding: 2.5rem; border-radius: 16px; box-shadow: 0 20px 40px rgba(0,0,0,0.2); width: 100%; max-width: 400px; }}
                .logo {{ text-align: center; margin-bottom: 1.5rem; }}
                h2 {{ color: #333; margin-top: 0; text-align: center; }}
                .email-hint {{ background: #f0f4f8; padding: 0.75rem; border-radius: 8px; font-size: 0.9rem; color: #4a5568; margin-bottom: 1.5rem; text-align: center; }}
                label {{ display: block; margin-bottom: 0.5rem; font-weight: 600; color: #4a5568; }}
                input {{ width: 100%; padding: 0.75rem; border: 1px solid #cbd5e0; border-radius: 8px; margin-bottom: 1.5rem; box-sizing: border-box; font-size: 1rem; }}
                button {{ width: 100%; padding: 0.85rem; border: none; border-radius: 8px; background: #007236; color: white; font-weight: 600; font-size: 1rem; cursor: pointer; transition: background 0.3s; }}
                button:hover {{ background: #004b23; }}
                .footer {{ margin-top: 1.5rem; text-align: center; font-size: 0.8rem; color: #718096; }}
            </style>
        </head>
        <body>
            <div class="card">
                <div class="logo"><img src="https://www.utmatamoros.edu.mx/wp-content/uploads/2021/04/Logo-UTM-2021.png" alt="UTM Logo" style="height: 60px;"></div>
                <h2>Nueva Contraseña</h2>
                <div class="email-hint">Cuenta: <b>{email}</b></div>
                <form action="/ejecutar_reset" method="post">
                    <input type="hidden" name="token" value="{token}">
                    <label>Contraseña Nueva</label>
                    <input type="password" name="nueva_password" required minlength="8" placeholder="Mínimo 8 caracteres">
                    <button type="submit">Actualizar Contraseña</button>
                </form>
                <div class="footer">Sistema de Soporte Automatizado v1.0</div>
            </div>
        </body>
    </html>
    """

@app.post("/ejecutar_reset")
async def execute_reset(token: str = Form(...), nueva_password: str = Form(...)):
    email, error = validate_token(token)
    if error:
        raise HTTPException(status_code=400, detail=error)
    
    # Validar complejidad básica (ejemplo simple)
    if not any(c.isupper() for c in nueva_password) or not any(c.isdigit() for c in nueva_password):
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos una mayúscula y un número.")
    
    # Llamar a Graph API para cambiar contraseña
    access_token = get_access_token()
    if not access_token:
        raise HTTPException(status_code=500, detail="Error de conexión con Microsoft Cloud.")
    
    # URL para resetear contraseña en Entra ID
    # Requiere UserAuthenticationMethod.ReadWrite.All
    url = f"https://graph.microsoft.com/v1.0/users/{email}/authentication/passwordMethods"
    # Nota: El flujo exacto puede variar según si es admin o usuario normal.
    # Para reset forzado se suele usar PATCH a /users/{id} con passwordProfile
    
    update_url = f"https://graph.microsoft.com/v1.0/users/{email}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "passwordProfile": {
            "forceChangePasswordNextSignIn": False,
            "password": nueva_password
        }
    }
    
    response = requests.patch(update_url, headers=headers, json=payload)
    
    if response.status_code == 204:
        # Marcar token como usado
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("UPDATE reset_tokens SET usado = 1 WHERE token_uuid = ?", (token,))
        conn.commit()
        conn.close()
        
        return {"mensaje": "Contraseña actualizada con éxito. Ya puedes iniciar sesión."}
    else:
        print(f"Error Graph API: {response.status_code} - {response.text}")
        raise HTTPException(status_code=500, detail="No se pudo actualizar la contraseña en el servidor de Microsoft.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
