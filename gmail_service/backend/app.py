import os
import json
import time
import threading
import base64
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Flask, request, jsonify, session, redirect, url_for, send_file
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room
from werkzeug.middleware.proxy_fix import ProxyFix

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from email.mime.text import MIMEText

import jwt
import pandas as pd
from bson import ObjectId
from db_config import MongoDB
import requests
import traceback

# Import the custom monitoring classes
from gmail_monitor import GmailMonitor
from parser import TextParser
from request_manager import RequestManager

app = Flask(__name__)
# Fix for session handling behind proxies
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

# Use a fixed secret key instead of a random one that changes on each restart
app.secret_key = 'your_secure_secret_key_here'  # In production, use a secure randomly generated key
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=5)

CORS(app, supports_credentials=True, origins="*")
socketio = SocketIO(app, cors_allowed_origins="*")

# Load client configuration
# Use absolute path for credentials file
CLIENT_SECRETS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "credentials.json")
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/gmail.send', 'https://www.googleapis.com/auth/userinfo.profile', 'https://www.googleapis.com/auth/userinfo.email']

# JWT configuration
JWT_SECRET = 'your_jwt_secret_key_here'  # In production, use a secure randomly generated key
JWT_ALGORITHM = 'HS256'

# Load configurations from config.json
try:
    with open(CONFIG_FILE, 'r') as f:
        app_config = json.load(f)
    print(f"Loaded configuration from {CONFIG_FILE}")
except Exception as e:
    print(f"Error loading config.json: {str(e)}. Using default configurations.")
    app_config = {
        "check_interval": 60,
        "email_filter": "newer_than:2d -in:chats -from:me",
        "custom_schema": {
            "date": "DD MMM YYYY formatted date",
            "guest_name": "Full name of the guest",
            "pax": "Number of guests/people (integer)",
            "flight_no": "Flight number if available",
            "pickup_time": "Time in HH:MM AM/PM format", 
            "pickup_location": "Location for pickup",
            "hotel_drop": "Hotel or drop-off location",
            "tour": "Tour details if applicable",
            "payment": "Payment information if available",
            "code": "Booking or reference code"
        },
        "subject_keywords": [
            "booking", "reservation", "confirmation", "pickup", 
            "airport", "transfer", "arrival", "hotel", "travel"
        ],
        "relevance_keywords": [
            "booking", "reservation", "confirmation", "hotel", "flight", 
            "travel", "itinerary", "guest", "pickup", "transfer"
        ],
        "max_results": 5
    }

# Global variable to store email monitoring threads
email_monitors = {}
# Socket connections by user
socket_connections = {}
# Temporary storage for authentication states
auth_states = {}
# Store RequestManager instances by user
request_managers = {}
# GROQ API key for the TextParser
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'message': 'Token is missing'}), 401
        
        try:
            token = token.split(' ')[1]  # Remove 'Bearer ' prefix
            data = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            user_email = data['email']
            
            # Store user info in session
            session['user_email'] = user_email
            
            # Store user info in request object for easier access
            request.user = {
                'email': user_email
            }
            
            # If credentials are in session, add them to request.user
            credentials_dict = session.get('credentials')
            if credentials_dict:
                request.user['credentials'] = credentials_dict
                
        except Exception as e:
            print(f"Token validation error: {str(e)}")
            return jsonify({'message': 'Token is invalid'}), 401
        
        return f(*args, **kwargs)
    return decorated

# Custom WebSocket event handler for email notifications
class WebSocketNotifier:
    def __init__(self, socketio_instance, user_email):
        self.socketio = socketio_instance
        self.user_email = user_email
        
    def notify_new_request(self, request_doc):
        """Notify frontend about new request via WebSocket"""
        # Convert MongoDB ObjectId to string for serialization if needed
        if isinstance(request_doc, dict) and '_id' in request_doc:
            request_doc = dict(request_doc)  # Make a copy
            request_doc['id'] = str(request_doc.pop('_id'))
        
        # Ensure parsed_data is accessible to the frontend
        if isinstance(request_doc, dict) and 'processed_data' in request_doc and isinstance(request_doc['processed_data'], dict):
            request_doc['parsed_data'] = request_doc['processed_data']
        
        self.socketio.emit('new_requests', 
                         {'count': 1, 'requests': [request_doc]},
                         room=self.user_email)
    
    def notify_update(self, request_doc):
        """Notify frontend about updated request via WebSocket"""
        # Convert MongoDB ObjectId to string for serialization if needed
        if isinstance(request_doc, dict) and '_id' in request_doc:
            request_doc = dict(request_doc)  # Make a copy
            request_doc['id'] = str(request_doc.pop('_id'))
            
        # Ensure parsed_data is accessible to the frontend
        if isinstance(request_doc, dict) and 'processed_data' in request_doc and isinstance(request_doc['processed_data'], dict):
            request_doc['parsed_data'] = request_doc['processed_data']
            
        self.socketio.emit('request_updated', request_doc, room=self.user_email)

