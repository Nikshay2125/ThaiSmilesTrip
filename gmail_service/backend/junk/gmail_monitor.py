import os
import time
import threading
import queue
from typing import Set, Optional, Dict, List
import json
import re
from parser import TextParser
from gmail_fetch import get_gmail_service, get_recent_emails
from request_manager import RequestManager

class EmailProcessor(threading.Thread):
    """Thread class to process emails in parallel."""
    
    def __init__(self, queue, parser, request_manager, processed_ids, is_agent_response):
        threading.Thread.__init__(self)
        self.queue = queue
        self.parser = parser
        self.request_manager = request_manager
        self.processed_ids = processed_ids
        self.is_agent_response = is_agent_response
        self.daemon = True
        
    def run(self):
        while True:
            try:
                email = self.queue.get()
                if email is None:  # Poison pill to stop thread
                    break
                    
                # Process email based on type
                if self.is_agent_response:
                    self._process_agent_response(email)
                else:
                    self._process_booking_request(email)
                    
                self.queue.task_done()
            except Exception as e:
                print(f"Error in EmailProcessor: {str(e)}")
                self.queue.task_done()
    
    def _process_agent_response(self, email):
        """Process a driver agent response."""
        email_id = email.get('id')
        if email_id in self.processed_ids:
            return
            
        subject = email.get('subject', '')
        from_email = email.get('from', '').lower()
        
        # Log processing of agent response
        print(f"Processing agent response from {from_email}: {subject}")
        
        # Extract request ID from subject - update pattern to be more flexible
        req_id_match = re.search(r'(RE: |Re: |)Driver Needed for Request (REQ_\d+_\d+_\d+)', subject, re.IGNORECASE)
        if not req_id_match:
            print(f"Could not find request ID in subject: {subject}")
            self.processed_ids.add(email_id)
            return
            
        request_id = req_id_match.group(2)  # Use group 2 to get the request ID since group 1 is the optional Re: part
        
        # Check if this request exists
        if request_id not in self.request_manager.requests:
            print(f"Request {request_id} not found in system")
            self.processed_ids.add(email_id)
            return
            
        request = self.request_manager.requests[request_id]
        agent_id = request.get('driver_id')
        
        if not agent_id:
            print(f"Request {request_id} has no assigned agent ID")
            self.processed_ids.add(email_id)
            return
            
        # Process the agent's response to get driver details
        # Pass the email data to the request manager
        success = self.request_manager.process_driver_response(email)
        
        if success:
            print(f"Successfully processed driver details for request {request_id}")
            # You could automatically confirm here if needed:
            # self.request_manager.set_confirmation(request_id, True)
        else:
            print(f"Failed to process driver details for request {request_id}")
            
        self.processed_ids.add(email_id)
    
    def _process_booking_request(self, email):
        """Process a potential booking request email."""
        email_id = email.get('id')
        if email_id in self.processed_ids:
            return
            
        subject = email.get('subject', '')
        body_text = email.get('body', '').lower()
        
        # Skip automated replies and confirmations from our own system
        if "thank you for your request" in body_text and "your service team" in body_text:
            print(f"Skipping our own automated reply: {subject}")
            self.processed_ids.add(email_id)
            return
            
        # Skip emails that are replies to our confirmations
        if subject.lower().startswith("re:") and "request id: req_" in body_text:
            print(f"Skipping reply to our confirmation: {subject}")
            self.processed_ids.add(email_id)
            return
        
        # Parse the email content
        body = email.get('body', '')
        if not body:
            self.processed_ids.add(email_id)
            return
            
        parsed_info = self.parser.parse_text(body)
        
        # Verify that parsing extracted key information
        key_fields_present = [field for field in ['guest_name', 'date', 'flight_no', 'pickup_time', 'hotel_drop'] 
                            if parsed_info.get(field)]
        
        if parsed_info and len(key_fields_present) >= 2:
            request_id = self.request_manager.add_request(email)
            print(f"Added new request: {request_id}")
            print(f"Parsed info contains fields: {key_fields_present}")
            
            # Store parsed data in MongoDB
            stored = self.request_manager.process_and_store_in_mongodb(request_id, parsed_info)
            if stored:
                print(f"Successfully stored request {request_id} in MongoDB")
            else:
                print(f"Failed to store request {request_id} in MongoDB")
            
            self.processed_ids.add(email_id)
        else:
            print(f"Skipping email with insufficient parsed information: {subject}")
            self.processed_ids.add(email_id)

