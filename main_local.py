import os
import json
import logging
import base64
from pathlib import Path
from bson import ObjectId
import urllib.parse

import pickle
import itsdangerous
import requests 

from fastapi import Cookie, FastAPI, Request, UploadFile, Body, File, Form, HTTPException, Depends
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware import Middleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.responses import RedirectResponse, HTMLResponse
import msal
from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient
from azure.identity import DefaultAzureCredential, AzureCliCredential, ClientSecretCredential
from azure.core.exceptions import AzureError

from pymongo.errors import DuplicateKeyError
from data.GPTData import GPTData
from data.ModelConfiguration import ModelConfiguration
from gpt_utils import handle_upload_files, create_folders
from azure_openai_utils import generate_response, get_azure_openai_deployments, call_maf
from mongo_service import get_gpt_by_id, create_new_gpt, get_gpts_for_user, update_gpt, delete_gpt, delete_gpts, delete_chat_history, fetch_chat_history, get_usecases, update_gpt_instruction, update_message
from routes.ilama32_routes import router as ilama32_router

import uvicorn
from bson import ObjectId
from dotenv import load_dotenv # For environment variables (recommended)
from standalone_programs.simple_gpt import run_conversation, ticket_conversations, get_conversation
import httpx

delimiter = "```"
load_dotenv()  # Load environment variables from .env file
create_folders()

# Get the secret key from the environment.  DO NOT generate it dynamically!
secret_key = os.getenv("SESSION_SECRET_KEY") 
if not secret_key:
    raise ValueError("SESSION_SECRET_KEY environment variable not set. Create a new secret key")

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
            "https://dharmimax-d5dsbmg8g8a9bud4.southindia-01.azurewebsites.net",
            "https://dharmimax-d5dsbmg8g8a9bud4.southindia-01.azurewebsites.net:443"
          ]

middleware = [
 #Middleware(HTTPSRedirectMiddleware),
#  Middleware(
#      SessionMiddleware, 
#      secret_key=CONFIG["SESSION_SECRET_KEY"], 
#      same_site="lax",  # Important for cross-site requests
#      https_only=True, # Important for security - only set cookies over HTTPS
#      max_age=1*24*60*60  # 1 day session expiry
#  ),
 Middleware(
     CORSMiddleware, 
     allow_origins=origins, 
     allow_credentials=True,  # Allow cookies to be sent
     allow_methods=["*"], 
     allow_headers=["*"]
 )
]

app = FastAPI(middleware=middleware, trusted_hosts=["customgptapp.azurewebsites.net"])

# Include the routers
app.include_router(ilama32_router, prefix="/ilama32", tags=["ilama32"])

# Set up Jinja2 for templating
templates = Jinja2Templates(directory="templates")

# Mount the 'static' directory for static files (CSS, JS, images later)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# --- MSAL Setup ---
# msal_app = msal.ConfidentialClientApplication(
#     CONFIG["CLIENT_ID"],
#     client_credential=CONFIG["CLIENT_SECRET"],
#     authority=CONFIG["AUTHORITY"],
#     token_cache=msal.SerializableTokenCache() # Initialize token_cache
# )

# --- Startup and Shutdown Handlers (For Token Cache Persistence) ---
# @app.on_event("startup")
# async def startup_event():
#  try:
#      with open("token_cache.bin", "rb") as f:
#          cache = pickle.load(f)
#  except (FileNotFoundError, EOFError): # Handle empty file
#      cache = msal.SerializableTokenCache()

#  msal_app.token_cache = cache

# @app.on_event("shutdown")
# async def shutdown_event():
#  with open("token_cache.bin", "wb") as f:
#      pickle.dump(msal_app.token_cache, f)

# @app.middleware("http")
# async def ensure_https_session_cookie(request: Request, call_next):
#     response = await call_next(request)
#     if request.url.scheme == "https":  
#         if "session" in response.cookies:
#             response.set_cookie(
#                 "session",
#                 response.cookies["session"],
#                 secure=True,  # Important!
#                 httponly=True,  # Important!
#                 samesite="lax",
#                 path="/",
#             )
#     return response

# # --- Authentication Routes ---
# @app.get("/login")
# async def login(request: Request):
#     logger.info(f"Request URL {request.url}")
#     redirect_uri = f"https://{request.url.hostname}/getAToken" # Explicitly construct
#     auth_url = msal_app.get_authorization_request_url(
#         CONFIG["SCOPE"],
#         redirect_uri=request.url_for("getAToken"),  # FastAPI's url_for
#         #redirect_uri=redirect_uri,
#         prompt="select_account",  # Force user to select account on each login (optional)
#     )
#     logger.info(f"Redirecting to: {auth_url}")
#     return RedirectResponse(auth_url)

