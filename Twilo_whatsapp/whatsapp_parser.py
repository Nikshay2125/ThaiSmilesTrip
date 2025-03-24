import os
from typing import Dict, Optional
from datetime import datetime
import json
import re
import spacy
import time  # Added missing import
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from whatsapp_logger import WhatsAppClient

class WhatsAppMessageParser:
    def __init__(self):
        """Initialize the parser with Groq LLM, spaCy, and WhatsApp client."""
        # Initialize WhatsApp client
        account_sid = 'AC5c49c197045993c193f4a2fb10b7ee38'
        auth_token = '92c2d25859863139a87a6c235f66c4e0'
        self.whatsapp_client = WhatsAppClient(account_sid, auth_token)

        # Initialize Groq LLM
        self.model = ChatGroq(
            api_key=os.environ.get("GROQ_API_KEY", "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"),
            model_name="llama-3.3-70b-versatile", 
            temperature=0.1,
            max_tokens=100,
            model_kwargs={
                "top_p": 0.9,
                "frequency_penalty": 0.3,
                "presence_penalty": 0.3,
            },
        )
        
        # Initialize spaCy
        self.nlp = spacy.load("en_core_web_sm")
        
        # Define the prompt template for message processing
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a precise WhatsApp message parser that extracts specific information.
            You MUST output ONLY a valid JSON object with EXACTLY these fields:
            {{
                "booking_id": <string or null>,
                "start_date": <YYYY-MM-DD string or null>,
                "end_date": <YYYY-MM-DD string or null>, 
                "num_people": <integer or null>,
                "place": <string or null>
            }}
            STRICT RULES:
            1. Output ONLY the JSON object, no other text
            2. No markdown formatting
            3. Fields must be exactly as shown above
            4. booking_id must be a string or null
            5. start_date and end_date must be in YYYY-MM-DD format or null
            6. num_people must be an integer or null
            7. place must be a string or null
            8. If information is unclear or missing, use null
            9. No additional fields or comments allowed"""),
            ("user", "{message_content}")
        ])

    def _preprocess_message(self, content: str) -> str:
        """
        Preprocess message content using spaCy to extract meaningful tokens.
        
        Args:
            content (str): Raw message content
            
        Returns:
            str: Preprocessed content with important tokens
        """
        try:
            if not content:
                return ""
                
            doc = self.nlp(content)
            important_tokens = []
            
            for token in doc:
                # Keep tokens that are:
                # 1. Named entities
                # 2. Numbers
                # 3. Nouns and proper nouns
                # 4. Important verbs
                # 5. Adjectives (for sentiment/urgency)
                if (token.ent_type_ or
                    token.like_num or
                    token.pos_ in {'NOUN', 'PROPN'} or
                    (token.pos_ == 'VERB' and not token.is_stop) or
                    token.pos_ == 'ADJ'):
                    important_tokens.append(token.text)
                
                # Keep basic punctuation for readability
                elif token.text in {'.', ':', ',', '?', '!'}:
                    important_tokens.append(token.text)
            
            preprocessed_text = ' '.join(important_tokens)
            return ' '.join(preprocessed_text.split())
            
        except Exception as e:
            print(f"Warning in preprocessing: {str(e)}")
            return str(content) if content else ""

    def _validate_response(self, response: Dict) -> Dict:
        """Validate and clean the LLM response."""
        validated = {
            "service_name": None,
            "date": None,
            "total_passengers": None
        }
        
        # Validate service_name
        if isinstance(response.get("service_name"), str):
            service_name = response["service_name"].strip()
            validated["service_name"] = service_name if service_name else None
            
        # Validate date
        if response.get("date"):
            validated["date"] = self._validate_date_format(str(response["date"]))
            
        # Validate total_passengers
        try:
            passengers = response.get("total_passengers")
            if passengers is not None:
                passengers = int(passengers)
                validated["total_passengers"] = passengers if passengers > 0 else None
        except (ValueError, TypeError):
            pass
            
        return validated

    def _validate_date_format(self, date_str: str) -> Optional[str]:
        """Validate and normalize date format."""
        if not date_str:
            return None
        
        # Check if already in correct format
        if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
            return date_str
            
        try:
            # Common date formats to try
            formats = [
                "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", 
                "%d-%m-%Y", "%B %d, %Y", "%d %B %Y"
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
                except ValueError:
                    continue
        except Exception:
            pass
        
        return None

    def process_message(self, message_content: str) -> Dict:
        """
        Process a WhatsApp message using LLM with robust error handling.
        
        Args:
            message_content (str): Message content to process
            
        Returns:
            Dict: Validated and cleaned extracted information
        """
        if not message_content:
            return self._validate_response({})
            
        try:
            # Preprocess the message
            preprocessed_content = self._preprocess_message(message_content)
            
            if not preprocessed_content:
                return self._validate_response({})
            
            # Process with LLM
            try:
                chain = self.prompt | self.model
                result = chain.invoke({"message_content": preprocessed_content})
            except Exception as e:
                print(f"LLM processing error: {str(e)}")
                return self._validate_response({})
            
            # Clean up the response
            try:
                response_text = result.content.strip()
                if response_text.startswith("```") and response_text.endswith("```"):
                    response_text = response_text[3:-3].strip()
                if response_text.startswith("json"):
                    response_text = response_text[4:].strip()
                    
                extracted_info = json.loads(response_text)
                
            except (json.JSONDecodeError, AttributeError) as e:
                print(f"JSON parsing error: {str(e)}")
                return self._validate_response({})
                
            return self._validate_response(extracted_info)
            
        except Exception as e:
            print(f"Unexpected error in parsing: {str(e)}")
            return self._validate_response({})

    def fetch_and_process_recent_message(self) -> Optional[Dict]:
        """
        Fetch the most recent WhatsApp message and process it.
        
        Returns:
            Dict: Contains both the original message and processed information
        """
        try:
            recent_message = self.whatsapp_client.get_recent_message()
            
            if not recent_message:
                return None
                
            processed_info = self.process_message(recent_message['body'])
            
            return {
                "original_message": recent_message,
                "processed_info": processed_info
            }
            
        except Exception as e:
            print(f"Error in fetch and process: {str(e)}")
            return None

def main():
    # Example usage
    parser = WhatsAppMessageParser()
    
    print("WhatsApp Message Parser is running! 🚀")
    print("Waiting for messages to process...")
    
    processed_sids = set()
    
    while True:
        try:
            result = parser.fetch_and_process_recent_message()
            
            if result and result['original_message']['sid'] not in processed_sids:
                print("\nNew Message Processed:")
                print("Original Message:", result['original_message']['body'])
                print("\nProcessed Information:")
                print(json.dumps(result['processed_info'], indent=2))
                
                # Send acknowledgement message back to sender
                sender = result['original_message']['from']
                parser.whatsapp_client.send_message(
                    sender.replace('whatsapp:', ''),
                    "Message received! Thank you for contacting us."
                )
                
                processed_sids.add(result['original_message']['sid'])
                
            time.sleep(10)
            
        except KeyboardInterrupt:
            print("\nStopping WhatsApp Message Parser...")
            break
        except Exception as e:
            print(f"Error: {str(e)}")
            time.sleep(5)

if __name__ == "__main__":
    main()