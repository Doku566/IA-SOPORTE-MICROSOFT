import time
import requests
import secrets
import string
from app.services.graph_service import GraphService

class AdminService:
    def __init__(self):
        self.graph = GraphService()

    def generate_random_password(self, length=12):
        alphabet = string.ascii_letters + string.digits + "@#$!%*?&"
        while True:
            password = ''.join(secrets.choice(alphabet) for i in range(length))
            if (any(c.islower() for c in password)
                and any(c.isupper() for c in password)
                and any(c.isdigit() for c in password)
                and any(c in "@#$!%*?&" for c in password)):
                return password

    def reset_password(self, email: str) -> tuple[bool, str]:
        print(f"[ADMIN API] Solicitando reset de contraseña para: {email}...")
        
        admin_emails = []
        if email.lower() in admin_emails or email.lower().startswith("admin"):
            print(f"[ADMIN API] SEGURIDAD: reset bloqueado para cuenta administrativa ({email}).")
            return False, "Error de Seguridad: No esta permitido procesar restablecimientos automaticos para cuentas administrativas."
        
        new_password = self.generate_random_password()
        
        try:
            headers = self.graph._get_headers()
            url = f"https://graph.microsoft.com/v1.0/users/{email}"
            
            payload = {
                "passwordProfile": {
                    "forceChangePasswordNextSignIn": True,
                    "password": new_password
                }
            }
            
            response = requests.patch(url, headers=headers, json=payload)
            
            if response.status_code == 204:
                print(f"   [ADMIN API] Contrasena reseteada satisfactoriamente para {email}")
                return True, new_password
            else:
                error_msg = f"Graph API Error {response.status_code}: {response.text}"
                print(f"   [ADMIN API] Fallo: {error_msg}")
                return False, error_msg
                
        except Exception as e:
            print(f"   [ADMIN API] Error durante el proceso: {e}")
            return False, str(e)