# @app.get("/getAToken", name="getAToken")
# async def auth_response(request: Request):
#  redirect_uri = f"https://{request.url.hostname}/getAToken" # Explicitly construct
#  try:
#      cache = msal.SerializableTokenCache()
#      result = msal_app.acquire_token_by_authorization_code(
#          request.query_params["code"],
#          scopes=CONFIG["SCOPE"],
#          #redirect_uri=redirect_uri
#          redirect_uri=request.url_for("getAToken") # Ensure redirect_uri matches the original request
#      )

#      if "error" in result:
#          logger.error("Authentication error: " + result.get("error"))
#          return templates.TemplateResponse("auth_error.html", {"request": request, "result": result})

#      logger.info(f"Session ID after login: {request.session.get('session_cookie')}")
#      request.session["user"] = result.get("id_token_claims")

#      if cache.has_state_changed:
#          msal_app.token_cache = cache

#      #return RedirectResponse(url=f"https://{request.url.hostname}/")  # Redirect to index page after login
#      return RedirectResponse(url="/")
#  except Exception as e: # Handle exceptions
#      logging.exception("Error in auth_response:" + str(e)) # Log the exception
#      return templates.TemplateResponse("auth_error.html", {"request": request, "result": {"error": str(e)}}) # Show a general error

# # --- Logout Route ---
# @app.get("/logout")
# async def logout(request: Request):
#     request.session.pop("user", None)  # Clear user from session
#     request.session.clear()  # Clear the session
#     #return RedirectResponse(url=f"https://{request.url.hostname}/login")
#     return RedirectResponse(url=f"/login")

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

@app.post("/create_gpt")
async def create_gpt(request: Request, loggedUser: str = Cookie(None), gpt: str = Body(...), files: list[UploadFile] = File(...)):
    try:
        # Parse the JSON string into a dictionary
        gpt = json.loads(gpt)
        loggedUser = getUserName(request, "create_gpt")

        if loggedUser != None and loggedUser != "N/A":
            gpt["user"] = loggedUser
            # Now you can access gpt as a dictionary
            gpt = GPTData(**gpt)  # Validate and create GPTData instance
            logger.info(f"Received GPT data: {gpt}")

            if files != None and len(files) > 0:
                for file in files:
                    logger.info(f"Received files: {file.filename}")

            gpt_id = await create_new_gpt(gpt)
            logger.info(f"GPT created with ID: {gpt_id}")

            file_upload_status = ""

            if gpt.use_rag:
                file_upload_status = await handle_upload_files(gpt, files)
                logger.info(f"RAG Files uploaded successfully: {file_upload_status}")
        
            response = JSONResponse({"message": "GPT created successfully!", "gpt_id": gpt_id, "file_upload_status" : file_upload_status})
        else:
            response = JSONResponse({"error": "Unauthorized user"}, status_code=401)
    except DuplicateKeyError as de:
        logger.error(f"DuplicateKeyError while creating GPT: {de.error}")
        response = JSONResponse({"error": "GPT name already exists."}, status_code=400)
    except HTTPException as he:
        logger.error(f"Error Code: {he}", exc_info=True)
        response = JSONResponse({"error": he.detail}, status_code=500)

    return response

@app.get("/get_gpts")
async def get_gpts(request: Request):
    gpts = []
    loggedUser = getUserName(request, "get_gpts")
    #logger.info(f"User: {json.dumps(request.session.get('user'))}")

    if loggedUser != None and loggedUser != "N/A":
        gpts = await get_gpts_for_user(loggedUser)
        for gpt in gpts:
            gpt["_id"] = str(gpt["_id"]) # Convert ObjectId to string

    return JSONResponse({"gpts": gpts}, status_code=200)

