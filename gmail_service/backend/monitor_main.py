from gmail_monitor import GmailMonitor
import os
import json
import sys

def main():
    try:
        # Load configuration from config.json
        try:
            with open('config.json', 'r') as config_file:
                config = json.load(config_file)
                print("Loaded configuration from config.json")
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error loading config.json: {str(e)}")
            print("Using default configuration")
            config = {
                "check_interval": 30,
                "email_filter": "newer_than:2d -in:chats -from:me",
                "max_results": 5
            }
        
        # Get API key from environment
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            print("ERROR: GROQ_API_KEY environment variable is not set")
            print("Please set the environment variable with your API key")
            sys.exit(1)
        
        # Print configuration details
        print("\nStarting Gmail Monitor with configuration:")
        print(f"- Check interval: {config.get('check_interval', 30)} seconds")
        print(f"- Email filter: {config.get('email_filter', 'None')}")
        print(f"- Max results per check: {config.get('max_results', 5)}")
        print(f"- Custom schema: {'Yes' if config.get('custom_schema') else 'No'}")
        print(f"- Number of subject keywords: {len(config.get('subject_keywords', []))}")
        print(f"- Number of relevance keywords: {len(config.get('relevance_keywords', []))}")
        print("-" * 50)
        
        # Initialize the GmailMonitor with configuration from config.json
        monitor = GmailMonitor(
            api_key=api_key,
            check_interval=config.get('check_interval', 30),
            email_filter=config.get('email_filter'),
            custom_schema=config.get('custom_schema'),
            subject_keywords=config.get('subject_keywords'),
            relevance_keywords=config.get('relevance_keywords')
        )
        
        # Start monitoring with max_results from config
        monitor.start_monitoring(max_results=config.get('max_results', 5))
        
    except Exception as e:
        print(f"ERROR in Gmail Monitor: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main() 