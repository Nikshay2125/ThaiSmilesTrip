#!/usr/bin/env python
import os
import sys
import argparse
from dotenv import load_dotenv
from request_manager import RequestManager
from db_config import MongoDB

load_dotenv()

def send_request_to_driver(request_id, driver_id=None):
    """Send a request to a specific driver agent or the first available one."""
    request_manager = RequestManager()
    mongodb = MongoDB()
    
    # Check if request exists
    if request_id not in request_manager.requests:
        print(f"Request {request_id} not found.")
        return False
    
    # If driver_id is specified, verify it exists
    if driver_id:
        driver = mongodb.get_driver_by_id(driver_id)
        if not driver:
            print(f"Driver agent {driver_id} not found.")
            print("Available driver agents:")
            drivers = mongodb.get_available_drivers()
            for driver in drivers:
                print(f"  {driver['driver_id']} - {driver['email']}")
            return False
    else:
        # Get available driver agents
        available_agents = mongodb.get_available_drivers()
        if not available_agents:
            print("No available driver agents")
            return False
        
        driver_id = available_agents[0]['driver_id']
        print(f"Selected first available driver agent: {driver_id}")
    
    # Send the request to the driver agent
    result = request_manager.send_request_to_driver_agent(request_id, driver_id)
    if result:
        driver = mongodb.get_driver_by_id(driver_id)
        print(f"Successfully sent request {request_id} to driver agent {driver_id} ({driver['email']}).")
        return True
    else:
        print(f"Failed to send request {request_id} to driver agent {driver_id}.")
        return False

def list_pending_requests():
    """List all pending requests that can be assigned to a driver."""
    request_manager = RequestManager()
    pending_requests = request_manager.get_pending_requests()
    
    if not pending_requests:
        print("No pending requests found.")
        return
    
    print("\n=== Pending Requests ===")
    print(f"{'Request ID':<20} {'Status':<15} {'Guest':<20} {'Date':<12} {'Flight':<10}")
    print("-" * 80)
    
    for req in pending_requests:
        req_id = req.get('request_id', 'N/A')
        status = req.get('status', 'pending')
        
        # Get processed data if available
        proc_data = req.get('processed_data', {})
        guest = proc_data.get('guest_name', 'N/A')
        date = proc_data.get('date', 'N/A')
        flight = proc_data.get('flight_no', 'N/A')
        
        print(f"{req_id:<20} {status:<15} {guest:<20} {date:<12} {flight:<10}")

def list_driver_agents():
    """List all available driver agents."""
    mongodb = MongoDB()
    drivers = mongodb.get_available_drivers()
    
    if not drivers:
        print("No driver agents found.")
        return
    
    print("\n=== Driver Agents ===")
    print(f"{'Driver ID':<10} {'Status':<15} {'Email':<30} {'Assignments'}")
    print("-" * 80)
    
    for driver in drivers:
        driver_id = driver.get('driver_id', 'N/A')
        status = driver.get('status', 'N/A')
        email = driver.get('email', 'N/A')
        assignments = driver.get('current_assignments', [])
        
        assignment_count = len(assignments)
        assignment_str = f"{assignment_count} requests" if assignment_count else "None"
        
        print(f"{driver_id:<10} {status:<15} {email:<30} {assignment_str}")
        
        # Show assignments if any
        if assignments:
            for i, req_id in enumerate(assignments[:3]):  # Show up to 3 assignments
                print(f"{'':<10} {'':<15} {'':<30} - {req_id}")
            
            if len(assignments) > 3:
                print(f"{'':<10} {'':<15} {'':<30} - ... and {len(assignments) - 3} more")

def main():
    """Command-line interface for sending requests to driver agents."""
    parser = argparse.ArgumentParser(description="Send requests to driver agents")
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # List requests command
    list_parser = subparsers.add_parser("list", help="List pending requests")
    
    # List driver agents command
    list_agents_parser = subparsers.add_parser("agents", help="List available driver agents")
    
    # Send request command
    send_parser = subparsers.add_parser("send", help="Send a request to a driver agent")
    send_parser.add_argument("request_id", help="Request ID to send")
    send_parser.add_argument("--driver", help="Driver agent ID (optional, will use first available if not specified)")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Process commands
    if args.command == "list":
        list_pending_requests()
    elif args.command == "agents":
        list_driver_agents()
    elif args.command == "send":
        driver_id = args.driver if hasattr(args, 'driver') else None
        send_request_to_driver(args.request_id, driver_id)
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 