from whatsapp_logger import WhatsAppClient
from parser import TextParser
import json
import time
import re
from datetime import datetime, timezone

class ResponseSystem:
    def __init__(self, whatsapp_client):
        self.whatsapp_client = whatsapp_client
        self.required_fields = whatsapp_client.required_fields
        self.booking_states = {}  # Store booking state for each user
        self.start_time = datetime.now(timezone.utc)  # Store program start time with UTC timezone
        self.parser = TextParser()  # Initialize the text parser
        
    def send_format_instructions(self, to_number):
        """Send format instructions to user in a simple text format"""
        format_message = """Please provide your booking details in any format. Include the following information:

📅 Date (e.g., 15 Mar 2024)
👤 Guest Name
👥 Number of Guests
✈️ Flight Number (if available)
🕒 Pickup Time (e.g., 09:30 AM)
📍 Pickup Location
🏨 Hotel/Drop-off Location (if applicable)
🎯 Tour Details (if applicable)
💳 Payment Information (if applicable)
🔑 Booking Code

You can send the information in any format, and I'll understand it!"""
        self.whatsapp_client.send_message(to_number, format_message)

    def handle_booking_command(self, sender_number):
        """Handle initial booking command"""
        self.booking_states[sender_number] = "waiting_for_details"
        self.send_format_instructions(sender_number)

    def handle_booking_details(self, sender_number, message_body):
        """Handle booking details submission"""
        try:
            # Use the parser to extract information
            parsed_response = self.parser.parse_text(message_body)
            
            if parsed_response:
                print("\nParsed booking details:")
                print(json.dumps(parsed_response, indent=2))
                
                # Format confirmation message in a readable way
                confirm_msg = "I received the following information:\n\n"
                confirm_msg += f"📅 Date: {parsed_response.get('date', 'Not provided')}\n"
                confirm_msg += f"👤 Guest: {parsed_response.get('guest_name', 'Not provided')}\n"
                confirm_msg += f"👥 Guests: {parsed_response.get('pax', 'Not provided')}\n"
                confirm_msg += f"✈️ Flight: {parsed_response.get('flight_no', 'Not provided')}\n"
                confirm_msg += f"🕒 Pickup: {parsed_response.get('pickup_time', 'Not provided')}\n"
                confirm_msg += f"📍 Location: {parsed_response.get('pickup_location', 'Not provided')}\n"
                confirm_msg += f"🏨 Drop-off: {parsed_response.get('hotel_drop', 'Not provided')}\n"
                confirm_msg += f"🎯 Tour: {parsed_response.get('tour', 'Not provided')}\n"
                confirm_msg += f"💳 Payment: {parsed_response.get('payment', 'Not provided')}\n"
                confirm_msg += f"🔑 Code: {parsed_response.get('code', 'Not provided')}\n\n"
                confirm_msg += "Is this correct? Please reply with 'yes' or 'no'"
                
                self.whatsapp_client.send_message(sender_number, confirm_msg)
                self.booking_states[sender_number] = "waiting_for_confirmation"
                return parsed_response
            else:
                self.whatsapp_client.send_message(sender_number, "I couldn't understand the booking details. Please try again with the information in any format.")
                self.send_format_instructions(sender_number)
                return None
        except Exception as e:
            print(f"Error parsing message: {str(e)}")
            self.whatsapp_client.send_message(sender_number, "I encountered an error while processing your message. Please try again.")
            self.send_format_instructions(sender_number)
            return None

    def handle_confirmation(self, sender_number, message_body):
        """Handle user's confirmation response"""
        if message_body.lower().strip() == 'yes':
            self.whatsapp_client.send_message(sender_number, "✅ Thank you! Your booking has been confirmed and is being processed.")
            # Here you can add additional processing logic
            del self.booking_states[sender_number]
            return True
        elif message_body.lower().strip() == 'no':
            self.whatsapp_client.send_message(sender_number, "Please provide the information again in any format.")
            self.send_format_instructions(sender_number)
            self.booking_states[sender_number] = "waiting_for_details"
            return False
        else:
            self.whatsapp_client.send_message(sender_number, "Please reply with 'yes' or 'no'")
            return False

    def process_message(self, message):
        """Process incoming message and handle response"""
        # Only process messages that arrived after program start
        message_time = datetime.strptime(message['timestamp'], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        if message_time <= self.start_time:
            return

        sender = message['from']
        message_body = message['body']
        sender_number = sender.replace('whatsapp:', '')

        # Handle booking command
        if message_body.lower().strip() == 'booking':
            self.handle_booking_command(sender_number)
            return

        # Handle ongoing booking process
        if sender_number in self.booking_states:
            if self.booking_states[sender_number] == "waiting_for_details":
                self.handle_booking_details(sender_number, message_body)
            elif self.booking_states[sender_number] == "waiting_for_confirmation":
                self.handle_confirmation(sender_number, message_body)
        else:
            # If no ongoing booking, send instructions
            self.whatsapp_client.send_message(sender_number, "To start a booking, please send 'booking'")

def main():
    print("Response System is running! 🚀")
    print("Monitoring for new messages...")
    
    account_sid = 'ACa295770c86665717607a7f93866f322d'
    auth_token = 'c9484746ac3662692c91d289ce6074e2'
    whatsapp_client = WhatsAppClient(account_sid, auth_token)
    response_system = ResponseSystem(whatsapp_client)
    
    while True:
        try:
            message = whatsapp_client.get_recent_message()
            if message:
                response_system.process_message(message)
                
            time.sleep(10)
            
        except KeyboardInterrupt:
            print("\nStopping Response System...")
            break
        except Exception as e:
            print(f"Error: {str(e)}")
            time.sleep(5)

if __name__ == "__main__":
    main() 