import openai
from dotenv import load_dotenv
import os
import re
import json
import time
from functools import lru_cache
import pandas as pd
from datetime import datetime
import httpx

# Load environment variables
load_dotenv()

# Create custom HTTP client without proxies
http_client = httpx.Client(
    base_url="https://api.openai.com/v1",
    timeout=60.0,
    follow_redirects=True
)



# Set up OpenAI client
client = openai.OpenAI(
    api_key=os.getenv('OPENAI_API_KEY'),
    http_client=http_client
)

# Print the first few characters of the API key (for verification)
if client.api_key:
    print(f"API key loaded: {client.api_key[:5]}...")
else:
    print("No API key found!")

class ShoppingItemParser:
    def __init__(self):
        self.units = {
            'box': ['box', 'boxes', 'bx', 'carton', 'cartons', 'pack', 'packs', 'packet', 'packets'],
            'unit': ['unit', 'units'],
            'pcs': ['pcs', 'piece', 'pieces', 'pc'],
            'l': ['l', 'liter', 'liters', 'litre', 'litres'],
            'ml': ['ml', 'milliliter', 'milliliters']
        }
        
        # System prompt for OpenAI
        self.system_prompt = """You are a shopping item analyzer. Extract the following information from the given text:
1. Item name (main product)
2. Quantity (numeric value)
3. Unit of measurement
4. Brand name (if mentioned)
5. Priority level (HIGH, MEDIUM, or LOW)
6. Additional details or specifications

Return the information in this exact JSON format and similar english meaning word.ALso for brand name, consider using synonyms and search engine to find the most relevant one.
{
    "itemName": "product name",
    "quantity": "numeric value or empty string",
    "unit": "unit of measurement or empty string",
    "brand": "brand name or empty string",
    "priority": "HIGH/MEDIUM/LOW",
    "details": "additional details or empty string"
}"""

    def parse_with_context(self, text):
        try:
            # First try OpenAI analysis
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": text}
                ],
                temperature=0.2,
                max_tokens=150
            )
            
            # Parse OpenAI response
            ai_result = json.loads(response.choices[0].message.content)
            
            # Validate and standardize the result
            result = {
                "quantity": ai_result.get("quantity", ""),
                "unit": self._standardize_unit(ai_result.get("unit", "")),
                "itemName": ai_result.get("itemName", ""),
                "brand": ai_result.get("brand", ""),
                "priority": ai_result.get("priority", "MEDIUM"),
                "details": ai_result.get("details", ""),
                "description": text
            }
            
            return result
            
        except Exception as e:
            print(f"Error in parse_with_context: {e}")
            # Fallback to basic parsing if OpenAI fails
            return self._fallback_parse(text)
    
    def _standardize_unit(self, unit):
        """Standardize unit to a known format"""
        if not unit:
            return ""
            
        unit = unit.lower().strip()
        for std_unit, variations in self.units.items():
            if unit in variations or unit.rstrip('s') in variations:
                return std_unit
        return unit
    
    def _fallback_parse(self, text):
        """Basic fallback parsing when OpenAI fails"""
        return {
            "quantity": "",
            "unit": "",
            "itemName": text,
            "brand": "",
            "priority": "MEDIUM",
            "details": "",
            "description": text
        }

def analyze_text(text):
    """Main function to analyze shopping item text"""
    parser = ShoppingItemParser()
    return parser.parse_with_context(text)

if __name__ == '__main__':
    # Test single item analysis
    test_text = "1l milk of amul brand"
    print("\nTesting single item analysis:")
    result = analyze_text(test_text)
    print(f"Analysis result: {json.dumps(result, indent=2)}")

    
    def process_file(input_file, output_file):
        try:
            # Read the input Excel file
            print(f"Reading input file: {input_file}")
            df = pd.read_excel(input_file)
            
            # Prepare a list to hold the results
            results = []
            
            # Iterate through each row in the DataFrame
            for index, row in df.iterrows():
                # Get the text from the first column, regardless of its name
                text = str(row.iloc[0]) if not pd.isna(row.iloc[0]) else ""
                print(f"Processing row {index + 1}: {text}")
                
                if text.strip():  # Only process non-empty rows
                    analysis_result = analyze_text(text)
                    if analysis_result:
                        results.append(analysis_result)
            
            if results:
                # Create a new DataFrame from the results
                results_df = pd.DataFrame(results)
                
                # Reorder columns for better readability
                column_order = ['quantity', 'unit', 'itemName', 'brand', 'priority', 'details', 'description']
                results_df = results_df.reindex(columns=column_order)
                
                # Write the results to an Excel file
                results_df.to_excel(output_file, index=False)
                print(f"Successfully wrote output to: {output_file}")
            else:
                print("No results to write to output file")
                
        except FileNotFoundError:
            print(f"Error: Input file '{input_file}' not found")
        except Exception as e:
            print(f"An error occurred: {e}")
            raise  # This will show the full error traceback


    # Define input and output file paths
    input_file = 'processing/inputfile.xlsx'
    output_file = 'processing/output.xlsx'
    
    # Process the file
    #process_file(input_file, output_file)
    print(analyze_text("Cereal brand: Morning Star, sugar check needed for 4 boxes, medium priority."))
    
    print("\nProcessing complete!")

