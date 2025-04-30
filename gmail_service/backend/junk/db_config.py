from pymongo import MongoClient
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# MongoDB connection
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017')
DB_NAME = os.getenv('DB_NAME', 'email_service')

class MongoDB:
    def __init__(self):
        self.client = MongoClient(MONGO_URI)
        self.db = self.client[DB_NAME]
        self.requests = self.db.requests
        self.drivers = self.db.drivers
        self.assignments = self.db.assignments

    def insert_request(self, request_data):
        """Insert processed request data into MongoDB."""
        processed_data = {
            'request_id': request_data['id'],
            'email_id': request_data['email_data']['id'],  # Keep email ID for reference
            'sender': request_data['email_data']['from'],
            'processed_data': {
                # Add your parsed information here
                'booking_ref': None,  # Will be updated with parsed data
                'arrival_date': None,
                'flight_number': None,
                'pickup_time': None,
                'guests_count': None,
                'hotel': None
            },
            'status': request_data['status'],
            'created_at': datetime.fromisoformat(request_data['created_at']),
            'confirmation_sent': request_data['confirmation_sent'],
            'confirmation_status': request_data['confirmation']
        }
        return self.requests.insert_one(processed_data)

    def update_request_status(self, request_id, status):
        """Update request status in MongoDB."""
        return self.requests.update_one(
            {'request_id': request_id},
            {'$set': {'status': status}}
        )

    def update_confirmation(self, request_id, confirmation_status):
        """Update confirmation status in MongoDB."""
        return self.requests.update_one(
            {'request_id': request_id},
            {'$set': {
                'confirmation_status': confirmation_status,
                'confirmation_sent': True
            }}
        )

    def get_request(self, request_id):
        """Get request by ID."""
        return self.requests.find_one({'request_id': request_id})

    def get_request_by_email_id(self, email_id):
        """Get request by email ID."""
        return self.requests.find_one({'email_id': email_id})

    def get_all_requests(self):
        """Get all requests."""
        return list(self.requests.find())
        
    # Driver-related methods
    def init_driver_agents(self):
        """Initialize driver agents if they don't exist."""
        if self.drivers.count_documents({}) == 0:
            # Create initial driver agents
            for i in range(18):
                driver_id = f"D{i}"
                self.drivers.insert_one({
                    'driver_id': driver_id,
                    'email': f"driver{i}@example.com",  # Replace with actual emails
                    'status': 'available',
                    'current_assignments': []
                })
            return True
        return False
    
    def get_available_drivers(self):
        """Get a list of available drivers."""
        return list(self.drivers.find({'status': 'available'}))
    
    def get_driver_by_email(self, email):
        """Get driver by email address."""
        return self.drivers.find_one({'email': email})
        
    def get_driver_by_id(self, driver_id):
        """Get driver by ID."""
        return self.drivers.find_one({'driver_id': driver_id})
    
    def update_driver_status(self, driver_id, status):
        """Update driver status."""
        return self.drivers.update_one(
            {'driver_id': driver_id},
            {'$set': {'status': status}}
        )
    
    def add_assignment_to_driver(self, driver_id, request_id):
        """Add assignment to driver's current assignments."""
        return self.drivers.update_one(
            {'driver_id': driver_id},
            {'$push': {'current_assignments': request_id}}
        )
    
    def remove_assignment_from_driver(self, driver_id, request_id):
        """Remove assignment from driver's current assignments."""
        return self.drivers.update_one(
            {'driver_id': driver_id},
            {'$pull': {'current_assignments': request_id}}
        )
    
    # Assignment-related methods
    def create_assignment(self, request_id, driver_id):
        """Create a new assignment."""
        assignment = {
            'assignment_id': f"ASG_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'request_id': request_id,
            'driver_id': driver_id,
            'assignment_time': datetime.now(),
            'estimated_arrival': None,
            'actual_arrival': None,
            'completion_time': None,
            'status': 'assigned',
            'notes': None,
            'driver_details': None  # This will be populated when driver replies
        }
        result = self.assignments.insert_one(assignment)
        
        # Associate driver with request
        self.requests.update_one(
            {'request_id': request_id},
            {'$set': {'driver_id': driver_id}}
        )
        
        # Add assignment to driver's assignments list without changing status
        # Driver agents remain available for multiple assignments
        self.add_assignment_to_driver(driver_id, request_id)
        
        return result
    
    def update_assignment_status(self, assignment_id, status):
        """Update assignment status."""
        return self.assignments.update_one(
            {'assignment_id': assignment_id},
            {'$set': {'status': status}}
        )
    
    def get_assignment_by_request(self, request_id):
        """Get assignment by request ID."""
        return self.assignments.find_one({'request_id': request_id})
    
    def update_driver_details(self, request_id, driver_details):
        """Update driver details in the assignment."""
        assignment = self.get_assignment_by_request(request_id)
        if not assignment:
            return None
            
        return self.assignments.update_one(
            {'request_id': request_id},
            {'$set': {'driver_details': driver_details}}
        )
    
    def get_driver_details(self, request_id):
        """Get driver details for a request."""
        assignment = self.get_assignment_by_request(request_id)
        if not assignment:
            return None
        return assignment.get('driver_details') 