def monitor_emails(user_email, credentials_dict):
    """Background thread function to monitor emails using the GmailMonitor class"""
    try:
        # Create credentials object from stored credentials dictionary
        credentials = Credentials(**credentials_dict)
        
        # Set up the OAuth token and refresh handler
        def refresh_token_callback(updated_credentials):
            # Update the credentials in session
            # NOTE: This won't work directly in a thread, but demonstrates the logic
            session['credentials'] = {
                'token': updated_credentials.token,
                'refresh_token': updated_credentials.refresh_token,
                'token_uri': updated_credentials.token_uri,
                'client_id': updated_credentials.client_id,
                'client_secret': updated_credentials.client_secret,
                'scopes': updated_credentials.scopes
            }
            print(f"OAuth token refreshed for {user_email}")
        
        # Initialize WebSocketNotifier for real-time updates to frontend
        notifier = WebSocketNotifier(socketio, user_email)
        
        # Initialize the GmailMonitor with the configuration from config.json
        monitor = GmailMonitor(
            api_key=GROQ_API_KEY,
            check_interval=app_config.get('check_interval', 60),
            email_filter=app_config.get('email_filter'),
            custom_schema=app_config.get('custom_schema'),
            subject_keywords=app_config.get('subject_keywords'),
            relevance_keywords=app_config.get('relevance_keywords')
        )
        
        # Store the original methods to avoid losing functionality
        original_add_request = monitor.request_manager.add_request
        original_update_status = monitor.request_manager.update_request_status
        original_set_confirmation = monitor.request_manager.set_confirmation
        
        def add_request_with_notification(email_data):
            # Call the original add_request method to create the request
            request_id = original_add_request(email_data)
            
            # Get the request document
            request_doc = monitor.request_manager.get_request(request_id)
            if request_doc:
                # The email is already processed by GmailMonitor._process_single_email
                # which calls process_and_store_in_mongodb with the parsed data
                # We just need to ensure the frontend gets notified
                
                # Format the data for frontend consumption
                if isinstance(request_doc, dict):
                    # Ensure the document has the expected structure
                    if '_id' in request_doc:
                        request_doc['id'] = str(request_doc.pop('_id'))
                    
                    # Ensure parsed_data is accessible to the frontend
                    if 'processed_data' in request_doc and isinstance(request_doc['processed_data'], dict):
                        request_doc['parsed_data'] = request_doc['processed_data']
                
                # Notify frontend about new request
                notifier.notify_new_request(request_doc)
            
            return request_id
        
        def update_status_with_notification(request_id, status):
            # Update the status using the original method
            original_update_status(request_id, status)
            
            # Get the updated request
            request_doc = monitor.request_manager.get_request(request_id)
            if request_doc:
                # Format the data for frontend consumption
                if isinstance(request_doc, dict):
                    # Ensure the document has the expected structure
                    if '_id' in request_doc:
                        request_doc['id'] = str(request_doc.pop('_id'))
                    
                    # Ensure parsed_data is accessible to the frontend
                    if 'processed_data' in request_doc and isinstance(request_doc['processed_data'], dict):
                        request_doc['parsed_data'] = request_doc['processed_data']
                
                # Notify frontend about updated request
                notifier.notify_update(request_doc)
        
        def set_confirmation_with_notification(request_id, confirmed):
            # Set confirmation using the original method
            original_set_confirmation(request_id, confirmed)
            
            # Get the updated request
            request_doc = monitor.request_manager.get_request(request_id)
            if request_doc:
                # Format the data for frontend consumption
                if isinstance(request_doc, dict):
                    # Ensure the document has the expected structure
                    if '_id' in request_doc:
                        request_doc['id'] = str(request_doc.pop('_id'))
                    
                    # Ensure parsed_data is accessible to the frontend
                    if 'processed_data' in request_doc and isinstance(request_doc['processed_data'], dict):
                        request_doc['parsed_data'] = request_doc['processed_data']
                
                # Notify frontend about updated request
                notifier.notify_update(request_doc)
        
        # Replace the methods with our custom ones
        monitor.request_manager.add_request = add_request_with_notification
        monitor.request_manager.update_request_status = update_status_with_notification
        monitor.request_manager.set_confirmation = set_confirmation_with_notification
        
        # Start monitoring using the existing GmailMonitor implementation
        # Override the service with our authenticated service
        monitor.service = build('gmail', 'v1', credentials=credentials)
        
        # Store the request manager for API endpoint access
        request_managers[user_email] = monitor.request_manager
        
        # Start the monitoring loop
        print(f"Starting email monitoring for {user_email}")
        monitor.start_monitoring(max_results=app_config.get('max_results', 5))
        
    except Exception as e:
        print(f"Failed to initialize email monitoring for {user_email}: {str(e)}")

