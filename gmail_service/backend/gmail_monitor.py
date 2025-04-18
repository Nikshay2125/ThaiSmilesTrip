import os
import time
from typing import Set, Optional, Dict, List
import json
import re
from parser import TextParser
from gmail_fetch import get_gmail_service, get_recent_emails
from request_manager import RequestManager

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
        
        if not self.service:
            raise Exception("Failed to initialize Gmail service")

    def _extract_email_body(self, email_content: Dict) -> str:
        """Extract and clean the email body."""
        try:
            body = email_content.get('body', '')
            
            # Remove email signatures
            body = re.split(r'--|Regards,|Best regards,', body)[0].strip()
            
            # Remove quoted replies (lines starting with >)
            body = '\n'.join(line for line in body.split('\n') 
                           if not line.strip().startswith('>'))
            
            # Remove multiple newlines
            body = re.sub(r'\n\s*\n', '\n\n', body)
            
            return body.strip()
        except Exception as e:
            print(f"Error extracting email body: {str(e)}")
            return ""

    def _check_subject_relevance(self, subject: str) -> tuple:
        """Check if the subject contains relevant keywords and return matched words."""
        subject_lower = subject.lower()
        matched_keywords = [keyword for keyword in self.subject_keywords 
                          if keyword in subject_lower]
        return len(matched_keywords) > 0, matched_keywords

    def _process_single_email(self, email_content: Dict) -> Optional[Dict]:
        """Process a single email and extract relevant information."""
        try:
            # Check if we've already processed this email
            email_id = email_content.get('id')
            if not email_id:
                print("Skipping email without ID")
                return None

            # Check if already processed
            existing_req_id = self.request_manager.get_request_by_email_id(email_id)
            if existing_req_id or email_id in self.processed_ids:
                if existing_req_id:
                    print(f"Skipping already processed email (Request ID: {existing_req_id})")
                self.processed_ids.add(email_id)
                return None
            
            # Get email components
            subject = email_content.get('subject', '').lower()
            body_text = email_content.get('body', '').lower()
            from_email = email_content.get('from', '').lower()
            
            # Skip automated replies and confirmations from our own system
            if "thank you for your request" in body_text and "your service team" in body_text:
                print(f"Skipping our own automated reply: {subject}")
                self.processed_ids.add(email_id)
                return None
                
            # Skip emails that are replies to our confirmations
            if subject.startswith("re:") and "request id: req_" in body_text:
                print(f"Skipping reply to our confirmation: {subject}")
                self.processed_ids.add(email_id)
                return None
            
            # First check subject relevance
            subject_relevant, matched_subject_keywords = self._check_subject_relevance(subject)
            if subject_relevant:
                print(f"Subject '{subject}' is relevant. Matched keywords: {matched_subject_keywords}")
            else:
                # If subject doesn't match, check body with higher threshold
                # Count matching keywords in body
                body_keyword_count = sum(1 for keyword in self.relevance_keywords 
                                  if keyword in body_text[:500])
                
                # Require at least 3 matching keywords in body if subject doesn't match
                if body_keyword_count < 3:
                    print(f"Skipping non-relevant email (subject not relevant, matched only {body_keyword_count} keywords in body): {subject}")
                    self.processed_ids.add(email_id)
                    return None
                else:
                    print(f"Subject not relevant but body contains {body_keyword_count} keywords, proceeding")
                
            # Extract and clean the email body
            body = self._extract_email_body(email_content)
            if not body:
                self.processed_ids.add(email_id)
                return None
                
            # Parse the email content
            parsed_info = self.parser.parse_text(body)
            
            # Verify that parsing extracted key information
            key_fields_present = [field for field in ['guest_name', 'date', 'flight_no', 'pickup_time', 'hotel_drop'] 
                                if parsed_info.get(field)]
            
            if parsed_info and len(key_fields_present) >= 2:
                request_id = self.request_manager.add_request(email_content)
                print(f"Added new request: {request_id}")
                print(f"Parsed info contains fields: {key_fields_present}")
                print(f"Parsed info: {json.dumps(parsed_info, indent=2)}")
                
                # Store parsed data in MongoDB
                stored = self.request_manager.process_and_store_in_mongodb(request_id, parsed_info)
                if stored:
                    print(f"Successfully stored request {request_id} in MongoDB")
                else:
                    print(f"Failed to store request {request_id} in MongoDB")
                
                self.processed_ids.add(email_id)
                return parsed_info
            else:
                print(f"Skipping email with insufficient parsed information: {subject}")
                if parsed_info:
                    print(f"Parsed fields: {[k for k,v in parsed_info.items() if v]}")
                self.processed_ids.add(email_id)
                return None
            
        except Exception as e:
            print(f"Error processing email: {str(e)}")
            return None

    def start_monitoring(self, max_results: int = 5):
        """Start monitoring Gmail for new emails with adjustable parameters."""
        print(f"Starting Gmail monitor...")
        print(f"Checking every {self.check_interval} seconds")
        if self.email_filter:
            print(f"Filtering emails with query: {self.email_filter}")
        print(f"Subject keywords: {', '.join(self.subject_keywords)}")
        print(f"Body relevance keywords: {', '.join(self.relevance_keywords)}")
        
        consecutive_errors = 0
        max_consecutive_errors = 5
        last_cleanup = time.time()
        cleanup_interval = 3600  # Clean up every hour
        
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
                        result = self._process_single_email(email)
                        if result:
                            print("\nNew email processed:")
                            print(json.dumps(result, indent=2))
                
                # Periodically clean up processed requests
                current_time = time.time()
                if current_time - last_cleanup >= cleanup_interval:
                    self.request_manager.cleanup_processed_requests()
                    last_cleanup = current_time
                
                consecutive_errors = 0
                
            except Exception as e:
                consecutive_errors += 1
                print(f"Error in monitoring loop: {str(e)}")
                
                # Exponential backoff for repeated errors
                if consecutive_errors >= max_consecutive_errors:
                    wait_time = self.check_interval * (2 ** (consecutive_errors - max_consecutive_errors))
                    print(f"Too many errors. Waiting {wait_time} seconds before retrying...")
                    time.sleep(wait_time)
                    continue
            
            time.sleep(self.check_interval)


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