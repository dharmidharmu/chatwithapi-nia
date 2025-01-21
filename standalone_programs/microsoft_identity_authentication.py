# import os
# import logging
# from starlette.middleware.sessions import SessionMiddleware
# from fastapi import FastAPI, Request, Depends, HTTPException
# from fastapi.responses import HTMLResponse, RedirectResponse
# from fastapi.templating import Jinja2Templates
# from fastapi.staticfiles import StaticFiles  # For serving static files (if needed)
# import msal
# from dotenv import load_dotenv
# import pickle
# import requests
# import uvicorn
# import secrets

# # Generate a random URL-safe text string containing 32 bytes
# secret_key = secrets.token_urlsafe(32)

# # Store in an environment variable (best practice)
# os.environ["SESSION_SECRET_KEY"] = secret_key

# load_dotenv()  # Load environment variables

# # Configuration (from .env or equivalent)
# CONFIG = {
#  "AUTHORITY": f"https://login.microsoftonline.com/{os.getenv('TENANT_ID')}",
#  "CLIENT_ID": os.getenv("CLIENT_ID"),
#  "CLIENT_SECRET": os.getenv("CLIENT_SECRET_VALUE"),
#  "SCOPE": ["User.ReadBasic.All"],  # Scope as a list
#  "REDIRECT_PATH":  "/getAToken",
#  "SESSION_SECRET_KEY": os.getenv("SESSION_SECRET_KEY"),  # Important!
#  "ENDPOINT": os.getenv("ENDPOINT"),  # Downstream API endpoint
# }

# # --- FastAPI Setup ---
# app = FastAPI()
# app.add_middleware(SessionMiddleware, secret_key=CONFIG["SESSION_SECRET_KEY"])

# templates = Jinja2Templates(directory="templates")  # Assuming you have a templates directory
# app.mount("/static", StaticFiles(directory="static"), name="static") # Mount static directory

# # --- MSAL Setup ---
# msal_app = msal.ConfidentialClientApplication(
#  CONFIG["CLIENT_ID"],
#  client_credential=CONFIG["CLIENT_SECRET"],
#  authority=CONFIG["AUTHORITY"],
#  token_cache=msal.SerializableTokenCache() # Initialize token_cache
# )

# # --- Startup and Shutdown Handlers (For Token Cache Persistence) ---

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


# # --- Authentication Routes ---

# @app.get("/login")
# async def login(request: Request):
#     auth_url = msal_app.get_authorization_request_url(
#         CONFIG["SCOPE"],
#         redirect_uri=request.url_for("getAToken"),  # FastAPI's url_for
#         prompt="select_account",  # Force user to select account on each login (optional)
#     )
#     print(f"Redirecting to: {auth_url}")
#     return RedirectResponse(auth_url)

# @app.get("/getAToken", name="getAToken")
# async def auth_response(request: Request):
#  try:
#      cache = msal.SerializableTokenCache()
#      result = msal_app.acquire_token_by_authorization_code(
#          request.query_params["code"],
#          scopes=CONFIG["SCOPE"],
#          redirect_uri=request.url_for("getAToken") # Ensure redirect_uri matches the original request
#      )

#      if "error" in result:
#          print("Authentication error: " + result.get("error"))
#          return templates.TemplateResponse("auth_error.html", {"request": request, "result": result})

#      request.session["user"] = result.get("id_token_claims")
#      if cache.has_state_changed:
#          msal_app.token_cache = cache

#      return RedirectResponse(url="/")  # Redirect to landing page after login
#  except Exception as e: # Handle exceptions
#      logging.exception("Error in auth_response:" + str(e)) # Log the exception
#      return templates.TemplateResponse("auth_error.html", {"request": request, "result": {"error": str(e)}}) # Show a general error

# # --- Logout Route ---

# @app.get("/logout")
# async def logout(request: Request):
#  request.session.pop("user", None)  # Clear user from session
#  return RedirectResponse(url="/login")

# # --- Main Application Routes ---

# @app.get("/", response_class=HTMLResponse)
# async def index(request: Request):
#     user = request.session.get("user")
#     if user:
#         #getDeployments()
#         return templates.TemplateResponse("landing.html", {
#             "request": request, 
#             "user": user,
#             "config": CONFIG  # Pass the CONFIG dictionary
#         })
#     else:
#         return RedirectResponse(url="/login")

# @app.get("/call_downstream_api")
# async def call_downstream_api(request: Request):
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
     
#      return templates.TemplateResponse("display.html", {"request": request, "result": api_result})

#  except Exception as e:  # Handle broader exceptions
#      logging.exception(f"Error in call_downstream_api: {str(e)}")
#      return templates.TemplateResponse("error.html", {"request": request, "error": str(e)})  # Render a general error page
 
#  def getDeployments():
#      # Replace with your subscription ID
#     subscription_id = os.environ.get("SUBSCRITPION_ID")
#     resource_group = os.environ.get("RESOURCE_GROUP_NAME")
#     openai_account = os.environ.get("OPENAI_ACCOUNT_NAME")

#     # Use ManagedIdentityCredential for authentication (managed identities, App Service, etc.)
#     credential = ManagedIdentityCredential()

#     # Create a Cognitive Services management client
#     client = CognitiveServicesManagementClient(credential, subscription_id)

#     # Get all deployments in the subscription
#     deployments = client.deployments.list(resource_group_name=resource_group, account_name=openai_account)  # Or list_by_resource_group() for a specific resource group

#     for deployment in deployments:
#         print(f"Deployment Name: {deployment.name}")
#         print(f"Resource Group: {deployment.resource_group}")
#         print(f"Provisioning State: {deployment.provisioning_state}")
#         print(f"Model: {deployment.model.name if deployment.model else 'N/A'}") # Access model info
#         print(f"Scale Settings: {deployment.scale_settings}")
#         print("-" * 20) # Separator

# if __name__ == "__main__":
#     port = int(os.getenv("PORT", 8000))  # Use the environment variable or default to 8000
#     uvicorn.run(app, host="127.0.0.1", port=port, reload=True)