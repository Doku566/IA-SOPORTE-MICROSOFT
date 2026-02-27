import sys
import os

sys.path.append(os.getcwd())

from app.core.config import settings
from app.services.graph_service import GraphService

class EmailService:
    def __init__(self):
        self.graph_service = GraphService()
        self.smtp_user = settings.GRAPH_USER_EMAIL 
        print(f"EmailService inicializado para: {self.smtp_user}")

    def send_email(self, to_email: str, subject: str, body: str) -> bool:
        try:
            print(f"DTO: {to_email} | SUBJ: {subject} | BODY_LEN: {len(body)}")
            print(f"Intentando enviar correo a '{to_email}' via Graph API...")
            return self.graph_service.send_email(to_email, subject, body)
        except Exception as e:
            print(f"Error enviando correo: {e}")
            return False

    def check_inbox(self, criteria=None) -> list:
        try:
            messages = self.graph_service.check_inbox()
            return messages
        except Exception as e:
            print(f"Error revisando inbox: {e}")
            return []

    def send_otp_email(self, to_email: str, otp_code: str, student_name: str = "Estudiante"):
        subject = "Codigo de Verificacion - Soporte Tecnico UT Matamoros"
        body = f"""Hola {student_name},

Hemos recibido una solicitud para restablecer tu contraseña institucional.

Tu código de verificación es: {otp_code}

Por favor, responde a este correo con el código para continuar.
Este código expira en 10 minutos.

Si no solicitaste este cambio, ignora este correo.

Atentamente,
Soporte Tecnico
"""
        return self.send_email(to_email, subject, body)

    def send_rejection_email(self, to_email: str, reason: str):
        subject = "Actualizacion sobre tu solicitud de soporte"
        body = f"""Hola,

No pudimos procesar tu solicitud automáticamente.
Motivo: {reason}

Por favor, verifica tus datos o acude al departamento correspondiente.

Atentamente,
Soporte Tecnico
"""
        return self.send_email(to_email, subject, body)

    def send_data_request_email(self, to_email: str):
        subject = "Soporte Tecnico - Se requiere informacion adicional"
        body = """Hola,

Para ayudarte a restablecer tu contraseña, necesito que respondas a este correo llenando la siguiente plantilla:

------------------------------------------------
Nombre Completo: [ESCRIBE AQUI TU NOMBRE]
Matrícula: [ESCRIBE AQUI TU MATRICULA]
Carrera: [ESCRIBE AQUI TU CARRERA]
Solicitud: Restablecer Contraseña
------------------------------------------------

Una vez que respondas con estos datos, validaremos tu identidad.

Atentamente,
Soporte Tecnico
"""
        return self.send_email(to_email, subject, body)