@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    print(f"Client disconnected: {request.sid}")
    # Remove client from user mapping
    for user_email, sids in socket_connections.items():
        if request.sid in sids:
            sids.remove(request.sid)
            break

@socketio.on('authenticate')
def handle_authenticate(data):
    token = data.get('token')
    if not token:
        return False
    
    try:
        # Verify token
        data = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_email = data['email']
        
        # Add client to room for the user
        join_room(user_email)
        
        # Track socket connection for this user
        if user_email not in socket_connections:
            socket_connections[user_email] = set()
        socket_connections[user_email].add(request.sid)
        
        return True
    except:
        return False

@app.route('/auth/google')
def google_auth():
    # Hard-code the redirect URI to match exactly what's in Google Cloud Console
    redirect_uri = "http://localhost:5000/oauth2callback"
    
    # Create flow instance using client secrets file from Google API Console
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )
    
    # Generate a random state string to protect against CSRF
    state = str(uuid.uuid4())
    
    # Store state in our temporary storage with a timestamp
    auth_states[state] = {
        'timestamp': datetime.now(timezone.utc),
        'used': False
    }
    
    # Generate URL for authorization
    authorization_url, _ = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        state=state
    )
    
    print(f"Auth state saved: {state}")
    print(f"Redirect URI: {redirect_uri}")
    return jsonify({'auth_url': authorization_url})

