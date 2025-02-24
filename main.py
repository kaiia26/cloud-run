from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session
from werkzeug.utils import secure_filename
import os, io
from cloud_storage import upload_to_gcs, download_from_gcs, list_blobs, blob_exists
from gemini_service import generate_title_description
from config import BUCKET_NAME
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
from google.auth.transport import requests
import json
from google.cloud import secretmanager, storage
import google.oauth2.credentials
import logging

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

UPLOAD_FOLDER = './files'
ALLOWED_EXTENSIONS = {'jpg', 'jpeg'}
app.secret_key = 'supersecretkey'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def access_secret_version(secret_id, version_id='latest'):
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/project-1-kaia-perez-hvala/secrets/{secret_id}/versions/{version_id}"
    response = client.access_secret_version(name=name)
    payload = response.payload.data.decode('UTF-8')
    return payload

# Load OAuth client secrets from Google Secret Manager
try:
    CLIENT_SECRETS_CONTENT = access_secret_version("image_upload_client")
    CLIENT_SECRETS = json.loads(CLIENT_SECRETS_CONTENT)
except Exception as e:
    logger.error(f"Error loading client secrets: {e}")
    raise

SCOPES = ['https://www.googleapis.com/auth/devstorage.full_control'] 
REDIRECT_URI = 'https://8080-cs-901945017769-default.cs-us-east1-yeah.cloudshell.dev/oauth2/callback'

flow = Flow.from_client_config(
    CLIENT_SECRETS,
    scopes=SCOPES,
    redirect_uri=REDIRECT_URI
)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if 'credentials' not in session:
        flash('Please authenticate first')
        return redirect(url_for('authorize'))

    if request.method == 'POST':
        if 'form_file' not in request.files:
            flash('No file part')
            return redirect(request.url), 400

        file = request.files['form_file']

        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)

             # Read the file content:
            file_content = file.read()  # Read the file content as bytes

            # Upload the image to GCS
            # Create a storage client with the user's credentials
            credentials = google.oauth2.credentials.Credentials(**session['credentials'])
            logger.info(f"Credentials in session: {session['credentials']}")  # Log credentials
            logger.info(f"Credential: {credentials}")
            storage_client = storage.Client(credentials=credentials)
            upload_to_gcs(file_content, BUCKET_NAME, filename, storage_client)
            generate_title_description(BUCKET_NAME, filename)

            flash('File successfully uploaded')

            uploaded_files = list_blobs(BUCKET_NAME)
            return render_template('index.html', files=uploaded_files)

        flash('File type not allowed')
        return redirect(request.url)

    # Get the list of uploaded files in the cloud storage
    uploaded_files = list_blobs(BUCKET_NAME)
    return render_template('index.html', files=uploaded_files)

@app.route('/image_details/<filename>')
def image_details(filename):
    """Displays the title and description of an image."""
    if 'credentials' not in session:
        flash('Please authenticate first')
        return redirect(url_for('authorize'))

    # Construct the expected JSON filename
    json_filename = filename.rsplit(".", 1)[0].replace(" ", "_") + ".json"

    # Check if the JSON file exists in GCS
    if not blob_exists(BUCKET_NAME, json_filename):
        # If the JSON doesn't exist, set default values
        title = "Title not generated yet"
        description = "Description not generated yet"
    else:
        # If the JSON file exists, download and parse it
        try:
            json_content = download_from_gcs(BUCKET_NAME, json_filename)
            metadata = json.loads(json_content)
            # Get the title and description from the JSON, with defaults if missing
            title = metadata.get("title", "Title not found")
            description = metadata.get("description", "Description not found")
        except json.JSONDecodeError:
            # Handle JSON decoding errors
            logger.error(f"Error decoding JSON for {json_filename}")
            title = "Error loading title"
            description = "Error loading description"

    # Now, title and description are defined, so it's safe to render
    return render_template('image_details.html', filename=filename, title=title, description=description)


@app.route('/files/<filename>')
def get_file(filename):
    """Fetch and send the image from GCS."""
    content = download_from_gcs(BUCKET_NAME, filename, download_path=None)
    return send_file(io.BytesIO(content), mimetype='image/jpeg')

@app.route('/login')
def login():
    if 'credentials' in session:
        return redirect(url_for('upload_file'))
    else:
        return redirect(url_for('authorize'))


os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

@app.route('/authorize')
def authorize():
    authorization_url, state = flow.authorization_url()
    session['state'] = state
    return redirect(authorization_url)

@app.route('/oauth2/callback')
def oauth2_callback():
    try:
        # Check if the state matches (prevent CSRF)
        if request.args.get('state') != session.get('state'):
            logger.error("State mismatch detected during authentication.")
            flash('Authentication failed: Invalid state. Please try again.')
            session.clear() # Clear any existing session data
            return redirect(url_for('authorize'))

        flow.fetch_token(authorization_response=request.url)
        credentials = flow.credentials
        session['credentials'] = credentials_to_dict(credentials)

        #remove state
        session.pop('state', None)

        return redirect(url_for('upload_file'))
    except Exception as e:
        logger.error(f"Error during OAuth2 callback: {e}")
        flash('An error occurred during authentication.')
        session.clear() # Clear any existing session data
        return redirect(url_for('authorize'))


def credentials_to_dict(credentials):
    return {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }

def get_authenticated_session():
    if 'credentials' not in session:
        return redirect(url_for('authorize'))
    credentials = google.oauth2.credentials.Credentials(
        **session['credentials'])
    session = requests.AuthorizedSession(credentials)
    return session

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))  
    app.run(debug=True, host='0.0.0.0', port=port)


