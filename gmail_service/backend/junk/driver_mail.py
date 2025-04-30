#!/usr/bin/env python
import os
import sys
from dotenv import load_dotenv
from request_manager import RequestManager
from db_config import MongoDB

load_dotenv()

def print_usage():
    """Print usage instructions."""
    print("\nUsage:")
    print("  python driver_mail.py mail <request_id> <driver_id>  - Send request to specific driver")
    print("  python driver_mail.py list                          - List pending requests")
    print("  python driver_mail.py agents                        - List available drivers")
    print("  python driver_mail.py monitor                       - Start monitoring in auto mode")
    print("")

def mail_request(request_id, driver_id):
    """Send a request to a driver agent."""
    request_manager = RequestManager()
    mongodb = MongoDB()
    
    # Check if request exists
    if request_id not in request_manager.requests:
        print(f"Request {request_id} not found.")
        return False
    
    # Check if driver exists
    driver = mongodb.get_driver_by_id(driver_id)
    if not driver:
        print(f"Driver agent {driver_id} not found.")
        print("Available driver agents:")
        drivers = mongodb.get_available_drivers()
        for driver in drivers:
            print(f"  {driver['driver_id']} - {driver['email']}")
        return False
    
    # Send request to driver
    print(f"Sending request {request_id} to driver {driver_id}...")
    result = request_manager.send_request_to_driver_agent(request_id, driver_id)
    
    if result:
        print(f"Successfully sent request {request_id} to driver agent {driver_id} ({driver['email']}).")
        return True
    else:
        print(f"Failed to send request {request_id} to driver agent {driver_id}.")
        return False

def list_requests():
    """List all pending requests."""
    request_manager = RequestManager()
    pending_requests = request_manager.get_pending_requests()
    
    if not pending_requests:
        print("No pending requests found.")
        return
    
    print("\n=== Pending Requests ===")
    print(f"{'Request ID':<20} {'Status':<15} {'Guest':<20} {'Date':<12} {'Flight':<10}")
    print("-" * 80)
    
    for req in pending_requests:
        # Request ID could be in 'id', 'request_id', or be the dictionary key
        req_id = req.get('id') or req.get('request_id')
        status = req.get('status', 'pending')
        
        # Get processed data if available
        proc_data = req.get('processed_data', {})
        guest = proc_data.get('guest_name', 'N/A')
        date = proc_data.get('date', 'N/A')
        flight = proc_data.get('flight_no', 'N/A')
        
        print(f"{req_id:<20} {status:<15} {guest:<20} {date:<12} {flight:<10}")

def list_drivers():
    """List all available driver agents."""
    mongodb = MongoDB()
    drivers = mongodb.get_available_drivers()
    
    if not drivers:
        print("No driver agents found.")
        return
    
    print("\n=== Driver Agents ===")
    print(f"{'Driver ID':<10} {'Status':<15} {'Email':<30}")
    print("-" * 60)
    
    for driver in drivers:
        driver_id = driver.get('driver_id', 'N/A')
        status = driver.get('status', 'N/A')
        email = driver.get('email', 'N/A')
        
        print(f"{driver_id:<10} {status:<15} {email:<30}")

def start_monitor():
    """Start monitoring in auto mode."""
    import subprocess
    subprocess.run(["python", "monitor_main.py", "--auto"])

def main():
    """Main entry point for the script."""
    if len(sys.argv) < 2:
        print_usage()
        return
    
    command = sys.argv[1].lower()
    
    if command == "mail":
        # Check for required arguments
        if len(sys.argv) < 4:
            print("Error: Missing arguments.")
            print("Usage: python driver_mail.py mail <request_id> <driver_id>")
            return
        
        request_id = sys.argv[2]
        driver_id = sys.argv[3]
        mail_request(request_id, driver_id)
    
    elif command == "list":
        list_requests()
    
    elif command == "agents":
        list_drivers()
    
    elif command == "monitor":
        start_monitor()
    
    else:
        print(f"Unknown command: {command}")
        print_usage()

if __name__ == "__main__":
    main() 