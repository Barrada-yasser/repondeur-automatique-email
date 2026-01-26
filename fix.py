"""
MODULE GMAIL COMPLET - Avec Envoi d'Emails
===========================================
Version complète avec :
✅ Lecture des emails
✅ Marquage comme lu
✅ ENVOI d'emails (NOUVEAU !)
"""

import os.path
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# SCOPES avec permission d'envoi
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.send',  # ← ENVOI D'EMAILS
]

class GmailConnector:
    """Gère la connexion et les opérations Gmail"""
    
    def __init__(self):
        self.service = None
        self.creds = None
    
    def authenticate(self):
        """Authentifie l'utilisateur avec Gmail OAuth 2.0"""
        print("\n🔐 Authentification Gmail...\n")
        
        if os.path.exists('token.json'):
            print("   📄 Token existant trouvé, chargement...")
            self.creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                print("   🔄 Rafraîchissement du token...")
                self.creds.refresh(Request())
            else:
                print("   🌐 Première connexion - Ouverture du navigateur...")
                print("   👉 Autorisez l'accès à Gmail (lecture + ENVOI)\n")
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES
                )
                self.creds = flow.run_local_server(port=0)
            
            with open('token.json', 'w') as token:
                token.write(self.creds.to_json())
            print("   ✅ Token sauvegardé dans token.json")
        
        self.service = build('gmail', 'v1', credentials=self.creds)
        print("   ✅ Connexion Gmail établie!\n")
        
        return True
    
    def get_unread_emails(self, max_results=5):
        """Récupère les emails non lus"""
        try:
            print(f"📬 Récupération des {max_results} derniers emails non lus...\n")
            
            results = self.service.users().messages().list(
                userId='me',
                q='is:unread',
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            
            if not messages:
                print("   ℹ️  Aucun email non lu trouvé\n")
                return []
            
            print(f"   ✅ {len(messages)} email(s) non lu(s) trouvé(s)\n")
            
            emails = []
            for message in messages:
                email_data = self.get_email_details(message['id'])
                emails.append(email_data)
            
            return emails
            
        except HttpError as error:
            print(f"   ❌ Erreur Gmail API: {error}")
            return []
    
    def get_email_details(self, message_id):
        """Récupère les détails complets d'un email"""
        try:
            message = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()
            
            headers = message['payload']['headers']
            
            email_data = {
                'id': message_id,
                'thread_id': message.get('threadId', ''),
                'from': self._get_header(headers, 'From'),
                'to': self._get_header(headers, 'To'),
                'subject': self._get_header(headers, 'Subject'),
                'date': self._get_header(headers, 'Date'),
                'message_id_header': self._get_header(headers, 'Message-ID'),
                'body': self._get_body(message['payload']),
                'snippet': message.get('snippet', '')
            }
            
            return email_data
            
        except HttpError as error:
            print(f"   ❌ Erreur lors de la récupération de l'email: {error}")
            return None
    
    def _get_header(self, headers, name):
        """Extrait une valeur de header spécifique"""
        for header in headers:
            if header['name'] == name:
                return header['value']
        return ''
    
    def _get_body(self, payload):
        """Extrait le corps de l'email"""
        body = ''
        
        if 'body' in payload and 'data' in payload['body']:
            body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
        
        elif 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    if 'data' in part['body']:
                        body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                        break
                elif part['mimeType'] == 'multipart/alternative':
                    body = self._get_body(part)
                    if body:
                        break
        
        return body
    
    def mark_as_read(self, message_id):
        """Marque un email comme lu"""
        try:
            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'removeLabelIds': ['UNREAD']}
            ).execute()
            print(f"   ✅ Email {message_id[:10]}... marqué comme lu")
            return True
        except HttpError as error:
            print(f"   ❌ Erreur lors du marquage: {error}")
            return False
    
    # ========================================
    # NOUVELLE FONCTIONNALITÉ : ENVOI D'EMAILS
    # ========================================
    
    def send_email(self, to, subject, body, reply_to_message_id=None, thread_id=None):
        """
        Envoie un email via Gmail
        
        Args:
            to (str): Adresse email du destinataire
            subject (str): Objet de l'email
            body (str): Corps de l'email (texte brut)
            reply_to_message_id (str): ID du message auquel répondre (optionnel)
            thread_id (str): ID du thread pour conversation (optionnel)
            
        Returns:
            dict: Réponse de l'API Gmail ou None si erreur
        """
        try:
            # Créer le message
            message = MIMEMultipart()
            message['To'] = to
            message['Subject'] = subject
            
            # Si c'est une réponse, ajouter les headers appropriés
            if reply_to_message_id:
                message['In-Reply-To'] = reply_to_message_id
                message['References'] = reply_to_message_id
            
            # Ajouter le corps du message
            message.attach(MIMEText(body, 'plain', 'utf-8'))
            
            # Encoder en base64
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
            
            # Préparer le body pour l'API
            send_body = {'raw': raw_message}
            
            # Si c'est dans un thread, ajouter le threadId
            if thread_id:
                send_body['threadId'] = thread_id
            
            # Envoyer l'email
            sent_message = self.service.users().messages().send(
                userId='me',
                body=send_body
            ).execute()
            
            print(f"   ✅ Email envoyé avec succès (ID: {sent_message['id'][:10]}...)")
            return sent_message
            
        except HttpError as error:
            print(f"   ❌ Erreur lors de l'envoi: {error}")
            return None
    
    def format_email_for_display(self, email):
        """Formate un email pour l'affichage"""
        formatted = f"""
{'='*70}
📧 EMAIL
{'='*70}
De       : {email['from']}
À        : {email['to']}
Objet    : {email['subject']}
Date     : {email['date']}
{'='*70}

{email['body'][:500]}{"..." if len(email['body']) > 500 else ""}

{'='*70}
"""
        return formatted
    
    def extract_email_address(self, from_header):
        """
        Extrait l'adresse email du header From
        Exemple: "John Doe <john@example.com>" -> "john@example.com"
        """
        import re
        match = re.search(r'<(.+?)>', from_header)
        if match:
            return match.group(1)
        return from_header.strip()


# ========================================
# FONCTION DE TEST
# ========================================

def test_gmail_connection():
    """Teste la connexion Gmail et affiche les emails non lus"""
    
    print("\n" + "="*70)
    print("🧪 TEST DE CONNEXION GMAIL")
    print("="*70 + "\n")
    
    gmail = GmailConnector()
    
    if not gmail.authenticate():
        print("❌ Échec de l'authentification")
        return
    
    emails = gmail.get_unread_emails(max_results=3)
    
    if not emails:
        print("ℹ️  Aucun email à afficher")
        return
    
    print("📨 EMAILS NON LUS :")
    print("="*70 + "\n")
    
    for i, email in enumerate(emails, 1):
        print(f"\n{'='*70}")
        print(f"EMAIL #{i}")
        print(gmail.format_email_for_display(email))
    
    print("\n" + "="*70)
    print("✅ Test terminé avec succès!")
    print("="*70 + "\n")


if __name__ == "__main__":
    test_gmail_connection()