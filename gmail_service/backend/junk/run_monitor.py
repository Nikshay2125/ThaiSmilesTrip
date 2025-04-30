import os
import sys
import argparse
from dotenv import load_dotenv
from gmail_monitor import GmailMonitor

load_dotenv()

def main():
    """Run the Gmail monitoring service with command-line arguments."""
    parser = argparse.ArgumentParser(description="Gmail Monitoring Service")
    parser.add_argument("--interval", type=int, default=30, 
                       help="Check interval in seconds (default: 30)")
    parser.add_argument("--filter", type=str, 
                       help="Gmail search filter (e.g., 'subject:booking')")
    parser.add_argument("--max-results", type=int, default=5,
                       help="Maximum number of emails to fetch (default: 5)")
    parser.add_argument("--threads", type=int, default=2,
                       help="Number of worker threads (default: 2)")
    
    args = parser.parse_args()
    
    # Check for required API key
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("Error: GROQ_API_KEY environment variable is required")
        sys.exit(1)
    
    print(f"Starting Gmail monitoring:")
    print(f"- Check interval: {args.interval} seconds")
    print(f"- Email filter: {args.filter or 'None'}")
    print(f"- Max results: {args.max_results}")
    print(f"- Worker threads: {args.threads}")
    print("-" * 50)
    
    # Start the monitor with specified parameters
    monitor = GmailMonitor(
        api_key=api_key,
        check_interval=args.interval,
        email_filter=args.filter
    )
    
    try:
        monitor.start_monitoring(
            max_results=args.max_results, 
            num_threads=args.threads
        )
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user")
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main() 