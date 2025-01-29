from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from werkzeug.utils import secure_filename
import os, io
from cloud_storage import upload_to_gcs, download_from_gcs, list_blobs

app = Flask(__name__)

UPLOAD_FOLDER = './files'
ALLOWED_EXTENSIONS = {'jpg', 'jpeg'}
app.secret_key = 'supersecretkey'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
BUCKET_NAME = 'flask-images'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'form_file' not in request.files:
            flash('No file part')
            return redirect(request.url)

        file = request.files['form_file']

        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            upload_to_gcs(file, BUCKET_NAME, filename)
            flash('File successfully uploaded')
            return redirect(url_for('upload_file'))

        flash('File type not allowed')
        return redirect(request.url)

    # Get the list of uploaded files in the cloud storage
    uploaded_files = list_blobs(BUCKET_NAME)
    return render_template('index.html', files=uploaded_files)

@app.route('/files/<filename>')
def get_file(filename):
    content = download_from_gcs(BUCKET_NAME, filename, download_path=None)
    return send_file(io.BytesIO(content), mimetype='image/jpeg')

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5000)