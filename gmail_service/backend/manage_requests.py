import json
from request_manager import RequestManager
import argparse

def list_requests(request_manager: RequestManager):
    """List all requests with their status."""
    requests = request_manager.requests
    if not requests:
        print("No requests found.")
        return
    
    print("\nCurrent Requests:")
    output = []
    for req_id, req in requests.items():
        request_info = {
            "id": req_id,
            "from": req['email_data']['from'],
            "subject": req['email_data']['subject'],
            "status": req['status'],
            "created_at": req['created_at'],
            "confirmation": "Sent" if req['confirmation_sent'] else "Pending"
        }
        output.append(request_info)
    
    print(json.dumps(output, indent=2))

def confirm_request(request_manager: RequestManager, request_id: str):
    """Confirm a specific request."""
    if request_id in request_manager.requests:
        request_manager.set_confirmation(request_id, True)
        print(f"Request {request_id} confirmed and confirmation email sent.")
    else:
        print(f"Request {request_id} not found.")

def update_status(request_manager: RequestManager, request_id: str, status: str):
    """Update status of a specific request."""
    if request_id in request_manager.requests:
        request_manager.update_request_status(request_id, status)
        print(f"Status updated for request {request_id} to {status}")
    else:
        print(f"Request {request_id} not found.")

def main():
    parser = argparse.ArgumentParser(description='Manage email requests')
    parser.add_argument('action', choices=['list', 'confirm', 'status'],
                      help='Action to perform')
    parser.add_argument('--request-id', help='Request ID for confirm/status actions')
    parser.add_argument('--new-status', help='New status for status action')
    
    args = parser.parse_args()
    request_manager = RequestManager()
    
    if args.action == 'list':
        list_requests(request_manager)
    elif args.action == 'confirm':
        if not args.request_id:
            print("Error: --request-id is required for confirm action")
            return
        confirm_request(request_manager, args.request_id)
    elif args.action == 'status':
        if not args.request_id or not args.new_status:
            print("Error: --request-id and --new-status are required for status action")
            return
        update_status(request_manager, args.request_id, args.new_status)

if __name__ == "__main__":
    main() 