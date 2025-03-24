import os
from typing import Dict, Optional, Any
import json
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

class TextParser:
    """A generalized text parser that extracts structured information from any text format."""
    
    def __init__(self, schema: Optional[Dict] = None):
        """Initialize the parser with Groq LLM and optional schema."""
        # Initialize Groq LLM with enhanced settings for better comprehension
        self.model = ChatGroq(
            api_key=os.environ.get("GROQ_API_KEY", "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"),
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
        system_prompt = """You are an advanced text parser specialized in extracting structured information from any text format.
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
4. Maintain consistency in formatting across all fields
5. If information is ambiguous, use your best judgment based on context
6. Handle variations in date/time formats, names, and numerical values

Return the information in this exact JSON format:
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
        return text.strip()

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
                else:
                    raise json.JSONDecodeError("No JSON found", response_text, 0)
                
                # Ensure all schema fields are present
                for field in self.schema:
                    if field not in parsed_data:
                        parsed_data[field] = None
                
                return parsed_data
                
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
    parser = TextParser()
    
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
