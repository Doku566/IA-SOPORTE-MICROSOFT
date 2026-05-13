import os
import requests
from msal import ConfidentialClientApplication

# Carga de variables desde el entorno o gestor de secretos
TENANT_ID = os.getenv("TENANT_ID", "EJEMPLO_TENANT")
CLIENT_ID = os.getenv("CLIENT_ID", "EJEMPLO_CLIENT")
CLIENT_SECRET = os.getenv("CLIENT_SECRET", "EJEMPLO_SECRET")
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", "soporte-ia@ejemplo.edu.mx")

SCOPES = ["https://graph.microsoft.com/.default"]

def get_access_token():
    """Genera token OAuth 2.0 (Client Credentials) para Microsoft Graph API."""
    app = ConfidentialClientApplication(
        CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}",
        client_credential=CLIENT_SECRET
    )
    result = app.acquire_token_for_client(scopes=SCOPES)
    return result.get("access_token")

def fetch_unread_emails(token):
    """Obtiene correos no leídos del buzón de soporte mediante peticiones REST a Graph."""
    url = f"https://graph.microsoft.com/v1.0/users/{SUPPORT_EMAIL}/mailFolders/inbox/messages?$filter=isRead eq false"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get("value", [])
    return []

def send_email(token, to_email, subject, content):
    """Envía correo de respuesta automatizada formateado en HTML."""
    url = f"https://graph.microsoft.com/v1.0/users/{SUPPORT_EMAIL}/sendMail"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "message": {
            "subject": subject,
            "body": {"contentType": "HTML", "content": content},
            "toRecipients": [{"emailAddress": {"address": to_email}}]
        }
    }
    requests.post(url, headers=headers, json=payload)

def handle_password_reset(token, user_id):
    """Flujo de restablecimiento de contraseña temporal con directiva MFA forzada."""
    # La contraseña temporal se genera dinámicamente en tiempo de ejecución.
    # NUNCA hardcodear contraseñas en el código fuente, ni como ejemplos.
    # Patrón de generación recomendado:
    #   import secrets, string
    #   chars = string.ascii_letters + string.digits + "!@#$%*"
    #   new_password = "Pfx" + "".join(secrets.choice(chars) for _ in range(10)) + "1!"
    new_password = None  # Se genera en tiempo de ejecución
    
    url = f"https://graph.microsoft.com/v1.0/users/{user_id}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "passwordProfile": {
            "forceChangePasswordNextSignIn": True,
            "password": new_password  # Asignar contraseña generada dinámicamente
        }
    }
    # requests.patch(url, headers=headers, json=payload) # Comentado en ejemplo público
    return new_password
