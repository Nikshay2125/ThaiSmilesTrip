import time
from typing import Set, Optional, Dict, Callable, List
from datetime import datetime
import json
import re
from parser import TextParser
from gmail_fetch import get_gmail_service, get_recent_emails

class GmailMonitor:
    def __init__(self, check_interval: int = 10, email_filter: str = None, 
                 custom_schema: dict = None, relevance_keywords: List[str] = None):
        """
        Initialize the Gmail monitor.
        
        Args:
            check_interval: Time in seconds between checks (minimum 10 seconds)
            email_filter: Gmail search query (e.g., "from:example@gmail.com" or "subject:booking")
            custom_schema: Custom schema for the TextParser
            relevance_keywords: List of keywords to check for relevance in subject/body
        """
        self.check_interval = min(10, check_interval)  # Minimum 10 seconds
        self.email_filter = email_filter
        self.processed_ids: Set[str] = set()
        self.parser = TextParser(schema=custom_schema)
        self.service = get_gmail_service()
        
        # Default booking keywords
        default_keywords = ['booking', 'reservation', 'confirmation', 'hotel', 'flight', 
                          'travel', 'itinerary', 'guest', 'pickup', 'transfer']
                          
        # Use custom keywords if provided, otherwise use defaults
        self.relevance_keywords = relevance_keywords if relevance_keywords else default_keywords
        
        if not self.service:
            raise Exception("Failed to initialize Gmail service")

    def _extract_email_body(self, email_content: Dict) -> str:
        """Extract and clean the email body."""
        try:
            # Get the raw body
            body = email_content.get('body', '')
            
            # Remove email signatures (usually after "--" or "Regards,")
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

    def _process_single_email(self, email_content: Dict) -> Optional[Dict]:
        """Process a single email and extract relevant information."""
        try:
            # Check if we've already processed this email
            email_id = email_content.get('id')
            if not email_id or email_id in self.processed_ids:
                return None
                
            # Skip if subject doesn't contain booking keywords (secondary filter)
            subject = email_content.get('subject', '').lower()
            body_preview = email_content.get('body', '')[:200].lower()  # Check first 200 chars
            
            # Check if any keyword is present in subject or body preview
            is_relevant = any(keyword in subject for keyword in self.relevance_keywords) or \
                         any(keyword in body_preview for keyword in self.relevance_keywords)
            
            if not is_relevant:
                print(f"Skipping non-relevant email: {subject}")
                self.processed_ids.add(email_id)  # Mark as processed to avoid rechecking
                return None
                
            # Extract and clean the email body
            body = self._extract_email_body(email_content)
            if not body:
                return None
                
            # Parse the email content
            parsed_info = self.parser.parse_text(body)
            if parsed_info:
                # Mark this email as processed
                self.processed_ids.add(email_id)
                return parsed_info
                
            return None
            
        except Exception as e:
            print(f"Error processing email: {str(e)}")
            return None

    def start_monitoring(self, max_results: int = 1):
        """Start monitoring Gmail for new emails with adjustable parameters."""
        print(f"Starting Gmail monitor...")
        print(f"Checking every {self.check_interval} seconds")
        if self.email_filter:
            print(f"Filtering emails with query: {self.email_filter}")
        
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        while True:
            try:
                # Get the most recent emails with filter
                emails = get_recent_emails(
                    self.service, 
                    max_results=max_results, 
                    query=self.email_filter
                )
                
                if emails:
                    # Process the most recent email
                    result = self._process_single_email(emails[0])
                    if result:
                        print("\nNew email processed:")
                        print(json.dumps(result, indent=2))
                
                # Reset error counter on success
                consecutive_errors = 0
                
            except Exception as e:
                consecutive_errors += 1
                print(f"Error in monitoring loop: {str(e)}")
                
                # If we've had too many consecutive errors, wait longer
                if consecutive_errors >= max_consecutive_errors:
                    wait_time = self.check_interval * (2 ** (consecutive_errors - max_consecutive_errors))
                    print(f"Too many errors. Waiting {wait_time} seconds before retrying...")
                    time.sleep(wait_time)
                    continue
            
            # Wait before next check
            time.sleep(self.check_interval)

def monitor_gmail(check_interval: int = 10, email_filter: str = None, 
                  custom_schema: dict = None, relevance_keywords: List[str] = None):
    """
    Start monitoring Gmail for new emails.
    
    Args:
        check_interval: Time in seconds between checks (minimum 10 seconds)
        email_filter: Gmail search query (e.g., "from:example@gmail.com" or "subject:booking")
        custom_schema: Custom schema for the TextParser
        relevance_keywords: List of keywords to check for relevance in subject/body
    """
    monitor = GmailMonitor(
        check_interval=check_interval, 
        email_filter=email_filter,
        custom_schema=custom_schema,
        relevance_keywords=relevance_keywords
    )
    monitor.start_monitoring(max_results=1)

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
    
    # Custom relevance keywords
    relevance_keywords = [
        'booking', 'reservation', 'confirmation', 'hotel', 
        'guest', 'pickup', 'transfer', 'airport', 'flight'
    ]
    
    # Start monitoring with custom settings
    monitor_gmail(
        check_interval=30,  # Check every 30 seconds
        email_filter=filter_query,
        custom_schema=custom_schema,
        relevance_keywords=relevance_keywords
    ) 