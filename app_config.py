import os
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

load_dotenv()  # Load environment variables from .env file

APP_SCOPE = os.getenv("APP_SCOPE")
AUTHORITY= os.getenv("AUTHORITY")

# Application (client) ID of app registration
CLIENT_ID = os.getenv("CLIENT_ID")
# Application's generated client secret: never check this into source control!
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
TENANT_ID = os.getenv("TENANT_ID")

# Azure Blob Storage - Used for storing image uploads
UPLOAD_FOLDER = "uploads"
AZURE_BLOB_STORAGE_CONNECTION_URL=os.getenv("BLOB_STORAGE_CONNECTION_STRING")
AZURE_BLOB_STORAGE_CONTAINER=os.getenv("BLOB_STORAGE_CONTAINER_NAME")
AZURE_BLOB_STORAGE_ACCOUNT_NAME=os.getenv("BLOB_STORAGE_ACCOUNT_NAME")
AZURE_BLOB_STORAGE_ACCESS_KEY=os.getenv("BLOB_STORAGE_ACCESS_KEY")
RAG_DOCUMENTS_FOLDER = os.path.join(UPLOAD_FOLDER, "ragdocuments")
 
REDIRECT_PATH = "/getAToken"  # Used for forming an absolute URL to your redirect URI.

ENDPOINT = 'https://graph.microsoft.com/v1.0/me'  
SCOPE = ["User.Read"]

blob_service_client = BlobServiceClient(f"https://{AZURE_BLOB_STORAGE_ACCOUNT_NAME}.blob.core.windows.net",
    credential=AZURE_BLOB_STORAGE_ACCESS_KEY
)

# Tells the Flask-session extension to store sessions in the filesystem
SESSION_TYPE = "filesystem"