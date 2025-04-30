import os
from db_config import MongoDB
from dotenv import load_dotenv

load_dotenv()

def init_driver_agent_database():
    """Initialize the driver agent database with test agents."""
    mongodb = MongoDB()
    
    # Check if driver agents collection already has data
    agent_count = mongodb.drivers.count_documents({})
    
    if agent_count > 0:
        print(f"Driver agent database already contains {agent_count} agents.")
        return False
    
    # Configure your actual agent emails here
    agent_emails = [
        "abhijeet.kumar.csibm26@iilm.edu"
        # Add more agent emails as needed
    ]
    
    # Create driver agent documents
    for i, email in enumerate(agent_emails):
        agent_id = f"D{i}"
        mongodb.drivers.insert_one({
            'driver_id': agent_id,  # Using driver_id for compatibility
            'email': email,
            'status': 'available',
            'current_assignments': []
        })
    
    print(f"Successfully initialized driver agent database with {len(agent_emails)} agents.")
    return True

if __name__ == "__main__":
    init_driver_agent_database() 