class GmailMonitor:
    def __init__(self, api_key: str, check_interval: int = 10, email_filter: str = None, 
                 custom_schema: dict = None, relevance_keywords: List[str] = None,
                 subject_keywords: List[str] = None):
        """
        Initialize the Gmail monitor.
        
        Args:
            check_interval: Time in seconds between checks (minimum 10 seconds)
            email_filter: Gmail search query (e.g., "from:example@gmail.com" or "subject:booking")
            custom_schema: Custom schema for the TextParser
            relevance_keywords: List of keywords to check for relevance in body
            subject_keywords: List of keywords to check specifically in subject lines
        """
        self.api_key = api_key
        if not self.api_key:
            raise ValueError("GROQ_API_KEY environment variable is required")
        
        self.check_interval = max(10, check_interval)  # Minimum 10 seconds
        self.email_filter = email_filter
        self.processed_ids: Set[str] = set()
        self.parser = TextParser(self.api_key, schema=custom_schema)
        self.service = get_gmail_service()
        self.request_manager = RequestManager()
        
        # Default booking keywords if none provided
        self.relevance_keywords = relevance_keywords or [
            'booking', 'reservation', 'confirmation', 'hotel', 'flight', 
            'travel', 'itinerary', 'guest', 'pickup', 'transfer'
        ]
        
        # Default subject keywords if none provided
        self.subject_keywords = subject_keywords or [
            'booking', 'reservation', 'confirmation', 'pickup', 
            'airport', 'transfer', 'arrival', 'hotel', 'travel'
        ]
        
        # Email patterns for different types of emails
        self.agent_response_pattern = r'(RE: |Re: |)Driver Needed for Request REQ_\d+_\d+_\d+'
        
        # Work queues for parallel processing
        self.request_queue = queue.Queue()
        self.agent_response_queue = queue.Queue()
        
        # Thread lock for accessing shared resources
        self.lock = threading.Lock()
        
        if not self.service:
            raise Exception("Failed to initialize Gmail service")

    def _check_subject_relevance(self, subject: str) -> tuple:
        """Check if the subject contains relevant keywords and return matched words."""
        subject_lower = subject.lower()
        matched_keywords = [keyword for keyword in self.subject_keywords 
                          if keyword in subject_lower]
        return len(matched_keywords) > 0, matched_keywords

    def _check_if_agent_response(self, subject: str) -> bool:
        """Check if an email is a response from a driver agent."""
        # Update the pattern to match more variations of subject lines
        pattern = r'(RE: |Re: |)Driver Needed for Request REQ_\d+_\d+_\d+'
        return bool(re.match(pattern, subject, re.IGNORECASE))

    def classify_email(self, email: Dict) -> str:
        """Classify an email as either agent response or potential booking."""
        subject = email.get('subject', '')
        
        # First check if this is a driver agent response
        if self._check_if_agent_response(subject):
            return "agent_response"
            
        # Otherwise, check if it's a potential booking
        subject_relevant, _ = self._check_subject_relevance(subject.lower())
        if subject_relevant:
            return "potential_booking"
            
        # If subject not relevant, check body
        body_text = email.get('body', '').lower()
        body_keyword_count = sum(1 for keyword in self.relevance_keywords 
                               if keyword in body_text[:500])
        
        if body_keyword_count >= 3:
            return "potential_booking"
            
        return "irrelevant"

    def start_monitoring(self, max_results: int = 5, num_threads: int = 2):
        """Start monitoring Gmail for new emails with concurrent processing."""
        print(f"Starting Gmail monitor...")
        print(f"Checking every {self.check_interval} seconds")
        if self.email_filter:
            print(f"Filtering emails with query: {self.email_filter}")
        print(f"Subject keywords: {', '.join(self.subject_keywords)}")
        print(f"Body relevance keywords: {', '.join(self.relevance_keywords)}")
        print(f"Monitoring for driver agent responses with pattern: {self.agent_response_pattern}")
        print(f"Using {num_threads} threads for parallel processing")
        
        # Initialize driver agents database
        try:
            self.request_manager.mongodb.init_driver_agents()
            print("Driver agents database initialized")
        except Exception as e:
            print(f"Error initializing driver agents: {str(e)}")
        
        # Start worker threads
        request_workers = []
        agent_response_workers = []
        
        for i in range(num_threads):
            # Booking request processor threads
            worker = EmailProcessor(self.request_queue, self.parser, 
                                   self.request_manager, self.processed_ids, 
                                   is_agent_response=False)
            worker.start()
            request_workers.append(worker)
            
            # Agent response processor threads
            worker = EmailProcessor(self.agent_response_queue, self.parser, 
                                   self.request_manager, self.processed_ids, 
                                   is_agent_response=True)
            worker.start()
            agent_response_workers.append(worker)
        
        consecutive_errors = 0
        max_consecutive_errors = 5
        last_cleanup = time.time()
        cleanup_interval = 3600  # Clean up every hour
        
        try:
            while True:
                try:
                    # Get the most recent emails with filter
                    emails = get_recent_emails(
                        self.service, 
                        max_results=max_results, 
                        query=self.email_filter
                    )
                    
                    if emails:
                        for email in emails:
                            email_id = email.get('id')
                            
                            # Skip already processed emails
                            if email_id in self.processed_ids:
                                continue
                                
                            # Classify email type
                            email_type = self.classify_email(email)
                            
                            if email_type == "agent_response":
                                print(f"Queueing driver agent response: {email.get('subject')}")
                                self.agent_response_queue.put(email)
                            elif email_type == "potential_booking":
                                print(f"Queueing potential booking request: {email.get('subject')}")
                                self.request_queue.put(email)
                            else:
                                print(f"Skipping irrelevant email: {email.get('subject')}")
                                self.processed_ids.add(email_id)
                    
                    # Periodically clean up processed requests
                    current_time = time.time()
                    if current_time - last_cleanup >= cleanup_interval:
                        with self.lock:
                            self.request_manager.cleanup_processed_requests()
                        last_cleanup = current_time
                        
                    # Reset error counter after successful execution
                    consecutive_errors = 0
                        
                except Exception as e:
                    consecutive_errors += 1
                    print(f"Error in monitoring loop: {str(e)}")
                    if consecutive_errors >= max_consecutive_errors:
                        print(f"Too many consecutive errors ({consecutive_errors}). Exiting.")
                        break
                
                # Sleep before next check
                time.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            print("Shutting down email monitor...")
            
        finally:
            # Shut down worker threads
            for _ in range(num_threads):
                self.request_queue.put(None)
                self.agent_response_queue.put(None)
                
            # Wait for workers to finish
            for worker in request_workers + agent_response_workers:
                worker.join(timeout=1.0)
                
            print("Email monitor shutdown complete.")


