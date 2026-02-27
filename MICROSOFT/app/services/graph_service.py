import msal
import requests
from app.core.config import settings

class GraphService:
    def __init__(self):
        self.client_id = settings.AZURE_CLIENT_ID
        self.client_secret = settings.AZURE_CLIENT_SECRET
        self.tenant_id = settings.AZURE_TENANT_ID
        self.user_email = settings.GRAPH_USER_EMAIL or settings.SMTP_USER
        
        self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        self.scope = ["https://graph.microsoft.com/.default"]
        
        self.app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=self.authority,
            client_credential=self.client_secret
        )

    def _get_headers(self):
        result = self.app.acquire_token_silent(self.scope, account=None)
        if not result:
            result = self.app.acquire_token_for_client(scopes=self.scope)
        
        if "access_token" in result:
            return {
                "Authorization": f"Bearer {result['access_token']}",
                "Content-Type": "application/json"
            }
        else:
            raise Exception(f"Error autenticando con Graph API: {result.get('error_description')}")

    def send_email(self, to_email: str, subject: str, body: str):
        headers = self._get_headers()
        url = f"https://graph.microsoft.com/v1.0/users/{self.user_email}/sendMail"
        
        email_msg = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "Text",
                    "content": body
                },
                "toRecipients": [
                    {
                        "emailAddress": {
                            "address": to_email
                        }
                    }
                ]
            },
            "saveToSentItems": "true"
        }
        
        response = requests.post(url, headers=headers, json=email_msg)
        if response.status_code == 202:
            print(f"[Graph] Correo enviado a {to_email}")
            return True
        else:
            print(f"[Graph] Error enviando correo: {response.status_code} - {response.text}")
            return False

    def check_folder(self, folder_id="Inbox", unread_only=True) -> list:
        headers = self._get_headers()
        url = f"https://graph.microsoft.com/v1.0/users/{self.user_email}/mailFolders/{folder_id}/messages?$top=50"
        
        if unread_only:
            url += "&$filter=isRead eq false"
        
        try:
            response = requests.get(url, headers=headers)
            messages = []
            
            if response.status_code == 200:
                data = response.json()
                for item in data.get('value', []):
                    from_email = "Desconocido"
                    if 'from' in item and 'emailAddress' in item['from']:
                        from_email = item['from']['emailAddress']['address']
                        
                    msg = {
                        'id': item['id'],
                        'from': from_email,
                        'subject': item.get('subject', '(Sin Asunto)'),
                        'body': item.get('bodyPreview', '')
                    }
                    messages.append(msg)
            else:
                print(f"[Graph] Error leyendo {folder_id}: {response.status_code}")
                
            return messages
        except Exception as e:
            print(f"[Graph] Excepcion leyendo carpeta: {e}")
            return []

    def check_inbox(self, unread_only=True) -> list:
        return self.check_folder("Inbox", unread_only)

    def mark_as_read(self, message_id: str):
        import urllib.parse
        encoded_id = urllib.parse.quote(message_id)
        
        headers = self._get_headers()
        url = f"https://graph.microsoft.com/v1.0/users/{self.user_email}/messages/{encoded_id}"
        payload = {"isRead": True}
        
        response = requests.patch(url, headers=headers, json=payload)
        
        if response.status_code == 200:
            print(f"[Graph] Mensaje marcado como leido. ID: ...{message_id[-10:]}")
        else:
            print(f"[Graph] Error marcando como leido: {response.status_code}")
