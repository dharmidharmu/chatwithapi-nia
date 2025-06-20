import os
import json
import msal
import pickle
import logging

from fastapi import Cookie, FastAPI, Request, Security
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware import Middleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.responses import RedirectResponse, HTMLResponse
from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient
from azure.identity import DefaultAzureCredential, AzureCliCredential, ClientSecretCredential
from azure.core.exceptions import AzureError

from app_config import CLIENT_ID, APP_SCOPE
from auth_msal import verify_jwt_token
from gpt_utils import create_folders
from azure_openai_utils import call_maf
from routes.ilama32_routes import router as ilama32_router
from routes.gpt_routes_secured import router as gpt_router_secured
from routes.gpt_routes_unsecured import router as gpt_router_unsecured
from auth_config import azure_scheme

import uvicorn
from dotenv import load_dotenv # For environment variables (recommended)
from standalone_programs.simple_gpt import get_conversation

delimiter = "```"
load_dotenv()  # Load environment variables from .env file
create_folders()

# Get the secret key from the environment.  DO NOT generate it dynamically!
secret_key = os.getenv("SESSION_SECRET_KEY") 
if not secret_key:
    raise ValueError("SESSION_SECRET_KEY environment variable not set. Create a new secret key")

# Get environment variable to determine if we're in development or production
is_dev_environment = os.getenv("ENVIRONMENT", "development").lower() == "development"

# Configuration (from .env or equivalent)
CONFIG = {
 "AUTHORITY": f"https://login.microsoftonline.com/{os.getenv('TENANT_ID')}",
 "CLIENT_ID": os.getenv("CLIENT_ID"),
 "CLIENT_SECRET": os.getenv("CLIENT_SECRET_VALUE"),
 "SCOPE": ["User.ReadBasic.All"],  # Scope as a list
 "REDIRECT_PATH":  "/getAToken",
 "SESSION_SECRET_KEY": secret_key,  # Important!
 "ENDPOINT": os.getenv("ENDPOINT"),  # Downstream API endpoint
}

# Get logger
# Logging Configuration
logs_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(logs_dir, exist_ok=True)  # Create logs directory if it doesn't exist

log_filename = os.path.join(logs_dir, "app.log") 
logging.basicConfig(
    filename=log_filename,  
    level="INFO", 
    format="%(asctime)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s"
)

# Disable the change detected log
class IgnoreChangeDeductedFilter(logging.Filter):
    def filter(self, record):
        return "change detected" not in record.getMessage().lower()
 
logger = logging.getLogger()
logger.addFilter(IgnoreChangeDeductedFilter())

# FastAPI Configuration
# CORS configuration (update with your frontend origin)
origins = [
            "http://localhost", 
            "http://localhost:8000", 
            "http://localhost:3000", 
            "http://localhost:5173", 
            "http://127.0.0.1:5173", 
            "http://localhost:5174", 
            "http://127.0.0.1:5174",
            "https://login.microsoftonline.com",
            "https://customgptapp.azurewebsites.net", 
            "https://customgptapp.azurewebsites.net:443",
            "https://customgptapp2.azurewebsites.net", 
            "https://customgptapp2.azurewebsites.net:443",
            "https://niaapp.azurewebsites.net",
            "https://niaapp.azurewebsites.net:443"
            "https://niaapp2.azurewebsites.net",
            "https://niaapp2.azurewebsites.net:443"
          ]

middleware = [
#  Middleware(HTTPSRedirectMiddleware),
 Middleware(
     SessionMiddleware, 
     secret_key=CONFIG["SESSION_SECRET_KEY"], 
     same_site="lax",  # Important for cross-site requests
     https_only=True,  # Only require HTTPS in production, # Important for security - only set cookies over HTTPS
     max_age=1*24*60*60  # 1 day session expiry
 ),
 Middleware(
     CORSMiddleware, 
     allow_origins=origins, 
     allow_credentials=True,  # Allow cookies to be sent
     allow_methods=["*"], 
     allow_headers=["*"]
 )
]

