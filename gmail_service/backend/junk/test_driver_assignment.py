import os
import json
from db_config import MongoDB
from request_manager import RequestManager
from driver_parser import DriverDetailsParser
from dotenv import load_dotenv

load_dotenv()

def test_agent_request():
    """Test sending a request to a driver agent."""
    # Initialize MongoDB and request manager
    mongodb = MongoDB()
    request_manager = RequestManager()
    
    # Ensure driver agent database is initialized
    if mongodb.drivers.count_documents({}) == 0:
        print("Driver agent database is empty. Initializing...")
        mongodb.init_driver_agents()
    
    # Print available agents
    available_agents = mongodb.get_available_drivers()
    print(f"Available agents: {len(available_agents)}")
    for agent in available_agents[:3]:  # Just show the first 3
        print(f"  - {agent['driver_id']}: {agent['email']}")
    
    # Load sample request from requests.json
    with open('requests.json', 'r') as f:
        requests = json.load(f)
    
    sample_request_id = next(iter(requests.keys()))
    sample_request = requests[sample_request_id]
    
    print(f"\nSending request to agent for {sample_request_id}...")
    assigned = request_manager.send_request_to_driver_agent(sample_request_id)
    
    if assigned:
        print("Request sent to agent successfully!")
        
        # Get updated request
        updated_request = request_manager.get_request(sample_request_id)
        print(f"Request now has agent_id (stored as driver_id): {updated_request.get('driver_id')}")
        
        # Get assignment
        assignment = mongodb.get_assignment_by_request(sample_request_id)
        if assignment:
            print(f"Assignment created: {assignment['assignment_id']}")
            print(f"Assignment status: {assignment['status']}")
        else:
            print("No assignment found!")
    else:
        print("Failed to send request to agent!")

def test_agent_response():
    """Test processing a sample driver agent response."""
    # Initialize request manager
    request_manager = RequestManager()
    
    # Create a sample driver agent response email
    if not os.getenv("GROQ_API_KEY"):
        print("GROQ_API_KEY environment variable is required for this test")
        return
    
    # Get request ID from requests.json
    with open('requests.json', 'r') as f:
        requests = json.load(f)
    
    sample_request_id = next(iter(requests.keys()))
    
    # Create a sample driver agent response email
    sample_response = {
        "id": "sample_agent_response_123",
        "subject": f"Re: Driver Needed for Request {sample_request_id}",
        "from": "abhijeet.kumar.csibm26@iilm.edu",  # Use an actual agent email from your database
        "date": "Wed, 9 Apr 2025 21:15:23 +0530",
        "body": """
Hello Booking Team,

I can confirm we have assigned a driver for this request:

Driver Details:
- Name: Robert Thompson
- Contact: +44792123456

Vehicle Information:
- Mercedes S-Class, Black
- Registration: LX21 ABC
- Features: WiFi, Water, Phone Chargers, Leather seats

The driver will arrive 30 minutes before the scheduled time and will be waiting with a name sign.

Best regards,
Driver Agent
"""
    }
    
    # Process the sample response
    print("\nProcessing sample agent response...")
    success = request_manager.process_driver_response(sample_response)
    
    if success:
        print("Agent response processed successfully!")
        
        # Get updated request
        updated_request = request_manager.get_request(sample_request_id)
        driver_details = updated_request.get('driver_details', {})
        print("\nDriver details added to request:")
        print(f"  Name: {driver_details.get('name')}")
        print(f"  Contact: {driver_details.get('contact')}")
        if 'vehicle' in driver_details:
            vehicle = driver_details['vehicle']
            print(f"  Vehicle: {vehicle.get('model')}, {vehicle.get('color')}")
            print(f"  Registration: {vehicle.get('registration')}")
    else:
        print("Failed to process agent response!")

def test_confirmation_with_driver_details():
    """Test sending confirmation email with driver details."""
    # Initialize request manager
    request_manager = RequestManager()
    
    # Get request ID from requests.json
    with open('requests.json', 'r') as f:
        requests = json.load(f)
    
    sample_request_id = next(iter(requests.keys()))
    
    # Ensure request has confirmation=True but confirmation_sent=False
    if sample_request_id in request_manager.requests:
        request_manager.requests[sample_request_id]['confirmation'] = True
        request_manager.requests[sample_request_id]['confirmation_sent'] = False
        request_manager._save_requests()
        
        print(f"\nSending confirmation email for request {sample_request_id}...")
        request_manager.send_confirmation_email(sample_request_id)
        
        # Verify confirmation was sent
        updated_request = request_manager.get_request(sample_request_id)
        if updated_request.get('confirmation_sent'):
            print("Confirmation email sent successfully!")
        else:
            print("Failed to send confirmation email!")

if __name__ == "__main__":
    print("=== Testing Driver Agent Request Flow ===")
    test_agent_request()
    
    print("\n=== Testing Driver Agent Response Processing ===")
    test_agent_response()
    
    print("\n=== Testing Confirmation Email With Driver Details ===")
    test_confirmation_with_driver_details() 