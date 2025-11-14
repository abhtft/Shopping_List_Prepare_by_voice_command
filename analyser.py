import os
import json
import pandas as pd
from dotenv import load_dotenv
import openai
import httpx

# ----------------------------
# 1. Environment & Client Setup
# ----------------------------
load_dotenv()

# Get Azure OpenAI configuration from environment variables
azure_openai_endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
azure_openai_api_key = os.getenv('AZURE_OPENAI_API_KEY')
azure_openai_api_version = os.getenv('AZURE_OPENAI_API_VERSION', '2024-02-15-preview')
azure_openai_deployment_name = os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME','gpt-4.1')

# Validate required environment variables
if not azure_openai_endpoint:
    raise ValueError("AZURE_OPENAI_ENDPOINT environment variable is required")
if not azure_openai_api_key:
    raise ValueError("AZURE_OPENAI_API_KEY environment variable is required")
if not azure_openai_deployment_name:
    raise ValueError("AZURE_OPENAI_DEPLOYMENT_NAME environment variable is required")

# Ensure endpoint doesn't have trailing slash (Azure OpenAI client handles /v1 automatically)
endpoint = azure_openai_endpoint.rstrip('/')

# Create custom HTTP client for Azure OpenAI (optional - AzureOpenAI handles most of this)
http_client = httpx.Client(
    timeout=60.0,
    follow_redirects=True
)

# Initialize Azure OpenAI client
client = openai.AzureOpenAI(
    api_key=azure_openai_api_key,
    api_version=azure_openai_api_version,
    azure_endpoint=endpoint,
    http_client=http_client
)

# ----------------------------
# 2. Configurations (No Hardcoding) in dictionary form
# ----------------------------
#instructive prompt with clear what not to do
CONFIG = {
    "deployment_name": azure_openai_deployment_name,  # Azure OpenAI uses deployment names instead of model names
    "temperature": 0.2,
    "max_tokens": 2000,
    "system_prompt": """You are a shopping item analyzer. 

Extract structured information in strict JSON with the following fields:
{
  "itemName": "product name",
  "quantity": "numeric value or empty string",
  "unit": "unit of measurement or empty string",
  "brand": "brand name or empty string",
  "priority": "HIGH/MEDIUM/LOW",
  "details": "extra details or empty string"
}
Only return valid JSON (no explanations).
"""
}


# ----------------------------
# 3. Core Analyzer
# ----------------------------
class ShoppingItemParser:
    def __init__(self, config=CONFIG):
        self.config = config

    def analyze(self, text: str) -> dict:
        """
        Passes text to LLM and returns structured JSON.
        Falls back to safe parsing if LLM fails.
        """
        try:
            response = client.chat.completions.create(
                model=self.config["deployment_name"],  # Azure OpenAI uses deployment name instead of model name
                messages=[
                    {"role": "system", "content": self.config["system_prompt"]},
                    {"role": "user", "content": text}
                ],
                temperature=self.config["temperature"],
                max_tokens=self.config["max_tokens"]
            )

            # Parse JSON safely
            raw_output = response.choices[0].message.content.strip()
            result = json.loads(raw_output)

            # Always include original description
            result["description"] = text
            return result

        except Exception as e:
            print(f"⚠️ LLM error: {e} → using fallback for: {text}")
            return self._fallback_parse(text)

    def _fallback_parse(self, text: str) -> dict:
        """Minimal fallback if LLM fails"""
        return {
            "itemName": text,
            "quantity": "",
            "unit": "",
            "brand": "",
            "priority": "MEDIUM",
            "details": "",
            "description": text
        }


# ----------------------------
# 4. File Processing Utility
# ----------------------------
def process_excel(input_file: str, output_file: str, parser: ShoppingItemParser):
    try:
        df = pd.read_excel(input_file)
        results = []

        for idx, row in df.iterrows():
            text = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ""
            if text.strip():
                print(f"🔍 Processing row {idx+1}: {text}")
                results.append(parser.analyze(text))

        if results:
            results_df = pd.DataFrame(results)
            col_order = ["quantity", "unit", "itemName", "brand", "priority", "details", "description"]
            results_df = results_df.reindex(columns=col_order)
            results_df.to_excel(output_file, index=False)
            print(f"✅ Saved results to {output_file}")
        else:
            print("⚠️ No valid rows found.")

    except Exception as e:
        print(f"❌ Error in processing file: {e}")


# ----------------------------
# 5. Example Usage
# ----------------------------
if __name__ == "__main__":
    parser = ShoppingItemParser()

    # Example single test
    print("\n=== Single Item Test ===")
    example = "Cereal brand: Morning Star, sugar check needed for 4 boxes, medium priority."
    print(json.dumps(parser.analyze(example), indent=2))

    # Example Excel file processing
    # process_excel("processing/inputfile.xlsx", "processing/output.xlsx", parser)

    print("\n✅ Processing complete.")
