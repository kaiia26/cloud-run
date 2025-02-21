from google import genai
import google.generativeai as genai
import cloud_storage
from config import BUCKET_NAME
import json


genai.configure(api_key=os.environ['GEMINI_API'])

# Generation configuration settings
generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}

# Safety settings configuration
safety_settings = [
    {"category": "HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    {"category": "SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
]

PROMPT = "Generate a short title and a detailed description for this image."

# Initialize the Gemini model
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=generation_config,
    safety_settings=safety_settings
)

storage_client = storage.Client()
BUCKET_NAME = 'flask-images'

def save_json_to_gcs(bucket_name, filename, data):
    """Saves JSON data to Google Cloud Storage."""
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(filename)
    blob.upload_from_string(json.dumps(data), content_type="application/json")
    print(f"Saved JSON metadata to {filename} in bucket {bucket_name}")

def generate_title_description(filename):
    # Construct the GCS URI
    file_uri = f"gs://{BUCKET_NAME}/{filename}"
    uploaded_file = upload_to_gemini(file_path, mime_type= "image/jpeg")
    response = model.generate_content([uploaded_file, "/n/n", PROMPT])
    response_text = response.text.strip().split("/n", 1)
    title = response_text[0] if response_text else "Untitled"
    description = response_text[1] if len(response_text) > 1 else "No description available"

    # Save metadata as JSON in the same location as the image
    json_filename = filename.rsplit('.', 1)[0] + ".json"
    metadata = {"title": title, "description": description}
    save_json_to_gcs(BUCKET_NAME, json_filename, metadata)
    
    return title, description



