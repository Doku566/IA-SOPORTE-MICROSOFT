import os
import requests
from dotenv import load_dotenv
from msal import ConfidentialClientApplication

load_dotenv()

TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

def get_access_token():
    app = ConfidentialClientApplication(
        CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}",
        client_credential=CLIENT_SECRET
    )
    result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    return result.get("access_token")

def export_users():
    token = get_access_token()
    if not token:
        print("Error al obtener token.")
        return

    users = []
    url = "https://graph.microsoft.com/v1.0/users?$select=displayName,userPrincipalName,id,jobTitle,department&$top=999"
    headers = {"Authorization": f"Bearer {token}"}

    print("Descargando usuarios del directorio...")
    while url:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            users.extend(data.get("value", []))
            url = data.get("@odata.nextLink")
            print(f"  Descargados {len(users)} usuarios...")
        else:
            print(f"Error: {response.status_code} - {response.text}")
            break

    # Guardar en CSV
    import csv
    with open("directorio_utm_completo.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["displayName", "userPrincipalName", "id", "jobTitle", "department"])
        writer.writeheader()
        for user in users:
            writer.writerow({
                "displayName": user.get("displayName"),
                "userPrincipalName": user.get("userPrincipalName"),
                "id": user.get("id"),
                "jobTitle": user.get("jobTitle"),
                "department": user.get("department")
            })
    
    print(f"Exportación finalizada. {len(users)} usuarios guardados en 'directorio_utm_completo.csv'.")

if __name__ == "__main__":
    export_users()