@app.post("/chat/{gpt_id}/{gpt_name}")
async def chat(request: Request, gpt_id: str, gpt_name: str, user_message: str = Form(...), params: str = Form(...), uploadedImage: UploadFile = File(...)):
    if not user_message:
        return JSONResponse({"error": "Missing 'user_message' in request body."}, status_code=400)
    
    try:
        logger.info(f"Chat request received with GPT ID: {gpt_name} \n user message: {user_message} \n params: {params}")
        gpt = await get_gpt_by_id(gpt_id)

         # Parse the JSON string into a dictionary
        model_configuration = json.loads(params)
        model_configuration = ModelConfiguration(**model_configuration)  
        logger.info(f"Received GPT data: {gpt} \n Model Configuration: {model_configuration}")

        if gpt is None:
            return JSONResponse({"error": "GPT not found."}, status_code=404)
        
        streaming_response = False
        response = await generate_response(streaming_response, user_message, model_configuration, gpt, uploadedImage)
    except HTTPException as he:
        logger.error(f"Error while getting response from Model. Details : \n {he.detail}", exc_info=True)
        return JSONResponse({"error": f"Error while getting response from Model. Details : \n {he.detail}"}, status_code=500)

    return JSONResponse({"response": response['model_response'], "total_tokens" : response['total_tokens'] if response['total_tokens'] else 0, "follow_up_questions": response['follow_up_questions'] }, status_code=200)

@app.post("/chat/stream/{gpt_id}/{gpt_name}")
async def chat(request: Request, gpt_id: str, gpt_name: str, user_message: str = Form(...), params: str = Form(...), uploadedImage: UploadFile = File(...)):
    if not user_message:
        return JSONResponse({"error": "Missing 'user_message' in request body."}, status_code=400)
    
    try:
        logger.info(f"Chat request received with GPT ID: {gpt_name} \n user message: {user_message}\n params: {params}")
        gpt = await get_gpt_by_id(gpt_id)

         # Parse the JSON string into a dictionary
        model_configuration = json.loads(params)
        model_configuration = ModelConfiguration(**model_configuration)  
        logger.info(f"Received GPT data: {gpt} \n Model Configuration: {model_configuration}")

        if gpt is None:
            return JSONResponse({"error": "GPT not found."}, status_code=404)
        
        streaming_response = True
        return await generate_response(streaming_response, user_message, model_configuration, gpt, uploadedImage)
    except HTTPException as he:
        logger.error(f"Error while getting response from Model. Details : \n {he.detail}", exc_info=True)
        return JSONResponse({"error": f"Error while getting response from Model. Details : \n {he.detail}"}, status_code=500)

@app.post("/update_instruction/{gpt_id}/{gpt_name}/{usecase_id}")
async def update_instruction(request: Request, gpt_id: str, gpt_name: str, usecase_id: str):
    logger.info(f"Updating instruction for GPT with ID: {gpt_id} Name: {gpt_name} Usecase : {usecase_id}")

    try:
        loggedUser = getUserName(request, "update_instruction")
        if loggedUser != None and loggedUser != "N/A":
            result = await update_gpt_instruction(gpt_id, gpt_name, usecase_id, loggedUser)
            logger.info(f"Instruction updated for GPT: {gpt_name}, result: {result}")

            if result.modified_count == 1:
                response = JSONResponse({"message": "Instruction updated successfully!", "gpt_name": gpt_name}, status_code=200)
            elif result.modified_count == 0:
                response = JSONResponse({"message": "No Changes in the instruction!", "gpt_name": gpt_name}, status_code=200)
            else:
                response = JSONResponse({"error": "GPT not found"}, status_code=404)
        else:
            response = JSONResponse({"error": "Unauthorized user"}, status_code=401)
    except Exception as e:
        logger.error(f"Error occurred while updating instruction: {e}", exc_info=True)
        response = JSONResponse({"error": f"Error Code: {e}"}, status_code=500)

    return response

@app.put("/update_gpt/{gpt_id}/{gpt_name}")
async def modify_gpt(request: Request, gpt_id: str, gpt_name: str, gpt: str = Body(...), files: list[UploadFile] = File(...)):
    logger.info(f"Updating GPT with ID: {gpt_id} Name: {gpt_name}")

    try:
        loggedUser = getUserName(request, "modify_gpt")
        if loggedUser != None and loggedUser != "N/A":
            # Parse the JSON string into a dictionary
            gpt = json.loads(gpt)
            gpt["user"] = loggedUser
        
            # Now you can access gpt as a dictionary
            gpt = GPTData(**gpt)  # Validate and create GPTData instance
            logger.info(f"Received GPT data: {gpt}")

            if files != None and len(files) > 0:
                for file in files:
                    logger.info(f"Received files: {file.filename}")

            result = await update_gpt(gpt_id, gpt_name, gpt)
            logger.info(f"GPT : {gpt.name}, result: {result}, use_rag: {bool(gpt.use_rag)}")

            file_upload_status = ""

            if gpt.use_rag:
                file_upload_status = await handle_upload_files(gpt, files)
                logger.info(f"RAG Files uploaded successfully: {file_upload_status}")
                
            if result.modified_count == 1:
                response = JSONResponse({"message": "GPT created successfully!", "gpt_name": gpt_name, "file_upload_status" : file_upload_status}, status_code=200)
            elif result.modified_count == 0:
                response = JSONResponse({"message": "No Changes in the updated GPT!", "gpt_name": gpt_name, "file_upload_status" : file_upload_status}, status_code=200)
            else:
                response = JSONResponse({"error": "GPT not found"}, status_code=404)
        else:
            response = JSONResponse({"error": "Unauthorized user"}, status_code=401)
    except Exception as e:
        logger.error(f"Error occurred while updating GPT: {e}", exc_info=True)
        response = JSONResponse({"error": f"Error Code: {e}"}, status_code=500)

    return response
    
