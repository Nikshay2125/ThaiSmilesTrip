import os.path
import base64
import json
from typing import List, Dict, Optional
from email.mime.text import MIMEText
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

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
        subject = next(h['value'] for h in headers if h['name'] == 'Subject')
        sender = next(h['value'] for h in headers if h['name'] == 'From')
        date = next(h['value'] for h in headers if h['name'] == 'Date')
        
        # Get email body
        if 'parts' in message['payload']:
            parts = message['payload']['parts']
            data = parts[0]['body']['data']
            text = base64.urlsafe_b64decode(data).decode('utf-8')
        else:
            data = message['payload']['body']['data']
            text = base64.urlsafe_b64decode(data).decode('utf-8')
        
        return {
            'id': message_id,
            'subject': subject,
            'from': sender,
            'date': date,
            'body': text
        }
    except Exception as e:
        print(json.dumps({"error": f"Error getting email content: {str(e)}"}))
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
        
        return emails
    except HttpError as error:
        print(json.dumps({"error": f"An error occurred: {str(error)}"}))
        return []

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