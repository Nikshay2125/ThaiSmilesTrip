import os
import sys
import argparse
import threading
from gmail_monitor import GmailMonitor
from dotenv import load_dotenv
import subprocess

load_dotenv()

def start_monitoring(args):
    """Start the Gmail monitoring service."""
    # Check for required API key
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("Error: GROQ_API_KEY environment variable is required")
        sys.exit(1)
    
    # Set up email filter if provided
    email_filter = args.filter if args.filter else None
    
    # Start the monitor with specified parameters
    monitor = GmailMonitor(
        api_key=api_key,
        check_interval=args.interval,
        email_filter=email_filter
    )
    
    try:
        print(f"Starting Gmail monitoring with {args.interval} second interval...")
        print(f"This will monitor both new booking requests AND driver agent responses simultaneously")
        print(f"You can use the send_to_driver.py script to assign drivers while this is running")
        print(f"Press Ctrl+C to stop monitoring\n")
        monitor.start_monitoring(max_results=args.max_results, num_threads=args.threads)
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user")

def start_request_manager():
    """Start a subprocess to manage requests manually."""
    try:
        # Show help text first
        subprocess.run(["python", "manage_requests.py", "--help"])
        
        # Loop to allow running multiple commands
        while True:
            print("\nEnter command (or 'exit' to return to menu):")
            command = input("> ")
            
            if command.lower() == 'exit':
                break
                
            command_parts = command.split()
            subprocess.run(["python", "manage_requests.py"] + command_parts)
    except KeyboardInterrupt:
        print("\nRequest manager exited")

def display_menu():
    """Display the main menu for the application."""
    while True:
        print("\n===== Email Service Management System =====")
        print("1. Start Gmail Monitoring")
        print("2. Manage Driver Agent Assignments")
        print("3. Test Driver Agent Email Parsing")
        print("4. Initialize Driver Agents Database")
        print("5. Auto Mode (Monitor + Process in Background)")
        print("0. Exit")
        
        choice = input("\nEnter your choice: ")
        
        if choice == '1':
            parser = argparse.ArgumentParser(description="Gmail Monitoring Service")
            parser.add_argument("--interval", type=int, default=30, 
                             help="Check interval in seconds (default: 30)")
            parser.add_argument("--filter", type=str, 
                             help="Gmail search filter (e.g., 'subject:booking')")
            parser.add_argument("--max-results", type=int, default=5,
                             help="Maximum number of emails to fetch (default: 5)")
            parser.add_argument("--threads", type=int, default=2,
                             help="Number of worker threads (default: 2)")
            args = parser.parse_args([])
            
            # Allow customization
            print("\nMonitoring Configuration:")
            args.interval = int(input(f"Check interval in seconds [{args.interval}]: ") or args.interval)
            args.filter = input(f"Gmail search filter [{args.filter or 'None'}]: ") or args.filter
            args.max_results = int(input(f"Maximum emails to fetch [{args.max_results}]: ") or args.max_results)
            args.threads = int(input(f"Worker threads [{args.threads}]: ") or args.threads)
            
            start_monitoring(args)
            
        elif choice == '2':
            start_request_manager()
            
        elif choice == '3':
            # Run the driver parser test
            try:
                subprocess.run(["python", "driver_parser.py"])
            except Exception as e:
                print(f"Error running driver parser test: {str(e)}")
                
        elif choice == '4':
            # Initialize driver agents database
            try:
                subprocess.run(["python", "init_driver_db.py"])
            except Exception as e:
                print(f"Error initializing driver agents: {str(e)}")
                
        elif choice == '5':
            # Auto mode - start monitoring immediately with default settings
            parser = argparse.ArgumentParser(description="Gmail Monitoring Service")
            args = parser.parse_args([])
            args.interval = 30
            args.filter = None
            args.max_results = 5
            args.threads = 2
            
            print("\nStarting Auto Mode with default settings...")
            print("- Check interval: 30 seconds")
            print("- No email filter applied")
            print("- Maximum emails to fetch: 5")
            print("- Worker threads: 2")
            
            start_monitoring(args)
            
        elif choice == '0':
            print("Exiting system. Goodbye!")
            break
            
        else:
            print("Invalid choice. Please try again.")

def main():
    """Main entry point with command-line argument handling."""
    parser = argparse.ArgumentParser(description="Gmail Service Management System")
    parser.add_argument("--monitor", action="store_true", 
                       help="Start Gmail monitoring immediately")
    parser.add_argument("--auto", action="store_true",
                       help="Start in auto mode with default settings")
    parser.add_argument("--interval", type=int, default=30, 
                       help="Check interval in seconds for monitoring (default: 30)")
    parser.add_argument("--filter", type=str, 
                       help="Gmail search filter (e.g., 'subject:booking')")
    parser.add_argument("--max-results", type=int, default=5,
                       help="Maximum number of emails to fetch (default: 5)")
    parser.add_argument("--threads", type=int, default=2,
                       help="Number of worker threads (default: 2)")
    
    args = parser.parse_args()
    
    if args.auto:
        # Start in auto mode with default settings
        print("\nStarting in Auto Mode...")
        args.interval = 30
        args.filter = None
        args.max_results = 5
        args.threads = 2
        start_monitoring(args)
    elif args.monitor:
        # Start monitoring directly
        start_monitoring(args)
    else:
        # Show interactive menu
        display_menu()

if __name__ == "__main__":
    main() 