app = FastAPI(
    swagger_ui_oauth2_redirect_url='/oauth2-redirect',
    swagger_ui_init_oauth={
        'usePkceWithAuthorizationCodeGrant': True,
        'clientId': CLIENT_ID,
        'scopes': 'api://' + APP_SCOPE + '/access_as_user',
    },
    middleware=middleware, 
    trusted_hosts=["customgptapp.azurewebsites.net"]
    )

# Include the routers
app.include_router(ilama32_router, prefix="/ilama32", tags=["ilama32"])
app.include_router(gpt_router_secured, dependencies=[Security(azure_scheme, scopes=["access_as_user"])])
app.include_router(gpt_router_unsecured, prefix="/backend", tags=["backend"])
#app.include_router(gpt_router, dependencies=[Security(verify_jwt_token, scopes=["access_as_user"])])

# Set up Jinja2 for templating
templates = Jinja2Templates(directory="templates")

# Mount the 'static' directory for static files (CSS, JS, images later)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# --- MSAL Setup ---
msal_app = msal.ConfidentialClientApplication(
    CONFIG["CLIENT_ID"],
    client_credential=CONFIG["CLIENT_SECRET"],
    authority=CONFIG["AUTHORITY"],
    token_cache=msal.SerializableTokenCache() # Initialize token_cache
)

# --- Startup and Shutdown Handlers (For Token Cache Persistence) ---
@app.on_event("startup")
async def startup_event():
 try:
     with open("token_cache.bin", "rb") as f:
         cache = pickle.load(f)
 except (FileNotFoundError, EOFError): # Handle empty file
     cache = msal.SerializableTokenCache()

 msal_app.token_cache = cache

@app.on_event("shutdown")
async def shutdown_event():
 with open("token_cache.bin", "wb") as f:
     pickle.dump(msal_app.token_cache, f)

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    # try:
    #     # Add token to headers BEFORE processing the request
    #     if hasattr(request, "session") and "access_token" in request.session:
    #         token = request.session["access_token"]
    #         # FastAPI/Starlette Headers are immutable, so we need to modify properly
    #         # Create a modified scope with the new header
    #         auth_header = f"Bearer {token}"
    #         request.scope["headers"] = [
    #             *request.scope["headers"],
    #             (b"authorization", auth_header.encode())
    #         ]
    #         logger.info(f"Added authorization header: {auth_header}")
    # except (AttributeError, AssertionError) as e:
    #     logger.warning(f"Session access error: {str(e)}")
    
    # Now process the request with the added header
    response = await call_next(request)
    
    # Handle cookies if needed
    if request.url.scheme == "https":
        response.set_cookie(
            "session",
            response.cookies["session"],
            secure=True,
            httponly=True,
            samesite="lax",
            path="/",
        )
    
    return response

# --- Authentication Routes ---
@app.get("/login")
async def login(request: Request):
    logger.info(f"Request URL {request.url}")
    redirect_uri = f"https://{request.url.hostname}/getAToken" # Explicitly construct
    auth_url = msal_app.get_authorization_request_url(
        CONFIG["SCOPE"],
        redirect_uri=request.url_for("getAToken"),  # FastAPI's url_for
        #redirect_uri=redirect_uri,
        prompt="select_account",  # Force user to select account on each login (optional)
    )
    logger.info(f"Redirecting to: {auth_url}")
    return RedirectResponse(auth_url)

@app.get("/getAToken", name="getAToken")
async def auth_response(request: Request):
 redirect_uri = f"https://{request.url.hostname}/getAToken" # Explicitly construct
 try:
     cache = msal.SerializableTokenCache()
     result = msal_app.acquire_token_by_authorization_code(
         request.query_params["code"],
         scopes=CONFIG["SCOPE"],
         #redirect_uri=redirect_uri
         redirect_uri=request.url_for("getAToken") # Ensure redirect_uri matches the original request
     )

     if "error" in result:
         logger.error("Authentication error: " + result.get("error"))
         return templates.TemplateResponse("auth_error.html", {"request": request, "result": result})

     logger.info(f"Session ID after login: {request.session.get('session_cookie')}")
     request.session["user"] = result.get("id_token_claims")
     request.session["access_token"] = result.get("access_token")
     #logger.info(f"User session: {request.session['user']}")
     #request.session["session"] = result.get("access_token")  # Store access token in session
     #logger.info(f"Access Token: {request.session['session']}")
     
     logger.info(f"Request Headers: {request.headers}")


     if cache.has_state_changed:
         msal_app.token_cache = cache

     #return RedirectResponse(url=f"https://{request.url.hostname}/")  # Redirect to index page after login
     return RedirectResponse(url="/")  # Redirect to backend page after login
 except Exception as e: # Handle exceptions
     logging.exception("Error in auth_response:" + str(e)) # Log the exception
     return templates.TemplateResponse("auth_error.html", {"request": request, "result": {"error": str(e)}}) # Show a general error

