import os
import google.generativeai as genai
import json
import tempfile
from google.cloud import secretmanager
from cloud_storage import download_from_gcs, upload_to_gcs
from config import BUCKET_NAME
import logging
import re  # Import the regular expression module

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def access_secret(secret_name):
    """Access the API key from Google Secret Manager."""
    client = secretmanager.SecretManagerServiceClient()
    project_id = "project-1-kaia-perez-hvala"
    secret_path = f"projects/{project_id}/secrets/{secret_name}/versions/latest"

    response = client.access_secret_version(request={"name": secret_path})
    return response.payload.data.decode("UTF-8")

# Fetch the API key from Secret Manager
api_key = access_secret("GEMINI_API_KEY")

# Configure Gemini API
genai.configure(api_key=api_key)

# Generation configuration settings
generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}

# Safety settings configuration (optional)
safety_settings = [
    {"category": "HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "DANGEROUS", "threshold": "BLOCK_NONE"},
    {"category": "SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
]

# Prompt for Gemini to generate a title and description
PROMPT = """
You are an expert image caption writer. Analyze the image and generate a concise title and a detailed description.
Provide only the title and description in strict JSON format, without any introductory phrases or additional text.
Return the output in strict JSON format like this:
{
    "title": "the generated title",
    "description": "the generated description"
}
"""

# Initialize the Gemini model
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=generation_config,
    safety_settings=safety_settings,
)

# Upload the image content to Gemini
def upload_to_gemini(file_content, mime_type="image/jpeg"):
    """Uploads the image file content to Gemini."""
    # Use tempfile to create a file-like object from the image content
    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        tmp_file.write(file_content)
        tmp_file_path = tmp_file.name

    # Upload the image from the temporary file path
    uploaded_file = genai.upload_file(tmp_file_path, mime_type=mime_type)
    logger.info(
        f"Uploaded file: {uploaded_file.display_name} as {uploaded_file.uri}"
    )
    os.unlink(tmp_file_path)  # Delete the temporary file
    return uploaded_file

def create_json_file(bucket_name, filename, title, description, status = "success"):
    """Creates and uploads the json to GCS."""
    metadata = {"title": title, "description": description, "status": status}
    json_content = json.dumps(metadata, indent=4)
    json_filename = filename.rsplit(".", 1)[0].replace(" ", "_") + ".json"
    upload_to_gcs(json_content, BUCKET_NAME, json_filename, content_type="application/json")
    logger.info(f"Saved title and description to {json_filename}")
    
def create_text_file(bucket_name, filename, title, description):
    """Creates and uploads the text to GCS."""
    text_content = f"Title: {title}\nDescription: {description}"
    text_filename = filename.rsplit(".", 1)[0].replace(" ", "_") + ".txt"
    upload_to_gcs(text_content, BUCKET_NAME, text_filename, content_type="text/plain")
    logger.info(f"Saved title and description to {text_filename}")

# Generate the title and description for the image
def generate_title_description(bucket_name, filename):
    """
    Generates a title and description for an image using the Gemini API.
    Returns the title and description as a dictionary.
    """
    logger.info(f"Generating title and description for {filename}")
    # Download the image content from GCS
    image_content = download_from_gcs(bucket_name, filename)

    # Upload the image content to Gemini
    uploaded_file = upload_to_gemini(image_content, mime_type="image/jpeg")

    # Generate content using the uploaded file
    try:
        response = model.generate_content([uploaded_file, PROMPT])
        response.resolve()
        logger.info(f"Gemini's raw response for {filename}: {response.text}")  # Log the raw response

        # Check if the response is empty
        if not response.text or response.text.isspace():
            logger.error(f"Gemini returned an empty response for {filename}")
            raise ValueError(f"Gemini returned an empty response for {filename}")

        # Clean up the response using regex
        cleaned_response = response.text
        match = re.search(r"\{.*?\}(?=\s*|$)", cleaned_response, re.DOTALL)
        if match:
            cleaned_response = match.group(0)
        else:
            logger.error(f"No JSON found in response for {filename}")
            raise ValueError(f"No JSON found in response for {filename}")

        # Attempt to parse the cleaned response
        try:
            response_json = json.loads(cleaned_response)
        except json.JSONDecodeError:
            logger.error(f"JSON decoding error after cleaning for {filename}: {cleaned_response}")
            raise ValueError(f"JSON decoding error after cleaning for {filename}: {cleaned_response}")


        # Load the json
        title = response_json.get("title", "Untitled")
        description = response_json.get("description", "No description available")

        create_json_file(bucket_name, filename, title, description)
        create_text_file(bucket_name, filename, title, description)
        
        return {"title": title, "description": description}

    except ValueError as e:
        # Handle the errors and return an error message
        logger.error(f"Error generating title and description for {filename}: {e}")
        return {"title": "Error generating title", "description": "Error generating description"}

    except Exception as e:
        logger.error(f"An unexpected error occurred for {filename}: {e}")
        return {"title": "Error generating title", "description": "Error generating description"}