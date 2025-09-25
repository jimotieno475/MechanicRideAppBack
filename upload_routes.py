import os
from flask import Blueprint, request, jsonify
from firebase_admin import storage
import uuid

# Define a Flask Blueprint for the upload routes
upload_routes = Blueprint('upload_routes', __name__)

@upload_routes.route('/upload-image', methods=['POST'])
def upload_image():
    """
    Handles image uploads to the temporary storage folder in Firebase.
    """
    # Check if a file was uploaded in the request
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400

    file = request.files['file']

    # Check if the file is empty
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # Ensure the upload folder exists and get the bucket
    bucket = storage.bucket()
    
    # Generate a unique filename using a UUID to prevent collisions
    filename = f"temp_uploads/{uuid.uuid4()}_{file.filename}"
    blob = bucket.blob(filename)
    
    try:
        # Upload the file's content directly to the blob
        blob.upload_from_file(file)

        # The public URL is generated after the upload is complete
        public_url = blob.public_url

        print(f"✅ File uploaded successfully: {public_url}")
        return jsonify({"url": public_url}), 200

    except Exception as e:
        print(f"Error during file upload: {e}")
        return jsonify({"error": "Failed to upload file to Firebase"}), 500