@app.delete("/delete_gpt/{gpt_id}/{gpt_name}")
async def remove_gpt(gpt_id: str, gpt_name: str):
    logger.info(f"Deleting GPT: {gpt_id} Name: {gpt_name}")

    # Delete the GPT
    gpt_delete_result = await delete_gpt(gpt_id, gpt_name)

    if gpt_delete_result.deleted_count == 1:
        response = JSONResponse({"message": "GPT and Chat history removed successfully.!"})
    else:
        response = JSONResponse({"error": "GPT not found"}, status_code=404)

    return response

@app.delete("/delete_all_gpts")
async def delete_all_gpts(request: Request):
    loggedUser = getUserName(request, "delete_all_gpts")
    if loggedUser != None and loggedUser != "N/A":
        result = await delete_gpts(loggedUser)  # Delete all documents in the collection
        if result.deleted_count > 0:
            response = JSONResponse({"message": "All GPTs deleted successfully!"})
        else:
            response = JSONResponse({"error": "No GPTs found"}, status_code=404)
    else:
        response = JSONResponse({"error": "Unauthorized user"}, status_code=401)
    
    return response
    
@app.get("/chat_history/{gpt_id}/{gpt_name}")
async def get_chat_history(gpt_id: str, gpt_name: str):
    logger.info(f"Fetching chat history for GPT: {gpt_id} Name: {gpt_name}")

    chat_history = await fetch_chat_history(gpt_id, gpt_name, max_tokens_in_conversation)  # Fetch chat history from MongoDB

    # After saving the image, read its contents and encode the image as base64
    # The image URL will be saved in the chat. Use the URL to pick the image from the server
    for chat in chat_history:
        if "chatimages" in chat["content"]:
            uploads_directory = os.path.dirname(__file__)
            imagePath = os.path.join(uploads_directory, chat["content"])
            logger.info(f"Image URL found in chat history {imagePath}")
            #chat["content"] = imagePath

    if chat_history is None or chat_history == []:
        response = JSONResponse({"error": "No Chats in the GPT"}, status_code=404)
    else:
        #reverse the list for linear view or to see proper conversation flow
        response = JSONResponse({"chat_history": chat_history[::-1], "token_count": len(chat_history)}, status_code=200) 

    return response

@app.put("/clear_chat_history/{gpt_id}/{gpt_name}")
async def clear_chat_history(gpt_id: str, gpt_name: str):
    logger.info(f"Clearing chat history for GPT: {gpt_id} Name: {gpt_name}")

    result = await delete_chat_history(gpt_id, gpt_name)  # Delete all documents in the collection

    logger.info(f"Modified count: {result.modified_count}")
    
    if result.modified_count > 0:
        response = JSONResponse({"message": "Cleared conversations successfully!"})
    else:
        response = JSONResponse({"error": "No messages found in GPT"}, status_code=404)
    
    return response
    
@app.get("/usecases/{gpt_id}")
async def fetch_usecases(gpt_id: str):
    try:
        result = await get_usecases(gpt_id)
        logger.info(f"Use cases fetched successfully: {len(result)}")
        response = JSONResponse({"message": "SUCCESS", "usecases": result}, status_code=200)
    except Exception as e:
        logger.error(f"Error occurred while fetching usecases: {e}", exc_info=True)
        response = JSONResponse({"error": f"Error occurred while fetching usecases: {e}"}, status_code=500)
    
    return response
        
@app.get("/logs")
async def get_logs():
    """Fetch the contents of the app.log file."""
    log_file_path = "logs/app.log" # Update with your actual log file path

    if not os.path.exists(log_file_path):
        raise HTTPException(status_code=404, detail="Log file not found")

    with open(log_file_path, "r") as f:
        log_content = f.read()

    logger.info(log_filename)  

    return {"log_content": log_content}

