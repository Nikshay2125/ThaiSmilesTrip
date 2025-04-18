import json
import os
from typing import Dict, List, Optional
from datetime import datetime
from gmail_fetch import send_email
from db_config import MongoDB

class RequestManager:
    def __init__(self, json_file: str = "requests.json"):
        self.json_file = json_file
        self.requests = self._load_requests()
        self.email_id_to_request = self._build_email_id_map()
        self.mongodb = MongoDB()

    def _load_requests(self) -> Dict:
        """Load requests from JSON file or create new if doesn't exist."""
        if os.path.exists(self.json_file):
            try:
                with open(self.json_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}

    def _build_email_id_map(self) -> Dict[str, str]:
        """Build a map of email IDs to request IDs."""
        email_id_map = {}
        for req_id, req in self.requests.items():
            email_id = req.get('email_data', {}).get('id')
            if email_id:
                email_id_map[email_id] = req_id
        return email_id_map

    def _save_requests(self):
        """Save requests to JSON file."""
        with open(self.json_file, 'w') as f:
            json.dump(self.requests, f, indent=2)

    def get_request_by_email_id(self, email_id: str) -> Optional[str]:
        """Get request ID by email ID if it exists."""
        return self.email_id_to_request.get(email_id)

    def add_request(self, email_data: Dict) -> str:
        """Add a new request and send acknowledgment email."""
        # Check if email already exists
        email_id = email_data.get('id')
        if email_id:
            # Check MongoDB first
            existing_mongo_req = self.mongodb.get_request_by_email_id(email_id)
            if existing_mongo_req:
                print(f"Email already processed as request: {existing_mongo_req['request_id']}")
                return existing_mongo_req['request_id']
            
            # Then check JSON
            if email_id in self.email_id_to_request:
                existing_req_id = self.email_id_to_request[email_id]
                print(f"Email already processed as request: {existing_req_id}")
                return existing_req_id

        request_id = f"REQ_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(self.requests)}"
        
        # Create request entry
        request = {
            "id": request_id,
            "email_data": email_data,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "confirmation_sent": False,
            "confirmation": False
        }
        
        # Store request in JSON first
        self.requests[request_id] = request
        if email_id:
            self.email_id_to_request[email_id] = request_id
        self._save_requests()
        
        # Send acknowledgment email
        self._send_acknowledgment_email(request)
        
        return request_id

    def _send_acknowledgment_email(self, request: Dict):
        """Send acknowledgment email to the sender."""
        sender_email = request["email_data"]["from"]
        subject = f"Request Received - {request['id']}"
        body = f"""
Dear {sender_email.split('@')[0].split('<')[0]},

Thank you for your request. We have received it and will process it shortly.

Request ID: {request['id']}
Received at: {request['created_at']}

We will send you a confirmation email once your request is processed.

Best regards,
Your Service Team
"""
        send_email(sender_email, subject, body, reply_to=request["email_data"])

    def send_confirmation_email(self, request_id: str):
        """Send confirmation email for a confirmed request."""
        if request_id in self.requests:
            request = self.requests[request_id]
            if request["confirmation"] and not request["confirmation_sent"]:
                sender_email = request["email_data"]["from"]
                subject = f"Request Confirmed - {request_id}"
                body = f"""
Dear {sender_email.split('@')[0].split('<')[0]},

Your request has been confirmed.

Request ID: {request_id}
Confirmed at: {datetime.now().isoformat()}

Thank you for choosing our service.

Best regards,
Your Service Team
"""
                send_email(sender_email, subject, body, reply_to=request["email_data"])
                request["confirmation_sent"] = True
                self._save_requests()

    def get_pending_requests(self) -> List[Dict]:
        """Get all pending requests."""
        return [req for req in self.requests.values() if req["status"] == "pending"]

    def update_request_status(self, request_id: str, status: str):
        """Update request status in both JSON and MongoDB."""
        # Update MongoDB if exists
        self.mongodb.update_request_status(request_id, status)
        
        # Update JSON if exists
        if request_id in self.requests:
            self.requests[request_id]["status"] = status
            self._save_requests()

    def set_confirmation(self, request_id: str, confirmed: bool):
        """Set confirmation status in both JSON and MongoDB."""
        # Update MongoDB if exists
        self.mongodb.update_confirmation(request_id, confirmed)
        
        # Update JSON if exists
        if request_id in self.requests:
            self.requests[request_id]["confirmation"] = confirmed
            self._save_requests()
            if confirmed:
                self.send_confirmation_email(request_id)

    def get_request(self, request_id: str) -> Optional[Dict]:
        """Get request from either JSON or MongoDB."""
        # Try MongoDB first
        mongo_request = self.mongodb.get_request(request_id)
        if mongo_request:
            return mongo_request
        
        # Fall back to JSON
        return self.requests.get(request_id)

    def process_and_store_in_mongodb(self, request_id: str, parsed_data: Dict):
        """Process request and store in MongoDB."""
        if request_id not in self.requests:
            return False
        
        request = self.requests[request_id]
        
        try:
            # Store in MongoDB
            self.mongodb.insert_request(request)
            
            # Update MongoDB with parsed data
            self.mongodb.requests.update_one(
                {'request_id': request_id},
                {'$set': {'processed_data': parsed_data}}
            )
            
            # Keep the request in JSON but mark it as processed
            request['status'] = 'processed'
            request['processed_data'] = parsed_data
            self._save_requests()
            
            return True
            
        except Exception as e:
            print(f"Error storing in MongoDB: {str(e)}")
            return False

    def cleanup_processed_requests(self):
        """Clean up processed requests from JSON that are older than 24 hours and from previous days."""
        from datetime import datetime, timedelta
        
        current_time = datetime.now()
        current_date = current_time.date()
        to_remove = []
        
        for req_id, req in self.requests.items():
            if req['status'] == 'processed':
                created_at = datetime.fromisoformat(req['created_at'])
                created_date = created_at.date()
                
                # Only remove if:
                # 1. Request is from a previous day (not today)
                # 2. Request is older than 24 hours
                # 3. Request has been processed
                if (created_date < current_date and 
                    current_time - created_at > timedelta(hours=24)):
                    to_remove.append(req_id)
        
        for req_id in to_remove:
            # Double check the request is in MongoDB before removing from JSON
            mongo_request = self.mongodb.get_request(req_id)
            if mongo_request:
                self._cleanup_json_request(req_id)
            else:
                print(f"Warning: Request {req_id} not found in MongoDB, keeping in JSON storage")
            
        if to_remove:
            print(f"Cleaned up {len(to_remove)} processed requests from previous days from JSON storage")

    def _cleanup_json_request(self, request_id: str):
        """Remove request from JSON file after processing."""
        if request_id in self.requests:
            email_id = self.requests[request_id]['email_data'].get('id')
            if email_id and email_id in self.email_id_to_request:
                del self.email_id_to_request[email_id]
            del self.requests[request_id]
            self._save_requests() 