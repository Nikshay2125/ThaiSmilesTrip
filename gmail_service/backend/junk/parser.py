import os
from typing import Dict, Optional, Any
import json
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from dotenv import load_dotenv
import os
import re

load_dotenv() 

class TextParser:
    """A generalized text parser that extracts structured information from any text format."""
    
    def __init__(self, api_key: str,  schema: Optional[Dict] = None):
        self.api_key = api_key
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is required")
            
        self.model = ChatGroq(
            api_key=self.api_key,
            model_name="llama-3.3-70b-versatile",
            temperature=0.1,
            max_tokens=500,  # Increased for better context understanding
            model_kwargs={
                "top_p": 0.9,
                "frequency_penalty": 0.1,
                "presence_penalty": 0.1,
            },
        )
        
        # Default schema for travel/booking related information
        self.default_schema = {
            "date": "DD MMM YYYY formatted date",
            "guest_name": "Full name of the guest",
            "pax": "Number of guests/people (integer)",
            "flight_no": "Flight number if available",
            "pickup_time": "Time in HH:MM AM/PM format", 
            "pickup_location": "Location for pickup",
            "hotel_drop": "Hotel or drop-off location",
            "tour": "Tour details if applicable",
            "payment": "Payment information if available",
            "code": "Booking or reference code"
        }
        
        # Use provided schema or default
        self.schema = schema if schema else self.default_schema
        
        # Create a powerful prompt template for information extraction
        system_prompt = """You are an advanced text parser specialized in extracting structured information from booking and travel-related emails.
Your task is to analyze the provided text and extract information according to the specified schema.

SCHEMA:
{schema}

INSTRUCTIONS:
1. Carefully analyze the entire text to understand its context and structure
2. Extract all relevant information that matches the schema
3. Format the extracted information according to these rules:
   - Dates must be in DD MMM YYYY format (e.g., 15 Mar 2024)
   - Times must be in HH:MM AM/PM format (e.g., 09:30 AM)
   - Names should be in proper case
   - Numbers should be integers where appropriate
   - Use null for missing or non-applicable fields
4. Infer missing information when possible based on context clues
5. If information is ambiguous, use your best judgment based on context
6. Handle variations in date/time formats, names, and numerical values
7. IMPORTANT: For dates, if only month and day are provided, infer the year using context

EXAMPLE CONVERSIONS:
- "March 15" -> "15 Mar 2024" (current or upcoming year)
- "2:30 PM" -> "02:30 PM"
- "3 guests" -> pax: 3
- "BA789" or "Flight BA789" -> flight_no: "BA789"

Return the information in this exact JSON format, with values properly formatted according to the schema:
{{
  "date": "DD MMM YYYY",
  "guest_name": "Name",
  "pax": integer,
  "flight_no": "Number",
  "pickup_time": "HH:MM AM/PM",
  "pickup_location": "Location",
  "hotel_drop": "Location",
  "tour": "Details or null",
  "payment": "Info or null",
  "code": "Reference"
}}"""

        user_prompt = "Extract information from this text into the specified JSON format:\n\n{text}"
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", user_prompt)
        ])

    def _clean_text(self, text: str) -> str:
        """Clean and normalize input text."""
        if not text:
            return ""
        
        # Basic text cleaning while preserving important formatting
        text = text.replace('\\n', '\n')  # Preserve newlines
        text = text.replace('\\r', '')
        text = '\n'.join(line.strip() for line in text.split('\n'))  # Clean each line
        
        # Remove common email footers
        # Look for common email footer markers
        footer_patterns = [
            r'This email and any files transmitted with it',
            r'CONFIDENTIALITY NOTICE',
            r'____+',  # Long underscores
            r'\*\*\*\*+',  # Long asterisks
            r'Sent from my iPhone',
            r'Get Outlook for'
        ]
        
        for pattern in footer_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                text = text[:match.start()].strip()
                
        return text.strip()

    def _normalize_parsed_data(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize and clean parsed data."""
        normalized = {}
        
        # Process each field according to its expected format
        for field, value in parsed_data.items():
            if field not in self.schema:
                continue
                
            if value is None or value == "null" or value == "":
                normalized[field] = None
                continue
                
            # Convert to string for string fields
            if isinstance(value, (int, float)) and field != "pax":
                value = str(value)
                
            # Handle date field
            if field == "date" and value:
                # Ensure date is in DD MMM YYYY format
                date_patterns = [
                    # Match various date formats and normalize
                    (r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})', r'\1 {month_name} \3'),
                    (r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})', r'\3 {month_name} \1'),
                    (r'(\d{1,2})(?:st|nd|rd|th)? (\w+),? (\d{4})', r'\1 \2 \3'),
                ]
                
                # Already in correct format
                if re.match(r'^\d{1,2} \w{3} \d{4}$', value):
                    normalized[field] = value
                else:
                    # Try to apply transformations
                    normalized[field] = value
            
            # Handle pax/guests field - ensure it's an integer
            elif field == "pax" and value:
                try:
                    if isinstance(value, str):
                        # Extract number from string like "3 guests"
                        num_match = re.search(r'(\d+)', value)
                        if num_match:
                            normalized[field] = int(num_match.group(1))
                        else:
                            normalized[field] = None
                    else:
                        normalized[field] = int(value)
                except (ValueError, TypeError):
                    normalized[field] = None
            
            # Handle time field - ensure it's in HH:MM AM/PM format
            elif field == "pickup_time" and value:
                # Check if already in correct format
                if re.match(r'^\d{1,2}:\d{2} [AP]M$', value):
                    # Normalize to ensure 2 digits for hour
                    hour, rest = value.split(':', 1)
                    normalized[field] = f"{int(hour):02d}:{rest}"
                else:
                    # Try to convert to correct format
                    normalized[field] = value
            
            # All other fields
            else:
                normalized[field] = value
                
        # Ensure all schema fields are present
        for field in self.schema:
            if field not in normalized:
                normalized[field] = None
                
        return normalized

    def parse_text(self, text: str) -> Dict[str, Any]:
        """Parse any text input and extract structured information."""
        if not text:
            return {field: None for field in self.schema.keys()}
            
        try:
            # Clean the input text
            cleaned_text = self._clean_text(text)
            
            # Prepare the context with schema and text
            context = {
                "text": cleaned_text,
                "schema": json.dumps(self.schema, indent=2)
            }
            
            # Process with LLM
            try:
                chain = self.prompt | self.model
                result = chain.invoke(context)
                
                # Extract JSON from response
                response_text = result.content
                # Find JSON block between curly braces
                start = response_text.find('{')
                end = response_text.rfind('}') + 1
                if start >= 0 and end > start:
                    json_str = response_text[start:end]
                    parsed_data = json.loads(json_str)
                    
                    # Normalize and clean the parsed data
                    normalized_data = self._normalize_parsed_data(parsed_data)
                    return normalized_data
                else:
                    raise json.JSONDecodeError("No JSON found", response_text, 0)
                
            except json.JSONDecodeError as e:
                print(f"Error parsing LLM response: {str(e)}")
                return {field: None for field in self.schema.keys()}
                
            except Exception as e:
                print(f"Error in LLM processing: {str(e)}")
                return {field: None for field in self.schema.keys()}
                
        except Exception as e:
            print(f"Unexpected error in parsing: {str(e)}")
            return {field: None for field in self.schema.keys()}

def main():
    """Test the text parser with sample data."""
    # Initialize parser
    parser = TextParser(os.getenv("GROQ_API_KEY"))
    
    # Sample text in different formats
    test_cases = [
        # Standard format
        """DATE:- 04 FEB
        GUEST NAME : GUNJAN KEDAWAT
        PAX:- 01 
        Flights no:- 6E 6568
        PICKUP TIME : 11.00 AM
        HOTEL DROP : centara grand central ladprao Bangkok
        PICKUP : BKK AIRPORT
        Code - 29""",
        
        # Natural language format
        """Hello, this is a booking confirmation for John Smith. 
        He will be arriving on March 15th, 2024 on flight BA789. 
        Please arrange pickup from Heathrow Airport at 2:30 PM. 
        There will be 3 people in total. They'll be staying at the Ritz Hotel.
        Booking reference: BOOK123.""",
        
        # Minimal information
        """Guest: Alice Johnson
        Date: 20/04/2024
        Pick up from: Central Station
        Reference: REF456"""
    ]
    
    # Test each case
    for i, test_text in enumerate(test_cases, 1):
        print(f"\nTest Case {i}:")
        print("-" * 50)
        result = parser.parse_text(test_text)
        print(json.dumps(result, indent=2))
        print("-" * 50)

if __name__ == "__main__":
    main()
