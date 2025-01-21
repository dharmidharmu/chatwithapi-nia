import os
import itsdangerous
import json
from dotenv import load_dotenv # For environment variables (recommended)

load_dotenv()  # Load environment variables from .env file

def debug_session():
 session_cookie_value = "<cookie-data>"

 if session_cookie_value:
     try:
         # 1. Create a signer with the same secret key
         signer = itsdangerous.TimestampSigner(os.getenv("SESSION_SECRET_KEY"))

         # 2. Unsign and decode the cookie value
         decoded_data = signer.unsign(session_cookie_value).decode("utf-8")

         # 3. Split the data (it's timestamp:data)
         timestamp_str, data = decoded_data.split(":", 1)

         # 4. Convert the data from JSON back to a Python dictionary
         session_data = json.loads(data)

         print(f"session data : {session_data} \n timestamp: {timestamp_str}")

     except itsdangerous.BadSignature as bs:
         print(f"error Invalid session signature : {bs}") # Signature mismatch (tampering?)
     except Exception as e:
         print(f"error - Error decoding session data: {str(e)}") # Other errors

 else:
     print(f"No session cookie found.")


debug_session()