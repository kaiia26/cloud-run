from google.cloud import storage
from config import BUCKET_NAME  # Import BUCKET_NAME from config.py
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def upload_to_gcs(file, bucket_name, filename, storage_client=None, content_type=None):
    """Uploads a file to Google Cloud Storage.

    Args:
        file (bytes or str): The content of the file to upload.
        bucket_name (str): The name of the GCS bucket.
        filename (str): The name of the file in GCS.
        storage_client (google.cloud.storage.Client, optional): An existing storage client. Defaults to None.
        content_type (str, optional): The content type of the file. Defaults to None.

    Returns:
        str: The public URL of the uploaded file.
    """
    if storage_client is None:
        client = storage.Client()
    else:
        client = storage_client
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(filename)
    blob.upload_from_string(file, content_type=content_type)
    logger.info(f"File {filename} uploaded to {bucket_name}.")
    return blob.public_url

def download_from_gcs(bucket_name, filename, download_path=None):
    """Downloads a file from Google Cloud Storage.

    Args:
        bucket_name (str): The name of the GCS bucket.
        filename (str): The name of the file in GCS.
        download_path (str, optional): The path to save the file locally. Defaults to None.

    Returns:
        bytes: The content of the downloaded file.
    """
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(filename)
    content = blob.download_as_string()
    logger.info(f"File {filename} downloaded from {bucket_name}.")
    
    if download_path:
        with open(download_path, 'wb') as f:
            f.write(content)
            logger.info(f"File {filename} saved locally to {download_path}.")
    return content

def list_blobs(bucket_name):
    """List all blobs in the given bucket.

    Args:
        bucket_name (str): The name of the GCS bucket.

    Returns:
        list: A list of blob names.
    """
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blobs = bucket.list_blobs()  # This returns a generator
    logger.info(f"Listed blobs in {bucket_name}.")
    return [blob.name for blob in blobs]

def blob_exists(bucket_name, blob_name):
    """Checks if a blob (file) exists in the given bucket.

    Args:
        bucket_name (str): The name of the GCS bucket.
        blob_name (str): The name of the blob (file) to check.

    Returns:
        bool: True if the blob exists, False otherwise.
    """
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    logger.info(f"Checking if blob {blob_name} exists in {bucket_name}.")
    return blob.exists()