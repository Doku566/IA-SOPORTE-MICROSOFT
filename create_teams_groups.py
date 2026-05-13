import os
import time
import requests
import csv
import unicodedata
from dotenv import load_dotenv
from msal import ConfidentialClientApplication

# Cargar variables de entorno
load_dotenv()

TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
SUPPORT_EMAIL_TARGET = "soporte@utmatamoros.edu.mx"

def normalize_text(text):
    """Elimina acentos y convierte a minúsculas para comparaciones robustas."""
    if not text: return ""
    text = unicodedata.normalize('NFD', text)
    text = "".join([c for c in text if unicodedata.category(c) != 'Mn'])
    return text.lower().strip()

def get_access_token():
    app = ConfidentialClientApplication(
        CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}",
        client_credential=CLIENT_SECRET
    )
    result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    return result.get("access_token")

def get_user_id(token, email):
    # Primero intentar buscar en el CSV cargado (más rápido)
    # Si no, usar Graph API
    url = f"https://graph.microsoft.com/v1.0/users/{email}"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get("id")
    return None

def load_directory():
    """Carga el CSV exportado y crea un mapa de nombres normalizados."""
    directory = {}
    try:
        with open("directorio_utm_completo.csv", "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = normalize_text(row["displayName"])
                upn = row["userPrincipalName"]
                uid = row["id"]
                
                # Priorizar cuentas que no parezcan de alumnos (sin matrícula numérica pura)
                # O si ya hay una, preferir la que tenga Title 'Docente' o similar
                if name not in directory:
                    directory[name] = (uid, upn)
                else:
                    # Si ya existe, ver si la nueva parece más "oficial" (sin números)
                    existing_upn = directory[name][1]
                    if any(char.isdigit() for char in existing_upn.split("@")[0]) and not any(char.isdigit() for char in upn.split("@")[0]):
                        directory[name] = (uid, upn)
    except Exception as e:
        print(f"Error cargando directorio: {e}")
    return directory

def group_exists(token, display_name):
    safe_name = display_name.replace("'", "''")
    url = f"https://graph.microsoft.com/v1.0/groups?$filter=displayName eq '{safe_name}'"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        value = response.json().get("value", [])
        if len(value) > 0:
            return value[0].get("id")
    return None

def create_group(token, display_name, owners_ids):
    nickname = "".join(e for e in display_name if e.isalnum()).lower()
    
    url = "https://graph.microsoft.com/v1.0/groups"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    owners_bind = [f"https://graph.microsoft.com/v1.0/users/{uid}" for uid in owners_ids if uid]

    payload = {
        "description": f"Grupo de clase: {display_name}",
        "displayName": display_name,
        "groupTypes": ["Unified"],
        "mailEnabled": True,
        "mailNickname": nickname[:64],
        "securityEnabled": False,
        "owners@odata.bind": owners_bind
    }
    
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 201:
        return response.json().get("id")
    elif response.status_code == 400 and "already exists" in response.text:
        return group_exists(token, display_name)
    return None

def create_team(token, group_id, display_name):
    url = f"https://graph.microsoft.com/v1.0/groups/{group_id}/team"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "template@odata.bind": "https://graph.microsoft.com/v1.0/teamsTemplates('standard')"
    }
    
    for i in range(1, 12):
        response = requests.put(url, headers=headers, json=payload)
        if response.status_code in [201, 202, 409]:
            print(f"  [OK] Team verificado para '{display_name}'")
            return True
        elif response.status_code == 404:
            time.sleep(10)
        else:
            print(f"  [!] Error activando Team: {response.status_code} - {response.text}")
            break
    return False

def main():
    print("Iniciando proceso...")
    token = get_access_token()
    if not token: return

    # Cargar base de datos local
    print("Cargando base de datos local de usuarios...")
    directory = load_directory()
    print(f"Directorio cargado con {len(directory)} nombres únicos.")

    # Obtener ID de soporte
    support_id = get_user_id(token, SUPPORT_EMAIL_TARGET) or get_user_id(token, os.getenv("SUPPORT_EMAIL"))

    # Leer grupos a crear
    with open("grupos_clase.txt", "r", encoding="utf-8") as f:
        lines = f.readlines()

    print(f"Procesando {len(lines)} grupos...")

    for line in lines[:5]:
        if not line.strip(): continue
        
        parts = line.strip().split("\t")
        if len(parts) < 3:
            parts = [p.strip() for p in line.strip().split("  ") if p.strip()]
            if len(parts) < 3: continue

        group_name = parts[0]
        teacher_name = parts[1]
        prefect_email = parts[2]

        print(f"\n--- {group_name} ---")
        
        # 1. Buscar Docente en DB local
        teacher_norm = normalize_text(teacher_name)
        teacher_id = None
        teacher_upn = "No encontrado"
        
        if teacher_norm in directory:
            teacher_id, teacher_upn = directory[teacher_norm]
        else:
            # Búsqueda parcial si el nombre es largo
            found_partial = False
            for d_name in directory:
                if teacher_norm in d_name or d_name in teacher_norm:
                    teacher_id, teacher_upn = directory[d_name]
                    found_partial = True
                    break
        
        if teacher_id:
            print(f"  Docente: {teacher_name} -> {teacher_upn}")
        else:
            print(f"  AVISO: Docente '{teacher_name}' no encontrado en la base de datos.")

        # 2. Buscar Prefecto (usualmente por email directo)
        prefect_id = get_user_id(token, prefect_email)
        
        # 3. Propietarios
        owners_ids = list(set([uid for uid in [teacher_id, prefect_id, support_id] if uid]))

        # 4. Crear/Obtener Grupo
        group_id = create_group(token, group_name, owners_ids)
        if group_id:
            print(f"  Grupo ID: {group_id} (Owners: {len(owners_ids)})")
            create_team(token, group_id, group_name)
        
        time.sleep(1) # Pausa mínima

if __name__ == "__main__":
    main()
