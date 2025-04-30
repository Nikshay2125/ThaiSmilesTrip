import os
import sys
import json
import argparse
from typing import List, Dict, Optional
from dotenv import load_dotenv
from request_manager import RequestManager
from db_config import MongoDB
import subprocess

load_dotenv()

def list_requests(request_manager: RequestManager, status_filter: Optional[str] = None):
    """List all requests, optionally filtered by status."""
    requests = request_manager.requests
    
    if not requests:
        print("No requests found.")
        return
    
    filtered_requests = {}
    for req_id, req in requests.items():
        if status_filter and req.get('status') != status_filter:
            continue
        filtered_requests[req_id] = req
    
    if not filtered_requests:
        print(f"No requests with status '{status_filter}' found.")
        return
        
    print(f"\n{'=' * 80}")
    print(f"{'REQUEST ID':<25} {'STATUS':<12} {'DRIVER ID':<10} {'CUSTOMER':<30}")
    print(f"{'-' * 25} {'-' * 12} {'-' * 10} {'-' * 30}")
    
    for req_id, req in filtered_requests.items():
        status = req.get('status', 'unknown')
        driver_id = req.get('driver_id', 'N/A')
        customer = req.get('email_data', {}).get('from', 'Unknown')
        if len(customer) > 30:
            customer = customer[:27] + '...'
        print(f"{req_id:<25} {status:<12} {driver_id:<10} {customer:<30}")
    
    print(f"{'=' * 80}\n")

def list_driver_agents(mongodb: MongoDB):
    """List all driver agents with their current assignments."""
    agents = list(mongodb.drivers.find())
    
    if not agents:
        print("No driver agents found.")
        return
    
    print(f"\n{'=' * 80}")
    print(f"{'AGENT ID':<10} {'STATUS':<12} {'EMAIL':<30} {'ASSIGNMENTS'}")
    print(f"{'-' * 10} {'-' * 12} {'-' * 30} {'-' * 27}")
    
    for agent in agents:
        agent_id = agent.get('driver_id', 'unknown')
        status = agent.get('status', 'unknown')
        email = agent.get('email', 'unknown')
        assignments = agent.get('current_assignments', [])
        
        # Get assignment count
        assignment_count = len(assignments)
        assignment_str = f"{assignment_count} requests" if assignment_count else "None"
        
        print(f"{agent_id:<10} {status:<12} {email:<30} {assignment_str}")
        
        # Show assignments if any
        if assignments:
            for i, req_id in enumerate(assignments[:3]):  # Show up to 3 assignments
                print(f"{'':<10} {'':<12} {'':<30} - {req_id}")
            
            if len(assignments) > 3:
                print(f"{'':<10} {'':<12} {'':<30} - ... and {len(assignments) - 3} more")
    
    print(f"{'=' * 80}\n")

def assign_driver_agent(request_manager: RequestManager, request_id: str, agent_id: str):
    """Assign a specific driver agent to a request."""
    if request_id not in request_manager.requests:
        print(f"Request {request_id} not found.")
        return False
    
    request = request_manager.requests[request_id]
    if request.get('driver_id'):
        print(f"Request {request_id} already has driver agent {request.get('driver_id')} assigned.")
        confirm = input("Do you want to reassign? (y/n): ")
        if confirm.lower() != 'y':
            return False
    
    # Check if the agent exists
    agent = request_manager.mongodb.get_driver_by_id(agent_id)
    if not agent:
        print(f"Driver agent {agent_id} not found.")
        return False
    
    # Check if the agent is available
    if agent.get('status') != 'available':
        print(f"Driver agent {agent_id} is not available (status: {agent.get('status')}).")
        confirm = input("Assign anyway? (y/n): ")
        if confirm.lower() != 'y':
            return False
    
    # Send the request to the driver agent
    result = request_manager.send_request_to_driver_agent(request_id, agent_id)
    if result:
        print(f"Successfully assigned driver agent {agent_id} to request {request_id}.")
        print(f"Request email sent to: {agent.get('email')}")
        return True
    else:
        print(f"Failed to assign driver agent {agent_id} to request {request_id}.")
        return False

def confirm_request(request_manager: RequestManager, request_id: str):
    """Manually confirm a request."""
    if request_id not in request_manager.requests:
        print(f"Request {request_id} not found.")
        return False
    
    request = request_manager.requests[request_id]
    
    # Check if driver details are available
    if not request.get('driver_details'):
        print(f"Warning: Request {request_id} has no driver details.")
        confirm = input("Do you want to confirm anyway? (y/n): ")
        if confirm.lower() != 'y':
            return False
    
    request_manager.set_confirmation(request_id, True)
    print(f"Request {request_id} has been confirmed.")
    print("Confirmation email will be sent to the customer.")
    return True

def reset_assignments(mongodb: MongoDB):
    """Reset driver assignments with options to clear specific or all assignments."""
    print("\n=== Reset Driver Assignments ===")
    print("1. Clear all assignments")
    print("2. Clear assignments for specific request")
    print("3. Clear assignments for specific driver")
    print("4. Return to main menu")
    
    choice = input("\nSelect an option (1-4): ")
    
    if choice == "1":
        confirm = input("Are you sure you want to clear ALL assignments? (y/n): ")
        if confirm.lower() == 'y':
            subprocess.run(["python", "clear_assignments.py", "--all"])
            print("All assignments have been cleared.")
    elif choice == "2":
        request_id = input("Enter request ID to clear: ")
        if request_id:
            subprocess.run(["python", "clear_assignments.py", "--request-id", request_id])
            print(f"Assignments for request {request_id} have been cleared.")
    elif choice == "3":
        driver_id = input("Enter driver ID to clear: ")
        if driver_id:
            subprocess.run(["python", "clear_assignments.py", "--driver-id", driver_id])
            print(f"Assignments for driver {driver_id} have been cleared.")
    elif choice == "4":
        return
    else:
        print("Invalid option. Please try again.")

def main():
    """Command-line interface for manual driver agent assignment."""
    parser = argparse.ArgumentParser(description="Manage requests and driver agent assignments")
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # List requests command
    list_parser = subparsers.add_parser("list", help="List requests")
    list_parser.add_argument("--status", help="Filter by status (pending, processed, confirmed)")
    
    # List driver agents command
    list_agents_parser = subparsers.add_parser("agents", help="List available driver agents")
    
    # Assign driver agent command
    assign_parser = subparsers.add_parser("assign", help="Assign a driver agent to a request")
    assign_parser.add_argument("request_id", help="Request ID to assign")
    assign_parser.add_argument("agent_id", help="Driver agent ID to assign")
    
    # Confirm request command
    confirm_parser = subparsers.add_parser("confirm", help="Confirm a request")
    confirm_parser.add_argument("request_id", help="Request ID to confirm")
    
    args = parser.parse_args()
    
    # Initialize managers
    request_manager = RequestManager()
    mongodb = MongoDB()
    
    # Process commands
    if args.command == "list":
        list_requests(request_manager, args.status)
    elif args.command == "agents":
        list_driver_agents(mongodb)
    elif args.command == "assign":
        assign_driver_agent(request_manager, args.request_id, args.agent_id)
    elif args.command == "confirm":
        confirm_request(request_manager, args.request_id)
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 