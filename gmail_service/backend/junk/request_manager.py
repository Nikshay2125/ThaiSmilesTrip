import json
import os
from typing import Dict, List, Optional
from datetime import datetime
from gmail_fetch import send_email
from db_config import MongoDB
from driver_parser import DriverDetailsParser
import re  # For regex operations in driver response processing

class RequestManager:
    def __init__(self, json_file: str = "requests.json"):
        self.json_file = json_file
        self.requests = self._load_requests()
        self.email_id_to_request = self._build_email_id_map()
        self.mongodb = MongoDB()
        # Initialize driver parser if GROQ API key is available
        self.driver_parser = None
        if os.getenv("GROQ_API_KEY"):
            self.driver_parser = DriverDetailsParser(os.getenv("GROQ_API_KEY"))

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
                
                # Check if we have driver details
                driver_details_text = ""
                if "driver_details" in request and request["driver_details"]:
                    driver = request["driver_details"]
                    vehicle = driver.get("vehicle", {})
                    driver_details_text = f"""
Your driver details:
Name: {driver.get('name')}
Contact: {driver.get('contact')}
Vehicle: {vehicle.get('model')} ({vehicle.get('color')})
Registration: {vehicle.get('registration')}
Features: {vehicle.get('features', 'N/A')}
Estimated arrival: {driver.get('estimated_arrival')}

{driver.get('notes', '')}
"""
                
                body = f"""
Dear {sender_email.split('@')[0].split('<')[0]},

Your request has been confirmed.

Request ID: {request_id}
Confirmed at: {datetime.now().isoformat()}
{driver_details_text}
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
            
            # After processing, send email to a driver agent
            self.send_request_to_driver_agent(request_id)
            
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
                
                if (current_date > created_date) or (current_time - created_at > timedelta(hours=24)):
                    to_remove.append(req_id)
        
        for req_id in to_remove:
            self._cleanup_json_request(req_id)
    
    def _cleanup_json_request(self, request_id: str):
        """Remove a processed request from JSON but keep it in MongoDB."""
        if request_id in self.requests:
            email_id = self.requests[request_id].get('email_data', {}).get('id')
            if email_id and email_id in self.email_id_to_request:
                del self.email_id_to_request[email_id]
            del self.requests[request_id]
            self._save_requests()

    # New methods for driver agent management
    
    def send_request_to_driver_agent(self, request_id: str, agent_id: str = None) -> bool:
        """Send request to a driver agent (not directly to a driver) and wait for their response."""
        if request_id not in self.requests:
            return False
            
        # If agent_id not specified, select the first available agent
        if not agent_id:
            # Get available driver agents
            available_agents = self.mongodb.get_available_drivers()
            if not available_agents:
                print("No available driver agents")
                return False
                
            # Select the first available agent 
            # (in a real system, implement logic to select the most suitable agent)
            agent = available_agents[0]
            agent_id = agent['driver_id']
            agent_email = agent['email']
        else:
            # Get the specified agent
            agent = self.mongodb.get_driver_by_id(agent_id)
            if not agent:
                print(f"Agent {agent_id} not found")
                return False
            agent_email = agent['email']
        
        # Create assignment in MongoDB
        try:
            # Create assignment record
            self.mongodb.create_assignment(request_id, agent_id)
            
            # Update JSON with agent ID (stored as driver_id for compatibility)
            self.requests[request_id]['driver_id'] = agent_id
            self.requests[request_id]['assignment_id'] = f"ASG_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self._save_requests()
            
            # Send notification to driver agent
            self._send_agent_request_email(request_id, agent_email)
            
            return True
        except Exception as e:
            print(f"Error sending request to driver agent: {str(e)}")
            return False
    
    def _send_agent_request_email(self, request_id: str, agent_email: str):
        """Send email to driver agent with booking request details."""
        if request_id not in self.requests:
            return
            
        request = self.requests[request_id]
        processed_data = request.get('processed_data', {})
        
        subject = f"Driver Needed for Request {request_id}"
        
        # Format a detailed email with all relevant booking info
        pickup_date = processed_data.get('date', 'Not specified')
        pickup_time = processed_data.get('pickup_time', 'Not specified')
        pickup_location = processed_data.get('pickup_location', 'Not specified')
        guest_name = processed_data.get('guest_name', 'Not specified')
        pax = processed_data.get('pax', 'Not specified')
        flight = processed_data.get('flight_no', 'Not specified')
        hotel = processed_data.get('hotel_drop', 'Not specified')
        
        body = f"""
Dear Driver Agent,

We have a new transportation request that needs a driver assignment:

Request ID: {request_id}
Passenger: {guest_name}
Number of passengers: {pax}
Date: {pickup_date}
Time: {pickup_time}
Flight: {flight}
Pickup Location: {pickup_location}
Destination: {hotel}

Please reply to this email with the driver details for this assignment including:
- Driver's full name
- Driver's contact number
- Vehicle details (make, model, color, registration)
- Any additional information or special arrangements

IMPORTANT: Keep the original subject line in your reply so we can track this request.

Once we receive your response, we will confirm with the customer.

Best regards,
Booking Team
"""
        send_email(agent_email, subject, body)
    
    def process_driver_response(self, email_data: Dict) -> bool:
        """Process a driver agent's response containing driver details."""
        if not self.driver_parser:
            print("Driver parser not initialized")
            return False
            
        # Extract request ID from the email subject
        subject = email_data.get('subject', '')
        req_id_match = re.search(r'(RE: |Re: |)Driver Needed for Request (REQ_\d+_\d+_\d+)', subject, re.IGNORECASE)
        if not req_id_match:
            print("Could not find request ID in subject")
            return False
            
        # Get the matched group that contains the request ID (group 2)
        request_id = req_id_match.group(2)
        
        if request_id not in self.requests:
            print(f"Request {request_id} not found")
            return False
        
        # Get driver details by parsing the email body
        driver_details = self.driver_parser.parse_driver_details(email_data.get('body', ''))
        if not driver_details or not driver_details.get('name'):
            print("Could not parse driver details")
            return False
            
        print(f"Parsed driver details: {driver_details['name']} ({driver_details['contact']})")
        print(f"Vehicle: {driver_details['vehicle']['model']} {driver_details['vehicle']['color']} ({driver_details['vehicle']['registration']})")
            
        # Update request with driver details in both JSON and MongoDB
        try:
            # Update MongoDB assignment
            self.mongodb.update_driver_details(request_id, driver_details)
            
            # Update JSON
            self.requests[request_id]['driver_details'] = driver_details
            self._save_requests()
            
            print(f"Driver details updated for request {request_id}")
            return True
        except Exception as e:
            print(f"Error updating driver details: {str(e)}")
            return False 