@app.route('/oauth2callback')
def oauth2callback():
    # Hard-code the redirect URI to match exactly what's in Google Cloud Console
    redirect_uri = "http://localhost:5000/oauth2callback"
    
    try:
        # Check state parameter for CSRF protection
        state_param = request.args.get('state', '')
        print(f"State from request: {state_param}")
        
        # Check if state exists in our temporary storage
        if state_param not in auth_states:
            return jsonify({'error': 'Invalid state parameter'}), 400
        
        # Check if state has already been used (prevent replay attacks)
        state_data = auth_states[state_param]
        if state_data.get('used', False):
            return jsonify({'error': 'State has already been used'}), 400
        
        # Mark state as used
        auth_states[state_param]['used'] = True
        
        # Check if state has expired (10 min validity)
        time_diff = datetime.now(timezone.utc) - state_data['timestamp']
        if time_diff.total_seconds() > 600:  # 10 minutes
            return jsonify({'error': 'State has expired'}), 400
        
        # Get the authorization code from query parameters
        code = request.args.get('code')
        if not code:
            return jsonify({'error': 'Missing authorization code'}), 400
            
        # Load client secret file
        with open(CLIENT_SECRETS_FILE, 'r') as f:
            client_config = json.load(f)
        
        # Get client credentials from the loaded config
        client_id = client_config['web']['client_id']
        client_secret = client_config['web']['client_secret']
        token_uri = client_config['web']['token_uri']
        
        # Exchange code for tokens
        token_data = {
            'code': code,
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code'
        }
        
        # Make the token request
        token_response = requests.post(token_uri, data=token_data)
        
        if token_response.status_code != 200:
            print(f"Token exchange error: {token_response.text}")
            return jsonify({'error': 'Failed to exchange code for token'}), 400
            
        # Parse the token response
        token_info = token_response.json()
        
        # Create credentials from token info
        credentials = Credentials(
            token=token_info['access_token'],
            refresh_token=token_info.get('refresh_token'),
            token_uri=token_uri,
            client_id=client_id,
            client_secret=client_secret,
            scopes=token_info.get('scope', '').split(' ')
        )
        
        # Get user info using the credentials
        service = build('oauth2', 'v2', credentials=credentials)
        user_info = service.userinfo().get().execute()
        
        # Store credentials
        credentials_dict = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
        
        # Make sure we have a persistent session
        session.permanent = True
        
        # Store in session with explicit user_email key
        session['credentials'] = credentials_dict
        session['user_email'] = user_info['email']

        # Optionally store in database for persistence
        try:
            from db_config import MongoDB
            db = MongoDB()
            
            # Check if the db has a user_credentials collection, if not create it
            if 'user_credentials' not in db.db.list_collection_names():
                db.db.create_collection('user_credentials')
            
            # Store or update user credentials
            db.db.user_credentials.update_one(
                {'user_email': user_info['email']},
                {'$set': {
                    'credentials': credentials_dict,
                    'last_updated': datetime.now(timezone.utc)
                }},
                upsert=True
            )
            print(f"Stored credentials in database for {user_info['email']}")
        except Exception as db_err:
            print(f"Error storing credentials in database: {str(db_err)}")
            # Continue even if database storage fails
        
        # Start email monitoring for this user
        if user_info['email'] not in email_monitors:
            monitor_thread = threading.Thread(
                target=monitor_emails,
                args=(user_info['email'], credentials_dict),
                daemon=True
            )
            monitor_thread.start()
            email_monitors[user_info['email']] = monitor_thread
        
        # Create JWT token
        token = jwt.encode({
            'email': user_info['email'],
            'exp': datetime.now(timezone.utc) + timedelta(days=1)
        }, JWT_SECRET, algorithm=JWT_ALGORITHM)
        
        # Redirect to frontend with token
        frontend_url = "http://localhost:5173/dashboard"
        return redirect(f"{frontend_url}?token={token}")
        
    except Exception as e:
        print(f"OAuth callback error: {str(e)}")
        return jsonify({'error': f'OAuth error: {str(e)}'}), 400

@app.route('/api/requests')
@token_required
def get_requests():
    user_email = session.get('user_email')
    print(f"Getting requests for user: {user_email}")
    
    # Fall back to MongoDB for complete and consistent data
    db = MongoDB()
    
    # Get all requests for the user from MongoDB
    mongo_requests = list(db.requests.find({'user_email': user_email}, sort=[('created_at', -1)]))
    print(f"Found {len(mongo_requests)} requests in MongoDB")
    
    # Format the data for frontend consumption
    formatted_requests = []
    for request in mongo_requests:
        formatted_request = dict(request)  # Make a copy
        
        # Convert ObjectId to string for JSON serialization
        if '_id' in formatted_request:
            formatted_request['id'] = str(formatted_request.pop('_id'))
        
        # Handle any other ObjectId fields
        for key, value in formatted_request.items():
            if isinstance(value, ObjectId):
                formatted_request[key] = str(value)
        
        # Ensure the request has the necessary fields
        if 'email_data' not in formatted_request and 'sender' in formatted_request:
            formatted_request['email_data'] = {
                'from': formatted_request.get('sender', 'Unknown'),
                'subject': 'Request ' + formatted_request.get('request_id', 'Unknown'),
                'date': formatted_request.get('created_at', datetime.now().isoformat())
            }
        
        # Ensure parsed_data is accessible to the frontend
        if 'processed_data' in formatted_request and isinstance(formatted_request['processed_data'], dict):
            formatted_request['parsed_data'] = formatted_request['processed_data']
        
        # Add required fields if missing
        if 'status' not in formatted_request:
            formatted_request['status'] = formatted_request.get('status', 'pending')
        
        if 'created_at' not in formatted_request:
            formatted_request['created_at'] = datetime.now().isoformat()
            
        # Ensure confirmation fields are present
        formatted_request['confirmation'] = formatted_request.get('confirmation', False)
        formatted_request['confirmation_sent'] = formatted_request.get('confirmation_sent', False)
        
        # Set status to confirmed if confirmation is true
        if formatted_request.get('confirmation', False):
            formatted_request['status'] = 'confirmed'
        
        formatted_requests.append(formatted_request)
    
    # Use the RequestManager as well to get any requests that might be in memory but not yet in MongoDB
    if user_email in request_managers:
        request_manager = request_managers[user_email]
        try:
            # Get all requests from the request manager
            memory_requests = []
            for req_id, req in request_manager.requests.items():
                # Skip requests that are already in our formatted list
                if any(freq.get('request_id') == req_id or freq.get('id') == req_id for freq in formatted_requests):
                    continue
                
                # Format the request
                memory_req = dict(req)
                if '_id' in memory_req:
                    memory_req['id'] = str(memory_req.pop('_id'))
                
                # Ensure parsed_data is accessible to the frontend
                if 'processed_data' in memory_req and isinstance(memory_req['processed_data'], dict):
                    memory_req['parsed_data'] = memory_req['processed_data']
                
                # Ensure confirmation fields are present
                memory_req['confirmation'] = memory_req.get('confirmation', False)
                memory_req['confirmation_sent'] = memory_req.get('confirmation_sent', False)
                
                # Set status to confirmed if confirmation is true
                if memory_req.get('confirmation', False):
                    memory_req['status'] = 'confirmed'
                
                memory_requests.append(memory_req)
            
            # Add memory requests to the formatted requests
            if memory_requests:
                print(f"Adding {len(memory_requests)} additional requests from memory")
                formatted_requests.extend(memory_requests)
        except Exception as e:
            print(f"Error getting requests from RequestManager: {str(e)}")
    
    print(f"Returning {len(formatted_requests)} total requests to frontend")
    return jsonify(formatted_requests)

