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