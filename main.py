from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from werkzeug.utils import secure_filename
import os, io, json, tempfile, logging, re
from google.cloud import storage, secretmanager
import google.generativeai as genai

app = Flask(__name__)
UPLOAD_FOLDER = './files'
ALLOWED_EXTENSIONS = {'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
BUCKET_NAME = os.environ.get("BUCKET_NAME")

# Secret Manager access function
def access_secret(secret_name):
    client = secretmanager.SecretManagerServiceClient()
    project_id = "project-1-kaia-perez-hvala"
    secret_path = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
    response = client.access_secret_version(request={"name": secret_path})
    return response.payload.data.decode("UTF-8")

# Fetch API key and configure Gemini API
api_key = access_secret("GEMINI_API_KEY")
genai.configure(api_key=api_key)

generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}

safety_settings = [
    {"category": "HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "DANGEROUS", "threshold": "BLOCK_NONE"},
    {"category": "SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
]

PROMPT = """
You are an expert image caption writer. Analyze the image and generate a concise title and a detailed description.
Return the output in strict JSON format like this:
{
    "title": "the generated title",
    "description": "the generated description"
}
"""

model = genai.GenerativeModel(model_name="gemini-1.5-flash", generation_config=generation_config, safety_settings=safety_settings)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Google Cloud Storage functions
def upload_to_gcs(file, bucket_name, filename, content_type=None):
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(filename)
    blob.upload_from_string(file, content_type=content_type)

def download_from_gcs(bucket_name, filename):
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(filename)
    return blob.download_as_string()

def list_blobs(bucket_name):
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    return [blob.name for blob in bucket.list_blobs()]

# Upload image content to Gemini
def upload_to_gemini(file_content, mime_type="image/jpeg"):
    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        tmp_file.write(file_content)
        tmp_file_path = tmp_file.name

    try:
        uploaded_file = genai.upload_file(tmp_file_path, mime_type=mime_type)
    except Exception as e:
        print("error")
    finally:
        os.unlink(tmp_file_path)
    return uploaded_file

# Generate JSON metadata file
def create_json_file(bucket_name, filename, title, description, status="success", error_message=None):
    metadata = {"title": title, "description": description, "status": status}
    if error_message:
        metadata["error"] = error_message
    json_content = json.dumps(metadata, indent=4)
    json_filename = filename.rsplit(".", 1)[0].replace(" ", "_") + ".json"
    upload_to_gcs(json_content, bucket_name, json_filename, content_type="application/json")

# Generate title and description
def generate_title_description(bucket_name, filename):
    try:
        image_content = download_from_gcs(bucket_name, filename)
    except Exception as e:
        create_json_file(bucket_name, filename, "Error downloading", "Error downloading", "failure", f"Failed to download: {e}")
        return {"title": "Error downloading file", "description": "Error downloading file"}

    try:
        uploaded_file = upload_to_gemini(image_content, mime_type="image/jpeg")
    except Exception as e:
        create_json_file(bucket_name, filename, "Error uploading", "Error uploading", "failure", f"Failed to upload: {e}")
        return {"title": "Error uploading file", "description": "Error uploading file"}

    try:
        response = model.generate_content([uploaded_file, PROMPT])
        response.resolve()

        match = re.search(r"\{.*?\}(?=\s*|$)", response.text, re.DOTALL)
        if match:
            cleaned_response = match.group(0)
        else:
            raise ValueError("No JSON found in response")

        response_json = json.loads(cleaned_response)
        title = response_json.get("title", "Untitled")
        description = response_json.get("description", "No description available")
        create_json_file(bucket_name, filename, title, description)
        return {"title": title, "description": description}
    except Exception as e:
        create_json_file(bucket_name, filename, "Error generating", "Error generating", "failure", f"Unexpected error: {e}")
        return {"title": "Error generating title", "description": "Error generating description"}

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        file = request.files.get('form_file')
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_content = file.read()
            upload_to_gcs(file_content, BUCKET_NAME, filename)
    return render_template('index.html', files=list_blobs(BUCKET_NAME))

@app.route('/image_details/<filename>')
def image_details(filename):
    title_description = generate_title_description(BUCKET_NAME, filename)
    return render_template('image_details.html', filename=filename, **title_description)

@app.route('/files/<filename>')
def get_file(filename):
    return send_file(io.BytesIO(download_from_gcs(BUCKET_NAME, filename)), mimetype='image/jpeg')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

