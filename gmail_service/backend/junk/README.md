# Gmail Service - Driver Agent Integration

This system processes booking requests from emails and coordinates with driver agents to arrange transportation.

## Workflow

1. **Request Reception**: System monitors Gmail for booking/reservation emails
2. **Request Processing**: Parses email content to extract booking details
3. **Driver Agent Assignment**: Assigns a specific driver agent to a request (automated or manual)
4. **Driver Assignment**: Agent replies with driver details for the request
5. **Driver Assignment Processing**: System parses the agent's reply to extract driver information
6. **Confirmation**: System sends confirmation to the customer with driver details

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Set up environment variables in `.env`:
   ```
   GROQ_API_KEY=your_groq_api_key
   MONGO_URI=mongodb://localhost:27017
   DB_NAME=email_service
   ```

3. Initialize the driver agent database:
   ```
   python init_driver_db.py
   ```

## Running the Service

Start the service using the interactive menu:
```
python monitor_main.py
```

Or start the monitor directly (recommended for stable operation):
```
python run_monitor.py --interval 30 --threads 2
```

Command-line options:
- `--interval`: Check interval in seconds (default: 30)
- `--filter`: Gmail search filter (e.g., 'subject:booking') 
- `--max-results`: Maximum number of emails to fetch per check (default: 5)
- `--threads`: Number of worker threads for parallel processing (default: 2)

## Manual Control

The system provides manual control over driver agent assignments:

1. List all pending requests:
   ```
   python manage_requests.py list --status pending
   ```

2. List available driver agents:
   ```
   python manage_requests.py agents
   ```

3. Assign a specific driver agent to a request:
   ```
   python manage_requests.py assign REQ_20250409_200716_0 D0
   ```

4. Manually confirm a request:
   ```
   python manage_requests.py confirm REQ_20250409_200716_0
   ```

## Components

- **gmail_monitor.py**: Monitors Gmail for new emails and processes them
- **request_manager.py**: Manages request tracking and processing
- **driver_parser.py**: Parses driver details from agent responses
- **db_config.py**: Handles database operations
- **init_driver_db.py**: Initializes driver agent database
- **manage_requests.py**: Command-line tool for manual driver agent assignment
- **monitor_main.py**: Main application with menu-driven interface
- **run_monitor.py**: Simple script to run the monitor directly
- **test_driver_assignment.py**: Tests the driver agent workflow

## Multithreading

The system uses multithreading to handle both incoming booking requests and driver agent responses simultaneously. This ensures that:

1. New booking requests can be processed while waiting for driver agent responses
2. Driver agent responses are processed promptly without blocking new requests
3. The system can handle high volumes of emails efficiently

## Agent Response Format

Agents should reply to booking request emails with the following information:
```
Driver Details:
- Name: [driver name]
- Contact: [driver contact]

Vehicle Information:
- [vehicle model], [color]
- Registration: [registration number]
- Features: [features list]

[Additional notes]
```

The system will parse this information and associate it with the appropriate request. 