# --- Logout Route ---
@app.get("/logout")
async def logout(request: Request):
    request.session.pop("user", None)  # Clear user from session
    request.session.clear()  # Clear the session
    #return RedirectResponse(url=f"https://{request.url.hostname}/login")
    return RedirectResponse(url=f"/login")

# Conversation History
conversations = []
use_cases = []
max_tokens_in_conversation = 10 # To be implemented
max_conversations_to_consider = 10

# --- Main Application Routes ---

#http://localhost:8000/maf/ticket_id
# @app.get("/maf/{ticketNumber}", response_class=HTMLResponse)
# async def maf_index(request: Request, ticketNumber: str):
#     user = getSessionUser(request)
#     if user:
#         model_output = run_conversation(ticketNumber)

#         message = {"gpt_id" : "67406e4c3c9ee64a13c74f83",
#                     "gpt_name" : "plain_gpt3_5_turbo",
#                     "role": "assistant",
#                     "content": model_output
#         }

#         logger.info(f"Message: {message}")
#         logger.info(f"model_output: {model_output}")

#         if "No conversation found for the given ticket number. Please try again with a valid ticket" not in message["content"]:
#             ticketSummary = json.loads(message["content"])
#             isErrorResponse = False
#         else:
#             ticketSummary = message["content"]
#             isErrorResponse = True

#         response = templates.TemplateResponse("summary.html", {
#             "request": request, 
#             "ticketSummary": ticketSummary,
#             "ticketId" : ticketNumber,
#             "ticket_conversation": get_conversation(ticketNumber),
#             "user": user,
#             "isErrorResponse": isErrorResponse,
#             "config": CONFIG  # Pass the CONFIG dictionary
#         })

#         response.set_cookie(key="loggedUser", value=user["name"], max_age=1800)  # expires in 30 minutes
#     else:
#         response = RedirectResponse(url="/login")
    
#     return response

def getSessionUser(request:Request):
    #return getSessionUser(request)
    return "Dharmeshwaran S"

#http://localhost:8000/maf/?TID=ticket_id
@app.get("/maf/", response_class=HTMLResponse)
async def maf_index_1(request: Request, TID: str):
    user = getSessionUser(request)
    if user:
        model_output = call_maf(TID)

        message = {"gpt_id" : "67406e4c3c9ee64a13c74f83",
                    "gpt_name" : "plain_gpt3_5_turbo",
                    "role": "assistant",
                    "content": model_output
        }

        logger.info(f"Message: {message}")
        logger.info(f"model_output: {model_output}")

        if "No conversation found for the given ticket number. Please try again with a valid ticket" not in message["content"]:
            ticketSummary = json.loads(message["content"])
            isErrorResponse = False
        else:
            ticketSummary = message["content"]
            isErrorResponse = True

        response = templates.TemplateResponse("summary.html", {
            "request": request, 
            "ticketSummary": ticketSummary,
            "ticketId" : TID,
            "ticket_conversation": get_conversation(TID),
            "user": user,
            "isErrorResponse": isErrorResponse,
            "config": CONFIG  # Pass the CONFIG dictionary
        })

        response.set_cookie(key="loggedUser", value=getSessionUser(request), max_age=1800)  # expires in 30 minutes
    else:
       # response = RedirectResponse(url="/login")
        response = RedirectResponse(url="/")
    
    return response

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    user = getSessionUser(request)
    if user:
        response = templates.TemplateResponse("index.html", {
            "request": request, 
            "user": user,
            "config": CONFIG  # Pass the CONFIG dictionary
        })
        response.set_cookie(key="loggedUser", value=getSessionUser(request), max_age=1800)  # expires in 30 minutes
    else:
        #response = RedirectResponse(url="/login")
        response = RedirectResponse(url="/")
    
    return response

