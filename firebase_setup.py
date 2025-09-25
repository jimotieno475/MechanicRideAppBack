import firebase_admin
from firebase_admin import credentials, storage

# Path to your downloaded service account key
cred = credentials.Certificate("serviceAccountKey.json")

# Initialize the Firebase app with your credentials and storage bucket URL
# Replace 'YOUR_FIREBASE_STORAGE_BUCKET_URL' with your actual bucket URL
firebase_app = firebase_admin.initialize_app(cred, {
    'storageBucket': 'mech-mobile-a15c7.appspot.com'
})