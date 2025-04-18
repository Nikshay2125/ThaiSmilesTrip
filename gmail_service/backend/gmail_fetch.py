import os.path
import base64
import json
from typing import List, Dict, Optional
from email.mime.text import MIMEText
from email.message import Message
from email.header import decode_header
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",  # This scope includes both read and send
]

def get_gmail_service():
    """Gets Gmail API service instance."""
    creds = None
    # The file token.json stores the user's access and refresh tokens
    if os.path.exists("token.json"):
        try:
            creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        except ValueError:
            # If token.json is invalid, remove it and force re-authentication
            os.remove("token.json")
            creds = None
    
    # If there are no (valid) credentials available, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            # Request offline access to get refresh token
            flow.run_local_server(port=8080, access_type='offline', prompt='consent')
            creds = flow.credentials
            
        # Save the credentials for the next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    try:
        service = build("gmail", "v1", credentials=creds)
        return service
    except HttpError as error:
        print(json.dumps({"error": f"An error occurred: {str(error)}"}))
        return None

def get_email_content(service, message_id: str) -> Optional[Dict]:
    """Get the content of a specific email by its message ID."""
    try:
        message = service.users().messages().get(
            userId='me',
            id=message_id,
            format='full'
        ).execute()
        
        headers = message['payload']['headers']
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
        sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown Sender')
        date = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown Date')
        
        # Get email body
        def get_body_from_parts(parts):
            """Recursively extract body from email parts."""
            for part in parts:
                if part.get('mimeType') == 'text/plain':
                    if 'data' in part['body']:
                        return base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                elif part.get('parts'):
                    body = get_body_from_parts(part['parts'])
                    if body:
                        return body
            return None

        # Try to get body from parts first
        body = None
        if 'parts' in message['payload']:
            body = get_body_from_parts(message['payload']['parts'])
        
        # If no body found in parts, try direct body
        if not body and 'body' in message['payload'] and 'data' in message['payload']['body']:
            body = base64.urlsafe_b64decode(message['payload']['body']['data']).decode('utf-8')
        
        if not body:
            print(f"Warning: Could not extract body for message {message_id}")
            body = "No content available"
        
        return {
            'id': message_id,
            'subject': subject,
            'from': sender,
            'date': date,
            'body': body
        }
    except Exception as e:
        print(f"Error getting email content for message {message_id}: {str(e)}")
        return None

def get_recent_emails(service, max_results: int = 1, query: str = None) -> List[Dict]:
    """
    Get the most recent emails.
    
    Args:
        service: Gmail API service instance
        max_results: Maximum number of emails to retrieve
        query: Gmail search query (e.g., "from:example@gmail.com" or "subject:booking")
    """
    try:
        # Add query parameter to search if provided
        list_params = {
            'userId': 'me',
            'maxResults': max_results
        }
        
        if query:
            list_params['q'] = query
            
        results = service.users().messages().list(**list_params).execute()
        
        messages = results.get('messages', [])
        if not messages:
            return []
            
        emails = []
        for message in messages:
            email_content = get_email_content(service, message['id'])
            if email_content:
                emails.append(email_content)
            else:
                print(f"Skipping message {message['id']} due to content retrieval error")
        
        return emails
    except HttpError as error:
        print(f"Error listing messages: {str(error)}")
        return []
    except Exception as e:
        print(f"Unexpected error in get_recent_emails: {str(e)}")
        return []

def send_reply_email(original_email: Dict, reply_body: str) -> bool:
    """
    Send a reply email in the same thread as the original email.
    
    Args:
        original_email: Dictionary containing the original email data
        reply_body: The body text of the reply
    """
    try:
        service = get_gmail_service()
        if not service:
            print("Failed to get Gmail service")
            return False

        # Get the original email's headers
        message = service.users().messages().get(
            userId='me',
            id=original_email['id'],
            format='full'
        ).execute()
        
        headers = message['payload']['headers']
        
        # Extract necessary headers
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
        message_id = next((h['value'] for h in headers if h['name'] == 'Message-ID'), '')
        references = next((h['value'] for h in headers if h['name'] == 'References'), '')
        in_reply_to = next((h['value'] for h in headers if h['name'] == 'In-Reply-To'), '')
        from_email = next((h['value'] for h in headers if h['name'] == 'From'), '')
        
        # Create reply message
        reply_message = MIMEText(reply_body)
        reply_message['to'] = from_email
        reply_message['subject'] = f"Re: {subject}"
        reply_message['In-Reply-To'] = message_id
        reply_message['References'] = f"{references} {message_id}".strip()
        
        # Encode the message
        raw = base64.urlsafe_b64encode(reply_message.as_bytes()).decode('utf-8')
        
        # Send the email
        service.users().messages().send(
            userId='me',
            body={'raw': raw}
        ).execute()
        
        print(f"Reply sent successfully to {from_email}")
        return True
        
    except Exception as e:
        print(f"Error sending reply email: {str(e)}")
        return False

def send_email(to: str, subject: str, body: str, reply_to: Optional[Dict] = None) -> bool:
    """
    Send an email using Gmail API.
    
    Args:
        to: Recipient email address
        subject: Email subject
        body: Email body text
        reply_to: Optional original email to reply to
    """
    if reply_to:
        return send_reply_email(reply_to, body)
        
    try:
        service = get_gmail_service()
        if not service:
            print("Failed to get Gmail service")
            return False

        message = MIMEText(body)
        message['to'] = to
        message['subject'] = subject

        # Encode the message
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        
        # Send the email
        service.users().messages().send(
            userId='me',
            body={'raw': raw}
        ).execute()
        
        print(f"Email sent successfully to {to}")
        return True
        
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return False

def main():
    """Test the Gmail API functionality."""
    service = get_gmail_service()
    if service:
        print(json.dumps({"status": "Successfully connected to Gmail API"}))
        emails = get_recent_emails(service, max_results=1)
        if emails:
            output = {
                "most_recent_email": {
                    "subject": emails[0]['subject'],
                    "from": emails[0]['from'],
                    "date": emails[0]['date'],
                    "body_preview": emails[0]['body']
                }
            }
            print(json.dumps(output, indent=2))
        else:
            print(json.dumps({"status": "No emails found"}))

if __name__ == "__main__":
    main()