@app.route('/api/requests/<request_id>')
@token_required
def get_request(request_id):
    user_email = session.get('user_email')
    
    # Use the RequestManager from GmailMonitor
    if user_email in request_managers:
        request_manager = request_managers[user_email]
        try:
            request_doc = request_manager.get_request(request_id)
            if request_doc:
                # Convert to dict if mongodb document
                if hasattr(request_doc, '_id'):
                    request_doc = dict(request_doc)
                    request_doc['id'] = str(request_doc.pop('_id'))
                
                # Ensure parsed_data is accessible to the frontend
                if 'processed_data' in request_doc and isinstance(request_doc['processed_data'], dict):
                    request_doc['parsed_data'] = request_doc['processed_data']
                
                return jsonify(request_doc)
        except Exception as e:
            print(f"Error getting request from RequestManager: {str(e)}")
            # Fall back to MongoDB
    
    # Fall back to MongoDB
    db = MongoDB()
    request_doc = db.requests.find_one({'_id': ObjectId(request_id), 'user_email': user_email})
    if not request_doc:
        return jsonify({'message': 'Request not found'}), 404
    
    # Convert ObjectId to string for JSON serialization
    request_doc['id'] = str(request_doc.pop('_id'))
    
    # Ensure parsed_data is accessible to the frontend
    if 'processed_data' in request_doc and isinstance(request_doc['processed_data'], dict):
        request_doc['parsed_data'] = request_doc['processed_data']
    
    return jsonify(request_doc)

@app.route('/api/requests/<request_id>/confirm', methods=['POST'])
@token_required
def confirm_request(request_id):
    user_email = session.get('user_email')
    
    try:
        # Use the RequestManager directly
        if user_email not in request_managers:
            return jsonify({'message': 'No active request manager found'}), 400
            
        request_manager = request_managers[user_email]
        
        # Set confirmation status
        request_manager.set_confirmation(request_id, True)
        
        # Get the updated request
        request_doc = request_manager.get_request(request_id)
        if not request_doc:
            # Try MongoDB directly as fallback
            db = MongoDB()
            request_doc = db.requests.find_one({'request_id': request_id})
            if not request_doc:
                return jsonify({'message': 'Request not found'}), 404
        
        # Convert to dict and handle MongoDB ObjectId
        request_dict = {}
        if isinstance(request_doc, dict):
            request_dict = dict(request_doc)
            # Handle ObjectId in _id field
            if '_id' in request_dict:
                request_dict['id'] = str(request_dict.pop('_id'))
            # Handle ObjectId in any other fields
            for key, value in request_dict.items():
                if isinstance(value, ObjectId):
                    request_dict[key] = str(value)
        
        # Ensure parsed_data is accessible to the frontend
        if 'processed_data' in request_dict and isinstance(request_dict['processed_data'], dict):
            request_dict['parsed_data'] = request_dict['processed_data']
        
        # Update status to confirmed
        request_manager.update_request_status(request_id, 'confirmed')
        
        # Update confirmation fields
        request_dict['status'] = 'confirmed'
        request_dict['confirmation'] = True
        request_dict['confirmation_sent'] = True
        
        # Notify clients about the update
        notifier = WebSocketNotifier(socketio, user_email)
        notifier.notify_update(request_dict)
        
        return jsonify({'request': request_dict})
    
    except Exception as e:
        print(f"Error confirming request: {str(e)}")
        print(f"Full traceback: {traceback.format_exc()}")
        return jsonify({'message': f'Error confirming request: {str(e)}'}), 500

