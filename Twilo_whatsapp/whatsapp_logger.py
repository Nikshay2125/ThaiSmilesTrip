from twilio.rest import Client
from datetime import datetime
import json
import os
import requests
import time
import re

class WhatsAppClient:
    def __init__(self, account_sid, auth_token):
        self.client = Client(account_sid, auth_token)
        self.from_number = 'whatsapp:+14155238886'
        
        if not os.path.exists('logs'):
            os.makedirs('logs')

        self.required_fields = {
            "date": "(DD MMM YYYY)",
            "guest_name": "",
            "pax": "", 
            "flight_no": "Flight Number (if available, else NULL)",
            "pickup_time": "(HH:MM AM/PM)",
            "pickup_location": "",
            "hotel_drop": "(if applicable, else NULL)",
            "tour": "(if applicable, else NULL)",
            "payment": "(if applicable, else NULL)",
            "code": ""
        }
    
    def _log_message(self, message_data):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_file = f"logs/whatsapp_{datetime.now().strftime('%Y-%m-%d')}.json"
        
        logs = []
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8') as f:
                try:
                    logs = json.load(f)
                except json.JSONDecodeError:
                    logs = []
        
        logs.append(message_data)
        
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)

    def send_message(self, to_number, message):
        """
        Send a WhatsApp message to a specific number
        
        Args:
            to_number (str): The recipient's phone number (without 'whatsapp:' prefix)
            message (str): The message to send
            
        Returns:
            str: Message SID if successful, None if failed
        """
        try:
            message = self.client.messages.create(
                from_=self.from_number,
                body=message,
                to=f'whatsapp:{to_number}'
            )
            
            message_data = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "type": "sent",
                "from": self.from_number,
                "to": f"whatsapp:{to_number}",
                "body": message.body,
                "sid": message.sid
            }
            self._log_message(message_data)
            return message.sid
        except Exception as e:
            print(f"Error sending message: {str(e)}")
            return None

    def get_recent_message(self):
        """
        Fetch the most recent incoming WhatsApp message
        
        Returns:
            dict: Message data containing timestamp, sender, body, etc. or None if no messages
        """
        try:
            messages = self.client.messages.list(
                to=self.from_number,
                limit=1
            )
            
            if messages and messages[0].direction == 'inbound':
                message = messages[0]
                message_data = {
                    "timestamp": message.date_sent.strftime("%Y-%m-%d %H:%M:%S"),
                    "type": "received",
                    "from": message.from_,
                    "to": message.to,
                    "body": message.body,
                    "sid": message.sid
                }
                self._log_message(message_data)
                return message_data
            
            return None
                
        except Exception as e:
            print(f"Error fetching messages: {str(e)}")
            return None

    def check_message_format(self, message_body):
        """Check if message contains required fields"""
        required_keywords = list(self.required_fields.keys())
        found_keywords = [word for word in required_keywords if word.lower() in message_body.lower()]
        return len(found_keywords) >= len(required_keywords) * 0.5  # At least 50% of keywords should be present

    def send_format_instructions(self, to_number):
        """Send format instructions to user"""
        format_message = "Please provide information in the following format:\n\n"
        format_message += json.dumps(self.required_fields, indent=2)
        format_message += "\n\nPlease fill in the values for each field."
        self.send_message(to_number, format_message)

    def parse_user_response(self, message_body):
        """Try to parse user response into required format"""
        try:
            # Basic parsing - looking for key:value or key=value patterns
            response_dict = {}
            lines = message_body.split('\n')
            for line in lines:
                # Try to split on : or =
                parts = re.split('[:|=]', line, maxsplit=1)
                if len(parts) == 2:
                    key = parts[0].strip().lower()
                    value = parts[1].strip()
                    if key in self.required_fields:
                        response_dict[key] = value
            return response_dict
        except:
            return None

    def process_message(self):
        """Main message processing logic"""
        recent_message = self.get_recent_message()
        if not recent_message:
            return None

        sender = recent_message['from']
        message_body = recent_message['body']
        sender_number = sender.replace('whatsapp:', '')

        # Check if message follows required format
        if not self.check_message_format(message_body):
            self.send_format_instructions(sender_number)
            return None

        # Try to parse user response
        parsed_response = self.parse_user_response(message_body)
        if parsed_response:
            # Send confirmation message
            confirm_msg = "I received the following information:\n"
            confirm_msg += json.dumps(parsed_response, indent=2)
            confirm_msg += "\n\nIs this correct? Please reply with 'yes' or 'no'"
            self.send_message(sender_number, confirm_msg)
            
            # Wait for confirmation
            time.sleep(10)  # Wait for response
            confirmation = self.get_recent_message()
            if confirmation and confirmation['body'].lower().strip() == 'yes':
                print("Booking confirmed:")
                print(json.dumps(parsed_response, indent=2))
            elif confirmation and confirmation['body'].lower().strip() == 'no':
                self.send_message(sender_number, "Please provide the information again in the correct format.")
                self.send_format_instructions(sender_number)

def main():
    print("WhatsApp Message Reader is running! 🚀")
    print("Waiting for incoming messages...")
    
    account_sid = 'AC5c49c197045993c193f4a2fb10b7ee38'
    auth_token = '92c2d25859863139a87a6c235f66c4e0'
    whatsapp_client = WhatsAppClient(account_sid, auth_token)
    
    processed_sids = {}
    
    while True:
        try:
            whatsapp_client.process_message()
            time.sleep(10)
            
        except KeyboardInterrupt:
            print("\nStopping WhatsApp Message Reader...")
            break
        except Exception as e:
            print(f"Error: {str(e)}")
            time.sleep(5)

if __name__ == "__main__":
    main()