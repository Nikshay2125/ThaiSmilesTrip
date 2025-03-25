from twilio.rest import Client
from datetime import datetime
import json
import os
import time
import re
from datetime import timezone

class WhatsAppClient:
    def __init__(self, account_sid, auth_token):
        self.client = Client(account_sid, auth_token)
        self.from_number = 'whatsapp:+14155238886'
        self.start_time = datetime.now(timezone.utc)  # Store program start time with UTC timezone
        self.last_message_sid = None  # Track the last message we've seen
        
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
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        log_file = f"logs/whatsapp_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.json"
        
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
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
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
        Fetch the most recent incoming WhatsApp message that arrived after program start
        
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
                message_time = message.date_sent
                
                # Skip if we've already processed this message
                if message.sid == self.last_message_sid:
                    return None
                
                # Only process messages that arrived after program start
                if message_time > self.start_time:
                    message_data = {
                        "timestamp": message_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "type": "received",
                        "from": message.from_,
                        "to": message.to,
                        "body": message.body,
                        "sid": message.sid
                    }
                    self._log_message(message_data)
                    print("\nReceived new message:")
                    print(json.dumps(message_data, indent=2))
                    self.last_message_sid = message.sid  # Update last processed message
                    return message_data
            
            return None
                
        except Exception as e:
            print(f"Error fetching messages: {str(e)}")
            return None

def main():
    print("WhatsApp Message Monitor is running! 🚀")
    print("Waiting for incoming messages...")
    
    account_sid = 'AC5c49c197045993c193f4a2fb10b7ee38'
    auth_token = '92c2d25859863139a87a6c235f66c4e0'
    whatsapp_client = WhatsAppClient(account_sid, auth_token)
    
    while True:
        try:
            message = whatsapp_client.get_recent_message()
            if message:
                # Here we'll just log the message, response handling will be in response_system.py
                pass
                
            time.sleep(10)
            
        except KeyboardInterrupt:
            print("\nStopping WhatsApp Message Monitor...")
            break
        except Exception as e:
            print(f"Error: {str(e)}")
            time.sleep(5)

if __name__ == "__main__":
    main()