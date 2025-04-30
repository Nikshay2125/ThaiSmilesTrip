import os
from typing import Dict, Optional, Any
import json
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from dotenv import load_dotenv
import re

load_dotenv()

class DriverDetailsParser:
    """A parser that extracts driver details from agent responses."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is required")
            
        self.model = ChatGroq(
            api_key=self.api_key,
            model_name="llama-3.3-70b-versatile",
            temperature=0.1,
            max_tokens=500,
            model_kwargs={
                "top_p": 0.9,
                "frequency_penalty": 0.1,
                "presence_penalty": 0.1,
            },
        )
        
        # Define the schema for driver details
        self.schema = {
            "name": "Driver's full name",
            "contact": "Driver's contact number",
            "vehicle": {
                "model": "Vehicle model/make",
                "registration": "Vehicle registration number",
                "color": "Vehicle color",
                "features": "Special features of the vehicle"
            },
            "estimated_arrival": "Estimated arrival time (in DD MMM YYYY HH:MM AM/PM format)",
            "notes": "Additional notes or instructions"
        }
        
        # Create a prompt template for driver information extraction
        system_prompt = """You are an advanced parser specialized in extracting driver and vehicle details from emails.
Your task is to analyze the provided text and extract information according to the specified schema.

SCHEMA:
{schema}

INSTRUCTIONS:
1. Carefully analyze the entire text to understand its context and structure
2. Extract all relevant information that matches the schema
3. Format the extracted information according to these rules:
   - Driver name should be in proper case
   - Contact numbers should maintain their format with country code if provided
   - Vehicle details should be comprehensive
   - Estimated arrival should be in DD MMM YYYY HH:MM AM/PM format
   - Use null for missing or non-applicable fields
4. If information is ambiguous, use your best judgment based on context

Return the information in this exact JSON format:
{{
  "name": "Driver Name",
  "contact": "Contact Number",
  "vehicle": {{
    "model": "Vehicle Model",
    "registration": "Registration Number",
    "color": "Color",
    "features": "Special Features or null"
  }},
  "estimated_arrival": "DD MMM YYYY HH:MM AM/PM",
  "notes": "Additional Notes or null"
}}"""

        user_prompt = "Extract driver details from this email response:\n\n{text}"
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", user_prompt)
        ])

    def _clean_text(self, text: str) -> str:
        """Clean and normalize input text."""
        if not text:
            return ""
        
        # Basic text cleaning
        text = text.replace('\\n', '\n')
        text = text.replace('\\r', '')
        text = '\n'.join(line.strip() for line in text.split('\n'))
        
        # Remove common email footers
        footer_patterns = [
            r'This email and any files transmitted with it',
            r'CONFIDENTIALITY NOTICE',
            r'____+',
            r'\*\*\*\*+',
            r'Sent from my iPhone',
            r'Get Outlook for'
        ]
        
        for pattern in footer_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                text = text[:match.start()].strip()
                
        return text.strip()

    def parse_driver_details(self, text: str) -> Dict[str, Any]:
        """Parse driver details from the agent's email response."""
        if not text:
            return {
                "name": None,
                "contact": None,
                "vehicle": {
                    "model": None,
                    "registration": None,
                    "color": None,
                    "features": None
                },
                "estimated_arrival": None,
                "notes": None
            }
            
        # Clean the text first
        cleaned_text = self._clean_text(text)
        
        # Process with LLM for extraction
        chain = self.prompt | self.model
        result = chain.invoke({"text": cleaned_text, "schema": json.dumps(self.schema, indent=2)})
        
        try:
            # Extract JSON from the response
            json_pattern = r'```json(.*?)```|{.*}'
            json_match = re.search(json_pattern, result.content, re.DOTALL)
            
            if json_match:
                json_str = json_match.group(1) if json_match.group(1) else json_match.group(0)
                json_str = json_str.strip()
                parsed_data = json.loads(json_str)
            else:
                # Try to find JSON without backticks
                json_str = result.content
                # Find the first { and last }
                start = json_str.find('{')
                end = json_str.rfind('}') + 1
                if start >= 0 and end > 0:
                    json_str = json_str[start:end]
                    parsed_data = json.loads(json_str)
                else:
                    # Fallback if we can't extract valid JSON
                    return {
                        "name": None,
                        "contact": None,
                        "vehicle": {
                            "model": None,
                            "registration": None,
                            "color": None,
                            "features": None
                        },
                        "estimated_arrival": None,
                        "notes": None
                    }
            
            # Ensure all fields are present
            if "vehicle" not in parsed_data:
                parsed_data["vehicle"] = {}
                
            for vehicle_field in ["model", "registration", "color", "features"]:
                if vehicle_field not in parsed_data["vehicle"]:
                    parsed_data["vehicle"][vehicle_field] = None
                    
            for field in ["name", "contact", "estimated_arrival", "notes"]:
                if field not in parsed_data:
                    parsed_data[field] = None
                    
            return parsed_data
            
        except json.JSONDecodeError:
            print("Error decoding JSON from LLM response")
            return {
                "name": None,
                "contact": None,
                "vehicle": {
                    "model": None,
                    "registration": None,
                    "color": None,
                    "features": None
                },
                "estimated_arrival": None,
                "notes": None
            }

def main():
    """Test the driver details parser with a sample email."""
    api_key = os.getenv("GROQ_API_KEY")
    parser = DriverDetailsParser(api_key)
    
    # Sample email response
    sample_email = """
    Subject: Re: Driver Assignment for Request REQ_20250409_200716_0
    
    Hello,
    
    I can confirm that I'll be handling this pickup for John Smith on March 15th.
    
    Driver Details:
    - Name: Robert Thompson
    - Contact: +44792123456
    
    Vehicle Information:
    - Mercedes S-Class, Black
    - Registration: LX21 ABC
    - Features: WiFi, Water, Phone Chargers
    
    I'll arrive at Heathrow Airport at 2:00 PM (30 minutes before the pickup time) and will be waiting at the arrivals area with a name sign.
    
    Please let me know if you need any further information.
    
    Best regards,
    Robert
    """
    
    driver_details = parser.parse_driver_details(sample_email)
    print(json.dumps(driver_details, indent=2))

if __name__ == "__main__":
    main() 