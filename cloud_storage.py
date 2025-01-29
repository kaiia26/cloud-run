from google.cloud import storage

BUCKET_NAME = 'flask-images'

def upload_to_gcs(file, bucket_name, filename):
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(filename)
    blob.upload_from_file(file)
    return blob.public_url

def download_from_gcs(bucket_name, filename, download_path=None):
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(filename)
    content = blob.download_as_bytes()
    return content

def list_blobs(bucket_name):
    """List all blobs in the given bucket."""
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blobs = bucket.list_blobs()  # This returns a generator
    return [blob.name for blob in blobs]