if __name__ == "__main__":
    # Example filter: Only process emails with "booking" or "reservation" in the subject
    filter_query = "subject:(booking OR reservation OR confirmation)"
    
    # Example custom schema for specific booking information
    custom_schema = {
        "date": "DD MMM YYYY formatted date",
        "guest_name": "Full name of the guest",
        "pax": "Number of guests/people (integer)",
        "flight_no": "Flight number if available",
        "pickup_time": "Time in HH:MM AM/PM format", 
        "pickup_location": "Location for pickup",
        "hotel_drop": "Hotel or drop-off location"
    }
    
    # Subject-specific keywords
    subject_keywords = [
        'booking', 'reservation', 'confirmation', 'hotel', 
        'guest', 'pickup', 'transfer', 'airport', 'flight'
    ]
    
    # Body relevance keywords
    relevance_keywords = [
        'booking', 'reservation', 'confirmation', 'hotel', 
        'guest', 'pickup', 'transfer', 'airport', 'flight'
    ]
    
    # Start monitoring with custom settings
    monitor = GmailMonitor(
        api_key=os.getenv("GROQ_API_KEY"),
        check_interval=30,  # Check every 30 seconds
        email_filter=filter_query,
        custom_schema=custom_schema,
        subject_keywords=subject_keywords,
        relevance_keywords=relevance_keywords
    )
    monitor.start_monitoring(max_results=5)