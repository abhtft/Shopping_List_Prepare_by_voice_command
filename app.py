from flask import Flask, request, jsonify, send_from_directory, make_response
from flask_cors import CORS
from pymongo import MongoClient
from datetime import datetime
import os
from dotenv import load_dotenv
import nltk
import re
#import assemblyai as aai


from analyser import process_excel,ShoppingItemParser
import pytz
import openai
import json
import time
from functools import lru_cache
import pandas as pd
from bson import ObjectId
import httpx

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__, static_folder='dist', static_url_path='')

# Configure CORS
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

# Initialize MongoDB
try:
    MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
    client = MongoClient(MONGODB_URI)
    db = client.ShoppingV3_Voice_API
    print("✅ MongoDB Connection Successful!")
except Exception as e:
    print("❌ MongoDB Connection Error:", e)
    db = None

# Download required NLTK data
try:
    nltk.download('punkt')
    nltk.download('averaged_perceptron_tagger')
    nltk.download('maxent_ne_chunker', quiet=True)
    nltk.download('words', quiet=True)
    print("✅ NLP resources downloaded successfully")
except Exception as e:
    print(f"❌ Error downloading NLP resources: {e}")

# Configure AssemblyAI
#aai.settings.api_key = os.getenv("ASSEMBLYAI_API_KEY")

# Initialize the shopping item parser
parser = ShoppingItemParser()

# Initialize Azure OpenAI client
try:
    # Get Azure OpenAI configuration from environment variables
    azure_openai_endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
    azure_openai_api_key = os.getenv('AZURE_OPENAI_API_KEY')
    azure_openai_api_version = os.getenv('AZURE_OPENAI_API_VERSION', '2024-02-15-preview')
    azure_openai_deployment_name = os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME')
    
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
    openai_client = openai.AzureOpenAI(
        api_key=azure_openai_api_key,
        api_version=azure_openai_api_version,
        azure_endpoint=endpoint,
        http_client=http_client
    )
    print("✅ Azure OpenAI client initialized successfully")
    print(f"   Endpoint: {azure_openai_endpoint}")
    print(f"   Deployment: {azure_openai_deployment_name}")
    print(f"   API Version: {azure_openai_api_version}")
    
except Exception as e:
    print(f"❌ Error initializing Azure OpenAI client: {e}")
    raise

# Set up MongoDB Atlas connection
MONGODB_URI = os.getenv('MONGODB_URI')
mongo_client = MongoClient(MONGODB_URI)
db = mongo_client['grocery_db']
collection = db['cereal_analysis']

@app.route('/')
def serve():
    try:
        response = make_response(send_from_directory(app.static_folder, 'index.html'))
        response.headers['Content-Type'] = 'text/html; charset=utf-8'
        return response
    except Exception as e:
        print(f"Error serving index.html: {e}")
        return "Server Error", 500

@app.route('/<path:path>')
def serve_static(path):
    try:
        if path and os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
        return "Not Found", 404
    except Exception as e:
        print(f"Error serving static file {path}: {e}")
        return "Server Error", 500

@app.route('/api/analyze', methods=['POST'])
def analyze():
    try:
        data = request.json
        text = data.get('text', '')
        
        if not text:
            return jsonify({'error': 'No text provided'}), 400
            
        # Use the parser to analyze text
        result = parser.analyze(text)
        return jsonify(result)
        
    except Exception as e:
        print(f"Error in analyze endpoint: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api', methods=['POST', 'OPTIONS'])
def save_shopping_list():
    if request.method == 'OPTIONS':
        return '', 200
        
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        print("📥 Received data at /api:", data)

        # Convert UTC to IST and format up to seconds
        ist = pytz.timezone('Asia/Kolkata')
        utc_now = datetime.utcnow()
        ist_now = utc_now.replace(tzinfo=pytz.UTC).astimezone(ist)
        data['created_at'] = ist_now.strftime('%Y-%m-%d %H:%M:%S')

        # Save to MongoDB
        result = db.lists.insert_one(data)
        print("✅ Saved to MongoDB with ID:", result.inserted_id)
        print("📝 Bill Number:", data['billNumber'])

        # Save to Excel
        try:
            # Create the processing folder if it doesn't exist
            os.makedirs('processing', exist_ok=True)
            
            # Define the output file path
            output_file = os.path.join('processing', 'output_app.xlsx')
            
            # Convert the data to a DataFrame
            df = pd.DataFrame([data])
            
            # If the file already exists, append to it
            if os.path.exists(output_file):
                df = pd.read_excel(output_file)
                existing_df = pd.read_excel(output_file)
                df = pd.concat([existing_df, df], ignore_index=True)
            
            # Save the DataFrame to Excel
            df.to_excel(output_file, index=False)
            print(f"✅ Saved to Excel at: {output_file}")
        except Exception as excel_error:
            print(f"❌ Error saving to Excel: {excel_error}")



        return jsonify({
            'success': True,
            'id': str(result.inserted_id),
            'billNumber': data['billNumber']
        }), 201
    except Exception as e:
        print("❌ Error while processing /api request:", str(e))
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'mongodb': 'connected'
    }), 200

@app.route('/api/transcribe', methods=['POST', 'OPTIONS'])
def transcribe_audio():
    """
    NOTE: We are using Web Speech API directly in the frontend for faster transcription.
    This endpoint is kept for reference but not used.
    """
    # if request.method == 'OPTIONS':
    #     return '', 200
        
    # try:
    #     if 'audio' not in request.files:
    #         return jsonify({'error': 'No audio file provided'}), 400
            
    #     audio_file = request.files['audio']
    #     if not audio_file.filename:
    #         return jsonify({'error': 'No audio file selected'}), 400
            
    #     # Save the audio file temporarily
    #     temp_path = os.path.join('temp', audio_file.filename)
    #     os.makedirs('temp', exist_ok=True)
    #     audio_file.save(temp_path)
        
    #     # Transcribe using AssemblyAI
    #     transcriber = aai.Transcriber()
    #     transcript = transcriber.transcribe(temp_path)
        
    #     # Clean up the temporary file
    #     os.remove(temp_path)
        
    #     if transcript.error:
    #         return jsonify({'error': transcript.error}), 500
            
    #     return jsonify({
    #         'text': transcript.text,
    #         'confidence': transcript.confidence
    #     })
        
    # except Exception as e:
    #     print(f"❌ Error in transcription: {str(e)}")
    #     return jsonify({
    #         'error': str(e)
    #     }), 500
    
    # Return empty response since we're using Web Speech API

    #any one side web speech API was needed to be used
    return jsonify({'message': 'Using Web Speech API instead'}), 200

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Resource not found"}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error"}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    print(f"�� Server starting on https://localhost:{port}")
    print(f"📁 Serving static files from: {os.path.abspath(app.static_folder)}")
    
    # Check if SSL certificates exist, if not generate them
    if not (os.path.exists('cert.pem') and os.path.exists('key.pem')):
        print("🔒 Generating SSL certificates...")
        from generate_cert import generate_self_signed_cert
        generate_self_signed_cert()
    
    # Run with SSL
    app.run(
        host='0.0.0.0',
        port=port,
        debug=True,
        ssl_context=('cert.pem', 'key.pem')
    )