@app.route('/api/requests/<request_id>/status', methods=['PUT'])
@token_required
def update_request_status(request_id):
    user_email = session.get('user_email')
    
    # Get status from request body
    data = request.json
    status = data.get('status')
    
    if status not in ['pending', 'confirmed', 'rejected']:
        return jsonify({'message': 'Invalid status'}), 400
    
    # Use the RequestManager from GmailMonitor
    if user_email in request_managers:
        request_manager = request_managers[user_email]
        try:
            request_manager.update_request_status(request_id, status)
            
            # Get the updated request
            request_doc = request_manager.get_request(request_id)
            if request_doc:
                # Convert to dict if mongodb document
                if hasattr(request_doc, '_id'):
                    request_doc = dict(request_doc)
                    request_doc['id'] = str(request_doc.pop('_id'))
                
                # Notify clients about the update
                notifier = WebSocketNotifier(socketio, user_email)
                notifier.notify_update(request_doc)
                
                return jsonify({'request': request_doc})
        except Exception as e:
            print(f"Error updating request status with RequestManager: {str(e)}")
            # Fall back to MongoDB
    
    # Fall back to MongoDB
    db = MongoDB()
    
    # Update request status
    request_doc = db.requests.find_one_and_update(
        {'_id': ObjectId(request_id), 'user_email': user_email},
        {'$set': {'status': status}},
        return_document=True
    )
    
    if not request_doc:
        return jsonify({'message': 'Request not found'}), 404
    
    # Convert ObjectId to string for response
    request_doc['id'] = str(request_doc.pop('_id'))
    
    # Notify clients about the update
    notifier = WebSocketNotifier(socketio, user_email)
    notifier.notify_update(request_doc)
    
    return jsonify({'request': request_doc})

def create_confirmation_email(request_doc):
    """Create confirmation email message"""
    # Customize this function to create your confirmation email template
    subject = f"Confirmation: {request_doc['email_data']['subject']}"
    body = f"""Dear {request_doc['parsed_data'].get('guest_name', 'Guest')},

Your request has been confirmed.

Details:
- Flight: {request_doc['parsed_data'].get('flight_no', 'N/A')}
- Pickup Time: {request_doc['parsed_data'].get('pickup_time', 'N/A')}
- Pickup Location: {request_doc['parsed_data'].get('pickup_location', 'N/A')}
- Hotel: {request_doc['parsed_data'].get('hotel_drop', 'N/A')}
- Tour: {request_doc['parsed_data'].get('tour', 'N/A')}

Thank you for choosing our service.
"""
    
    message = MIMEText(body)
    message['to'] = request_doc['email_data']['from']
    message['subject'] = subject
    
    return {'raw': base64.urlsafe_b64encode(message.as_bytes()).decode()}

