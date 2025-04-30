#!/usr/bin/env python
import os
import sys
import argparse
from bson.objectid import ObjectId
from db_config import MongoDB
from dotenv import load_dotenv

load_dotenv()

def clear_all_assignments(mongodb):
    """Clear all driver assignments in the database."""
    # Remove assignments field from all requests
    result_requests = mongodb.requests.update_many(
        {"assigned_to": {"$exists": True}},
        {"$unset": {"assigned_to": ""}}
    )
    
    # Update all drivers to remove their assignments
    result_drivers = mongodb.drivers.update_many(
        {"assignments": {"$exists": True, "$ne": []}},
        {"$set": {"assignments": []}}
    )
    
    print(f"Cleared assignments from {result_requests.modified_count} requests")
    print(f"Reset assignments for {result_drivers.modified_count} drivers")

def clear_request_assignment(mongodb, request_id):
    """Clear assignment for a specific request."""
    try:
        # Convert string ID to ObjectId if necessary
        if not isinstance(request_id, ObjectId):
            request_id = ObjectId(request_id)
        
        # Find the request to get assigned driver
        request = mongodb.requests.find_one({"_id": request_id})
        if not request:
            print(f"Request with ID {request_id} not found")
            return
        
        if "assigned_to" not in request:
            print(f"Request {request_id} is not assigned to any driver")
            return
        
        driver_id = request["assigned_to"]
        
        # Remove assignment from request
        mongodb.requests.update_one(
            {"_id": request_id},
            {"$unset": {"assigned_to": ""}}
        )
        
        # Remove request from driver's assignments
        mongodb.drivers.update_one(
            {"_id": driver_id},
            {"$pull": {"assignments": request_id}}
        )
        
        print(f"Cleared assignment for request {request_id}")
        print(f"Removed request from driver {driver_id}'s assignments")
        
    except Exception as e:
        print(f"Error clearing request assignment: {str(e)}")

def clear_driver_assignments(mongodb, driver_id):
    """Clear all assignments for a specific driver."""
    try:
        # Convert string ID to ObjectId if necessary
        if not isinstance(driver_id, ObjectId):
            driver_id = ObjectId(driver_id)
        
        # Find the driver to get their assignments
        driver = mongodb.drivers.find_one({"_id": driver_id})
        if not driver:
            print(f"Driver with ID {driver_id} not found")
            return
        
        if "assignments" not in driver or not driver["assignments"]:
            print(f"Driver {driver_id} has no assignments")
            return
        
        # Get the list of assigned requests
        assigned_requests = driver["assignments"]
        
        # Remove assignments from all requests assigned to this driver
        result_requests = mongodb.requests.update_many(
            {"_id": {"$in": assigned_requests}},
            {"$unset": {"assigned_to": ""}}
        )
        
        # Clear driver's assignments
        mongodb.drivers.update_one(
            {"_id": driver_id},
            {"$set": {"assignments": []}}
        )
        
        print(f"Cleared {len(assigned_requests)} assignments for driver {driver_id}")
        print(f"Updated {result_requests.modified_count} requests")
        
    except Exception as e:
        print(f"Error clearing driver assignments: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description="Clear driver assignments from the database")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="Clear all assignments")
    group.add_argument("--request-id", type=str, help="Clear assignment for specific request ID")
    group.add_argument("--driver-id", type=str, help="Clear all assignments for specific driver ID")
    
    args = parser.parse_args()
    
    # Initialize database connection
    mongodb = MongoDB()
    
    if args.all:
        clear_all_assignments(mongodb)
    elif args.request_id:
        clear_request_assignment(mongodb, args.request_id)
    elif args.driver_id:
        clear_driver_assignments(mongodb, args.driver_id)

if __name__ == "__main__":
    main() 