@app.get('/favicon.ico')
async def favicon():
    file_name = 'favicon.ico'
    file_path = './static/' + file_name
    return FileResponse(path=file_path, headers={'mimetype': 'image/vnd.microsoft.icon'})


    
# @app.get("/userProfile")
# async def getUserProfile(request: Request):
#  try:
#      accounts = msal_app.get_accounts()
#      if accounts:
#          token = msal_app.acquire_token_silent(
#              CONFIG["SCOPE"],
#              account=accounts[0],  # Use the first logged-in account
#          )
#      else:
#          # If no accounts are found, redirect to login
#          return RedirectResponse(url="/login")

#      if "error" in token: # Handle error
#          logging.error(f"Error acquiring token silently: {token.get('error')}, {token.get('error_description')}")  # Log details
#          # You might want to handle different error types specifically, like interaction_required
#          return RedirectResponse(url="/login")

#      api_result = requests.get(
#          CONFIG["ENDPOINT"],
#          headers={"Authorization": "Bearer " + token["access_token"]},
#          timeout=30,
#      ).json()
     
#      return templates.TemplateResponse("display.html", {"request": request, "data": api_result})

#  except Exception as e:  # Handle broader exceptions
#      logging.exception(f"Error in call_downstream_api: {str(e)}")
#      return templates.TemplateResponse("auth_error.html", {"request": request, "error": str(e)})  # Render a general error page

def getDeployments():

    deployed_model_names = []

     # Replace with your subscription ID
    subscription_id = os.getenv("SUBSCRIPTION_ID")
    resource_group = os.getenv("RESOURCE_GROUP_NAME")
    openai_account = os.getenv("OPENAI_ACCOUNT_NAME")

    # Use ManagedIdentityCredential for authentication (managed identities, App Service, etc.)    
    credential = AzureCliCredential()

    # Create a Cognitive Services management client
    client = CognitiveServicesManagementClient(credential, subscription_id)

    # Get all deployments in the subscription
    deployments = client.deployments.list(resource_group_name=resource_group, account_name=openai_account)  # Or list_by_resource_group() for a specific resource group

    for deployment in deployments:
        logger.info(f"Deployment Name: {deployment.name}")
        deployed_model_names.append(deployment.name)
        #print(f"Deployment {deployment.as_dict()}")

    return deployed_model_names

# MSAL Authentication: Acquire token for Azure Management API
# def get_access_token(msal_app):
#     # Acquire token for Azure Management API (scopes)
#     result = msal_app.acquire_token_for_client(scopes=["https://management.azure.com/.default"])
    
#     if "access_token" in result:
#         logger.info("Successfully acquired access token.")
#         return result["access_token"]
#     else:
#         logger.error("Failed to acquire access token.")
#         raise Exception("Authentication failed: " + result.get("error_description", "Unknown error"))



# def print_session_values(request: Request, callee: str):
#     session = request.session
    
#     logger.info(f"Calling Method : {callee}. Session Information:\n")
#     for key, value in session.items():
#         logger.info(f"{key}: {value}\n")

#     session = request.session.get("session")
#     logger.info("session_cookie Information:\n")
#     if session != None:
#         for key, value in session.items():
#             logger.info(f"{key}: {value}\n")

#     session = request.session.get("_session")
#     logger.info("_session Information:\n")
#     if session != None:
#         for key, value in session.items():
#             logger.info(f"{key}: {value}\n")



# if __name__ == "__main__":
#    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

if __name__ == "__main__":
    #getDeployments()
    port = int(os.getenv("PORT", 8000))  # Use the environment variable or default to 8000
    uvicorn.run(app, host="localhost", port=port)