@app.route('/api/export-spreadsheet')
@token_required
def export_spreadsheet():
    try:
        db = MongoDB()
        print("Exporting all requests")
        
        # Get all requests without filtering by user
        requests = list(db.requests.find({}))
        print(f"Found {len(requests)} requests to export")
        
        # Prepare data for Excel
        excel_data = []
        for req in requests:
            try:
                # Get processed_data or parsed_data
                parsed_data = req.get('processed_data', {}) or req.get('parsed_data', {})
                
                # Get sender info
                sender = req.get('sender', '')
                if not sender and 'email_data' in req:
                    sender = req['email_data'].get('from', '')
                
                # Format the data
                row_data = {
                    'Request ID': str(req.get('_id', '')),
                    'Date': req.get('created_at', ''),
                    'Sender': sender,
                    'Guest Name': parsed_data.get('guest_name', ''),
                    'PAX': parsed_data.get('pax', ''),
                    'Flight': parsed_data.get('flight_no', ''),
                    'Pickup Time': parsed_data.get('pickup_time', ''),
                    'Pickup Location': parsed_data.get('pickup_location', ''),
                    'Hotel': parsed_data.get('hotel_drop', ''),
                    'Tour': parsed_data.get('tour', ''),
                    'Status': req.get('status', 'pending'),
                    'Confirmation': 'Yes' if req.get('confirmation', False) else 'No',
                    'Confirmation Sent': 'Yes' if req.get('confirmation_sent', False) else 'No'
                }
                excel_data.append(row_data)
                print(f"Added row data: {row_data}")
            except Exception as row_err:
                print(f"Error processing row: {str(row_err)}")
                continue
        
        if not excel_data:
            print("No data to export")
            return jsonify({'message': 'No data to export'}), 400
        
        # Create DataFrame and export to Excel
        df = pd.DataFrame(excel_data)
        print(f"Created DataFrame with {len(df)} rows")
        
        # Create a unique filename
        excel_file = f'requests_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        
        # Export to Excel with better formatting
        with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Requests')
            
            # Auto-adjust columns width
            worksheet = writer.sheets['Requests']
            for idx, col in enumerate(df.columns):
                max_length = max(
                    df[col].astype(str).apply(len).max(),  # max length of values
                    len(str(col))  # length of column name
                ) + 2  # adding a little extra space
                worksheet.column_dimensions[chr(65 + idx)].width = max_length
        
        print(f"Excel file created: {excel_file}")
        
        # Send the file
        return send_file(
            excel_file,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=excel_file
        )
        
    except Exception as e:
        print(f"Error exporting spreadsheet: {str(e)}")
        print(f"Full traceback: {traceback.format_exc()}")
        return jsonify({'message': f'Error exporting spreadsheet: {str(e)}'}), 500