@app.get("/deployedModels")
async def getDeployedModelsFromAzure():
    """Fetch the open ai models deployed in azure open ai portal."""
    try:
        deployments = getDeployments2()
        logger.info(f"Deployments fetched successfully: {len(deployments)}")
        if deployments is None:
            response = JSONResponse({"message": "No deployments found"}, status_code=200)
        else:
            response = JSONResponse({"message": "SUCCESS", "model_deployments": deployments}, status_code=200)
    except Exception as e:
        logger.error(f"Error occurred while fetching deployments: {e}", exc_info=True)
        response = JSONResponse({"error": f"Error occurred while fetching deployments: {e}"}, status_code=500)
    return response

@app.get("/get_image/{imagePath}",

    # Set what the media type will be in the autogenerated OpenAPI specification.
    # fastapi.tiangolo.com/advanced/additional-responses/#additional-media-types-for-the-main-response
    responses = {
        200: {
            "content": {"image/jpeg": {}}
        }
    },

    # Prevent FastAPI from adding "application/json" as an additional
    # response media type in the autogenerated OpenAPI specification.
    # https://github.com/tiangolo/fastapi/issues/3258
    response_class=StreamingResponse
)

async def get_image(imagePath: str):
    try:
        logger.info("Image path : " + imagePath)
        
        image_path = urllib.parse.unquote(imagePath)
        image_path = Path(imagePath)

        if not image_path.is_file():
            logger.info(f"Image not found in path: {imagePath}")
            return JSONResponse({"error": "Image not found on the server"}, status_code=404)
        
        logger.info(f"Fetching image from path: {imagePath}")

        fullPath = os.path.join(os.path.dirname(__file__), image_path)
        logger.info(f"Full path of image : {fullPath}")

        with open(fullPath, "rb") as img_file:
            logger.info("Reading image bytes")
            image_bytes = img_file.read()
            logger.info(f"Length of image : {len(image_bytes)}")

            # Convert bytes to base64 string
            base64_string = base64.b64encode(image_bytes).decode('utf-8')
            
            # Create the data URI
            data_uri = f"data:image/jpeg;base64,{base64_string}"

            # media_type here sets the media type of the actual response sent to the client.
            #return StreamingResponse(io.BytesIO(image_bytes), media_type="image/jpeg")
            response = JSONResponse(content={"image": data_uri}, status_code=200)
    except Exception as e:
        logger.error(f"Error occurred while fetching image: {e}", exc_info=True)
        response = JSONResponse({"error": f"Error occurred while fetching image: {e}"}, status_code=500)
    
    return response
    
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

def getDeployments2():
    deployed_model_names = []

    # Replace with your subscription ID, client ID, client secret, and tenant ID
    subscription_id = os.getenv("SUBSCRIPTION_ID")
    resource_group = os.getenv("RESOURCE_GROUP_NAME")
    openai_account = os.getenv("OPENAI_ACCOUNT_NAME")
    
    # Your MSAL app credentials (Client ID, Client Secret, Tenant ID)
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET_VALUE")
    tenant_id = os.getenv("TENANT_ID")
    
    try:
        # Use the token with Azure SDK's client
        credential = ClientSecretCredential(tenant_id, client_id, client_secret)
        
        # Create Cognitive Services management client with the token
        client = CognitiveServicesManagementClient(credential, subscription_id)
        
        logger.info("Starting to fetch deployments...")

        # Get all deployments in the subscription
        deployments = client.deployments.list(resource_group_name=resource_group, account_name=openai_account)

        if not deployments:
            logger.warning("No deployments found.")
        else:
            for deployment in deployments:
                logger.info(f"Deployment Name: {deployment.name}")
                deployed_model_names.append(deployment.name)

    except AzureError as e:
        logger.error(f"AzureError occurred: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error occurred: {str(e)}")

    return deployed_model_names

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

def getUserName(request: Request, callee: str):
    # loggedUser = "N/A"
    # user = getSessionUser(request)

    # if user is None:
    #     loggedUser = request.cookies.get("loggedUser")
    #     logger.info("Fetch => loggedUser from cookie")
    # else:
    #     loggedUser = user["name"]
    #     logger.info(f"Fetch => loggedUser from session")

    # logger.info(f"Calling Method : {callee} User: {loggedUser}") 
    #return loggedUser if loggedUser else "N/A" 
    #return loggedUser if loggedUser else "Dharmeshwaran S"
    return "Dharmeshwaran S"

# if __name__ == "__main__":
#    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

if __name__ == "__main__":
    #getDeployments()
    port = int(os.getenv("PORT", 8000))  # Use the environment variable or default to 8000
    uvicorn.run(app, host="0.0.0.0", port=port)