import os
import sys
import re
import random
import string
import requests
import sqlite3

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from orchestrator import get_access_token, send_email, DB_NAME

def get_ticket(ticket_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT correo_origen FROM tickets WHERE ticket_id = ?", (ticket_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def mark_ticket_resolved(ticket_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE tickets SET estado = 'RESUELTO', resolucion = 'Aprobado manualmente y contraseña reseteada' WHERE ticket_id = ?", (ticket_id,))
    conn.commit()
    conn.close()

def main():
    if len(sys.argv) < 3:
        print("Uso: python aprobar_ticket.py [TICKET_ID] [MATRICULA]")
        print("Ejemplo: python aprobar_ticket.py UTM-85305 1234567")
        sys.exit(1)
        
    ticket_id = sys.argv[1]
    matricula = sys.argv[2]
    
    external_email = get_ticket(ticket_id)
    if not external_email:
        print(f"Error: Ticket {ticket_id} no encontrado en la base de datos.")
        sys.exit(1)
        
    cuenta_objetivo = f"{matricula}@utmatamoros.edu.mx"
    
    print("Obteniendo token de acceso...")
    token = get_access_token()
    if not token:
        print("Error: No se pudo obtener el token.")
        sys.exit(1)
        
    # Generar contraseña temporal
    chars = string.ascii_letters + string.digits
    temp_password = "Utm" + "".join(random.choice(chars) for _ in range(8)) + "1!"
    
    print(f"Reseteando contraseña para la cuenta institucional: {cuenta_objetivo}")
    update_url = f"https://graph.microsoft.com/v1.0/users/{cuenta_objetivo}"
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
        print(f"Error de red al intentar el reseteo: {e}")
        sys.exit(1)
        
    if response.status_code == 204:
        print("¡Reseteo exitoso en Microsoft 365!")
        
        # Enviar correo al externo
        msg = f"""
        Estimado usuario,
        <br><br>
        Su identidad ha sido verificada y aprobada por el administrador. Su contraseña ha sido restablecida exitosamente.
        <br><br>
        <b>Cuenta Institucional:</b> {cuenta_objetivo}<br>
        <b>Contraseña Temporal:</b> <code>{temp_password}</code>
        <br><br>
        <i>Nota Importante:</i> Ingrese a office.com con estas credenciales. El sistema le pedirá obligatoriamente que cree una nueva contraseña.
        <br><br>
        <hr style="border-top: 1px solid #ccc;">
        <p style="font-size: 11px; color: #666;">
            <b>Ticket de seguimiento:</b> {ticket_id}<br>
            Estado: RESUELTO
        </p>
        """
        success = send_email(token, external_email, "Su nueva contraseña temporal - Soporte UTM", msg)
        if success:
            print(f"Se ha enviado el correo a {external_email}")
            mark_ticket_resolved(ticket_id)
            print(f"El ticket {ticket_id} ha sido marcado como RESUELTO en la base de datos.")
        else:
            print("Error al enviar el correo con la nueva contraseña.")
    else:
        print(f"Error de Graph API ({response.status_code}): {response.text}")

if __name__ == "__main__":
    main()