@app.route('/api/emails/check', methods=['POST'])
@token_required
def check_emails():
    user_email = session.get('user_email')
    print(f"Checking emails for user: {user_email}")
    
    try:
        # First try to get credentials from request.user if available 
        credentials_dict = getattr(request, 'user', {}).get('credentials')
        
        if not credentials_dict:
            # Then try to get credentials from session
            credentials_dict = session.get('credentials')
        
        # If credentials are not available in session, try to get them from db or JWT
        if not credentials_dict:
            # Check if we have an active email monitor for this user
            if user_email in email_monitors:
                print(f"Found active email monitor for {user_email}, retrieving credentials")
                # Try to get credentials from the monitor_emails thread
                monitor_thread = email_monitors[user_email]
                
                # Try different attribute names that might contain the credentials
                for attr_name in ['_args', '_kwargs', 'args', 'kwargs']:
                    if hasattr(monitor_thread, attr_name):
                        attr_value = getattr(monitor_thread, attr_name)
                        if isinstance(attr_value, tuple) and len(attr_value) > 1:
                            # Might be in args tuple
                            for arg in attr_value:
                                if isinstance(arg, dict) and 'token' in arg and 'refresh_token' in arg:
                                    credentials_dict = arg
                                    break
                        elif isinstance(attr_value, dict) and 'credentials_dict' in attr_value:
                            credentials_dict = attr_value['credentials_dict']
                            break
                
                # Direct access attempt
                if not credentials_dict and hasattr(monitor_thread, 'credentials_dict'):
                    credentials_dict = monitor_thread.credentials_dict
            
            # If still no credentials, try to check in the database if available
            if not credentials_dict:
                try:
                    # This is a placeholder - you would need to implement a user credentials storage
                    # For example, you might have a user_credentials collection in MongoDB
                    from db_config import MongoDB
                    db = MongoDB()
                    if hasattr(db, 'user_credentials'):
                        user_cred_doc = db.user_credentials.find_one({'user_email': user_email})
                        if user_cred_doc and 'credentials' in user_cred_doc:
                            credentials_dict = user_cred_doc['credentials']
                except Exception as db_err:
                    print(f"Error retrieving credentials from database: {str(db_err)}")
        
        if not credentials_dict:
            print(f"No credentials available for user: {user_email}")
            return jsonify({
                'message': 'No Gmail credentials available. Please refresh the page or log out and log in again.', 
                'new_requests': []
            }), 200  # Return empty list instead of error
        
        # Create credentials object
        credentials = Credentials(**credentials_dict)
        
        # Create Gmail service
        service = build('gmail', 'v1', credentials=credentials)
        
        # Create a new monitor instead of looking for an existing one
        monitor = GmailMonitor(
            api_key=GROQ_API_KEY,
            check_interval=app_config.get('check_interval', 60),
            email_filter=app_config.get('email_filter'),
            custom_schema=app_config.get('custom_schema'),
            subject_keywords=app_config.get('subject_keywords'),
            relevance_keywords=app_config.get('relevance_keywords')
        )
        monitor.service = service
        
        # Get or create a request manager
        if user_email in request_managers:
            request_manager = request_managers[user_email]
        else:
            request_manager = RequestManager()
            request_managers[user_email] = request_manager
            
        # Get the most recent emails
        from gmail_fetch import get_recent_emails
        print(f"Fetching recent emails for {user_email}...")
        emails = get_recent_emails(
            service, 
            max_results=app_config.get('max_results', 5), 
            query=app_config.get('email_filter')
        )
        
        print(f"Found {len(emails)} emails to process")
        
        # Process each email
        new_requests = []
        processed_any = False
        
        for email in emails:
            result = monitor._process_single_email(email)
            if result:
                processed_any = True
                print(f"Processed email with result: {result}")
                # Get the request document for this email
                email_id = email.get('id')
                request_id = request_manager.get_request_by_email_id(email_id)
                if request_id:
                    request_doc = request_manager.get_request(request_id)
                    if request_doc:
                        # Format for frontend
                        if isinstance(request_doc, dict) and '_id' in request_doc:
                            request_doc['id'] = str(request_doc.pop('_id'))
                        
                        # Ensure parsed_data is accessible
                        if isinstance(request_doc, dict) and 'processed_data' in request_doc and isinstance(request_doc['processed_data'], dict):
                            request_doc['parsed_data'] = request_doc['processed_data']
                        
                        new_requests.append(request_doc)
        
        # Get all requests from MongoDB to ensure frontend has the latest data
        if processed_any:
            # Even if the new_requests is empty, we might have processed 
            # emails that were already in the database
            db = MongoDB()
            all_requests = list(db.requests.find({'user_email': user_email}, sort=[('created_at', -1)]))
            print(f"Found {len(all_requests)} total requests in MongoDB after processing")
            
            # Format all requests for the frontend
            formatted_requests = []
            for req in all_requests:
                formatted_req = dict(req)
                # Convert ObjectId to string
                if '_id' in formatted_req:
                    formatted_req['id'] = str(formatted_req.pop('_id'))
                
                # Ensure parsed_data is accessible
                if 'processed_data' in formatted_req and isinstance(formatted_req['processed_data'], dict):
                    formatted_req['parsed_data'] = formatted_req['processed_data']
                
                # Ensure email_data exists
                if 'email_data' not in formatted_req and 'sender' in formatted_req:
                    formatted_req['email_data'] = {
                        'from': formatted_req.get('sender', 'Unknown'),
                        'subject': 'Request ' + formatted_req.get('request_id', 'Unknown'),
                        'date': formatted_req.get('created_at', datetime.now().isoformat())
                    }
                
                formatted_requests.append(formatted_req)
            
            # Notify all connected clients about the data update
            notifier = WebSocketNotifier(socketio, user_email)
            # Don't notify directly since notifier.notify_new_request would 
            # only notify about a single request. Instead, tell the frontend 
            # to reload all data.
            socketio.emit('reload_data', room=user_email)
            
            return jsonify({
                'processed_emails': True,
                'message': 'Emails processed successfully',
                'new_requests': new_requests,
                'all_requests': formatted_requests
            })
        
        print(f"Returning {len(new_requests)} new requests")
        return jsonify({
            'processed_emails': False,
            'message': 'No new emails were processed',
            'new_requests': new_requests
        })
    
    except Exception as e:
        print(f"Error checking emails: {str(e)}")
        traceback_str = traceback.format_exc()
        print(f"Traceback: {traceback_str}")
        # Return empty list on error instead of error status
        return jsonify({'message': f'Error checking emails, but continuing: {str(e)}', 'new_requests': []}), 200

if __name__ == '__main__':
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'  # Remove in production
    socketio.run(app, debug=True, port=5000) 