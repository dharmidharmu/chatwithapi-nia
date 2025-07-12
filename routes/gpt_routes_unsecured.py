import os
import json
import logging
import base64
from pathlib import Path
from bson import ObjectId
import urllib.parse
from typing import Annotated

from fastapi import APIRouter, Cookie, Request, Security, UploadFile, Body, File, Form, HTTPException, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient
from azure.identity import ClientSecretCredential
from azure.core.exceptions import AzureError

from pymongo.errors import DuplicateKeyError
from auth_msal import get_current_user
from data.GPTData import GPTData
from data.InputPrompt import InputPrompt
from data.ModelConfiguration import ModelConfiguration
from gpt_utils import handle_upload_files, create_folders
from azure_openai_utils import generate_response
from mongo_service import fetch_chat_history_for_use_case, get_gpt_by_id, create_new_gpt, get_gpts_for_user, update_gpt, delete_gpt, delete_gpts, delete_chat_history, fetch_chat_history, get_usecases, update_gpt_instruction, get_collection, get_prompts, update_prompt, delete_prompt
from prompt_utils import PromptValidator

from bson import ObjectId
from dotenv import load_dotenv # For environment variables (recommended)

conversations = []
use_cases = []
max_tokens_in_conversation = 10 # To be implemented
max_conversations_to_consider = 10

delimiter = "```"
load_dotenv()  # Load environment variables from .env file
create_folders()

# Create a logger for this module
logger = logging.getLogger(__name__)

# create the router
router = APIRouter()

@router.post("/create_gpt")
async def create_gpt(request: Request,  loggedUser: str = Cookie(None), gpt: str = Body(...), files: list[UploadFile] = File(...)):
    try:
        # Parse the JSON string into a dictionary
        gpt = json.loads(gpt)
        #loggedUser = await getUserName(request, "create_gpt")
        # loggedUser = user.get("name", "N/A")  # Extract the username from the user token payload
        logger.info(f"Logged User: {loggedUser}")

        if loggedUser != None and loggedUser != "N/A":
            gpt["user"] = loggedUser
            gpt["use_case_id"] = ""
            # Now you can access gpt as a dictionary
            gpt = GPTData(**gpt)  # Validate and create GPTData instance
            #logger.info(f"Received GPT data: {gpt}")

            if files != None and len(files) > 0:
                for file in files:
                    logger.info(f"Received files: {file.filename}")

            gpt_id = await create_new_gpt(gpt)
            logger.info(f"GPT created with ID: {gpt_id}")

            file_upload_status = ""

            if gpt.use_rag:
                file_upload_status = await handle_upload_files(gpt_id, gpt, files)
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

@router.get("/get_gpts")
async def get_gpts(request: Request):
    gpts = []
    loggedUser = await getUserName(request, "get_gpts")
    #logger.info(f"User: {json.dumps(request.session.get('user'))}")
    logger.info(f"Logged User: {loggedUser}")

    if loggedUser != None and loggedUser != "N/A":
        gpts = await get_gpts_for_user(loggedUser)
        for gpt in gpts:
            gpt["_id"] = str(gpt["_id"]) # Convert ObjectId to string

    return JSONResponse({"gpts": gpts}, status_code=200)

@router.post("/chat/{gpt_id}/{gpt_name}")
async def chat(request: Request, gpt_id: str, gpt_name: str,  user_message: str = Form(...), params: str = Form(...), uploadedImage: UploadFile = File(...)):
    if not user_message:
        return JSONResponse({"error": "Missing 'user_message' in request body."}, status_code=400)
    
    try:
        logger.info(f"Chat request received with GPT ID: {gpt_name} \n user message: {user_message} \n params: {params}")
        gpt = await get_gpt_by_id(gpt_id)

         # Parse the JSON string into a dictionary
        model_configuration = json.loads(params)
        model_configuration = ModelConfiguration(**model_configuration)  
        #logger.info(f"Received GPT data: {gpt} \n Model Configuration: {model_configuration}")

        if gpt is None:
            return JSONResponse({"error": "GPT not found."}, status_code=404)
        
        streaming_response = False
        response = await generate_response(streaming_response, user_message, model_configuration, gpt, uploadedImage)
    except HTTPException as he:
        logger.error(f"Error while getting response from Model. Details : \n {he.detail}", exc_info=True)
        return JSONResponse({"error": f"Error while getting response from Model. Details : \n {he.detail}"}, status_code=500)

    return JSONResponse({"response": response['model_response'], "total_tokens" : response['total_tokens'] if response['total_tokens'] else 0, "follow_up_questions": response['follow_up_questions'] }, status_code=200)

@router.post("/chat/stream/{gpt_id}/{gpt_name}")
async def chat(request: Request, gpt_id: str, gpt_name: str,  user_message: str = Form(...), params: str = Form(...), uploadedImage: UploadFile = File(...)):
    if not user_message:
        return JSONResponse({"error": "Missing 'user_message' in request body."}, status_code=400)
    
    loggedUser = await getUserName(request, "update_instruction")
    logger.info(f"Logged User: {loggedUser}")
    
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

@router.post("/update_instruction/{gpt_id}/{gpt_name}/{usecase_id}")
async def update_instruction(request: Request, gpt_id: str, gpt_name: str, usecase_id: str):
    logger.info(f"Updating instruction for GPT with ID: {gpt_id} Name: {gpt_name} Usecase : {usecase_id}")
    # Ensure that the user is authenticated and has the necessary permissions

    try:
        loggedUser = await getUserName(request, "update_instruction")
        logger.info(f"Logged User: {loggedUser}")
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

@router.put("/upload_document/{gpt_id}/{gpt_name}")
async def upload_document_index(request: Request, gpt_id: str, gpt_name: str,  files: list[UploadFile] = File(...)):
    logger.info(f"Updating GPT with ID: {gpt_id} Name: {gpt_name}")
    gpts_collection = await get_collection("gpts")
    gpt: GPTData = await gpts_collection.find_one({"_id": ObjectId(gpt_id)})
    logger.info(f"GPT Details: {gpt}")
    try:
        loggedUser = await getUserName(request, "modify_gpt")
        logger.info(f"Logged User: {loggedUser}")

        if loggedUser != None and loggedUser != "N/A":
            if gpt is None:
                raise ValueError("GPT object is None. Ensure it is properly initialized.")
            # Parse the JSON string into a dictionary
            # gpt = json.loads(gpt)
            gpt["user"] = loggedUser
            gpt["use_case_id"] = gpt.get("use_case_id", "") 
            gpt["use_rag"] = True
        
            # Now you can access gpt as a dictionary
            gpt = GPTData(**gpt)  # Validate and create GPTData instance
            logger.info(f"Received GPT data: {gpt}")

            if files != None and len(files) > 0:
                for file in files:
                    logger.info(f"Received files: {file.filename}")

            # result = await update_gpt(gpt_id, gpt_name, gpt)
            logger.info(f"GPT : {gpt.name}, use_rag: {bool(gpt.use_rag)}")

            file_upload_status = ""

            if gpt.use_rag:
                file_upload_status = await handle_upload_files(gpt_id, gpt, files)
                logger.info(f"RAG Files uploaded successfully: {file_upload_status}")
                response = JSONResponse({"message": "Document Uploaded Successfully!", "gpt_name": gpt_name, "file_upload_status" : file_upload_status}, status_code=200)
                
            # if result.modified_count == 1:
            #     response = JSONResponse({"message": "GPT created successfully!", "gpt_name": gpt_name, "file_upload_status" : file_upload_status}, status_code=200)
            # elif result.modified_count == 0:
            #     response = JSONResponse({"message": "No Changes in the updated GPT!", "gpt_name": gpt_name, "file_upload_status" : file_upload_status}, status_code=200)
            else:
                response = JSONResponse({"error": "GPT not found"}, status_code=404)
        else:
            response = JSONResponse({"error": "Unauthorized user"}, status_code=401)
    except Exception as e:
        logger.error(f"Error occurred while updating GPT: {e}", exc_info=True)
        response = JSONResponse({"error": f"Error Code: {e}"}, status_code=500)

    return response

@router.put("/update_gpt/{gpt_id}/{gpt_name}")
async def modify_gpt(request: Request, gpt_id: str, gpt_name: str,  gpt: str = Body(...), files: list[UploadFile] = File(...)):
    logger.info(f"Updating GPT with ID: {gpt_id} Name: {gpt_name}")

    try:
        loggedUser = await getUserName(request, "modify_gpt")
        logger.info(f"Logged User: {loggedUser}")
        if loggedUser != None and loggedUser != "N/A":
            # Parse the JSON string into a dictionary
            gpt = json.loads(gpt)
            gpt["user"] = loggedUser
            gpt["use_case_id"] = gpt.get("use_case_id", "") 
        
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
                file_upload_status = await handle_upload_files(gpt_id, gpt, files)
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
    
@router.delete("/delete_gpt/{gpt_id}/{gpt_name}")
async def remove_gpt(request: Request, gpt_id: str, gpt_name: str):
    logger.info(f"Deleting GPT: {gpt_id} Name: {gpt_name}")

    loggedUser = await getUserName(request, "remove_gpt")
    logger.info(f"Logged User: {loggedUser}")

    # Delete the GPT
    gpt_delete_result = await delete_gpt(gpt_id, gpt_name)

    if gpt_delete_result.deleted_count == 1:
        response = JSONResponse({"message": "GPT and Chat history removed successfully.!"})
    else:
        response = JSONResponse({"error": "GPT not found"}, status_code=404)

    return response

@router.delete("/delete_all_gpts")
async def delete_all_gpts(request: Request):
    loggedUser = await getUserName(request, "delete_all_gpts")
    logger.info(f"Logged User: {loggedUser}")
    if loggedUser != None and loggedUser != "N/A":
        result = await delete_gpts(loggedUser)  # Delete all documents in the collection
        if result.deleted_count > 0:
            response = JSONResponse({"message": "All GPTs deleted successfully!"})
        else:
            response = JSONResponse({"error": "No GPTs found"}, status_code=404)
    else:
        response = JSONResponse({"error": "Unauthorized user"}, status_code=401)
    
    return response
    
@router.get("/chat_history/{gpt_id}/{gpt_name}")
async def get_chat_history(request: Request, gpt_id: str, gpt_name: str):
    logger.info(f"Fetching chat history for GPT: {gpt_id} Name: {gpt_name}")

    loggedUser = await getUserName(request, "get_chat_history")
    logger.info(f"Logged User: {loggedUser}")

    chat_history = await fetch_chat_history(gpt_id, gpt_name, max_tokens_in_conversation)  # Fetch chat history from MongoDB
    #logger.info(f"Chat history {chat_history}")

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

@router.get("/chat_history/{gpt_id}/{gpt_name}/{use_case_id}")
async def get_chat_history_for_use_case(request: Request, gpt_id: str, gpt_name: str,  use_case_id: str = "all"):
    logger.info(f"Fetching chat history for GPT: {gpt_id} Name: {gpt_name}")

    loggedUser = await getUserName(request, "get_chat_history_for_use_case")
    logger.info(f"Logged User: {loggedUser}")

    if use_case_id == "all":
        chat_history = await fetch_chat_history(gpt_id, gpt_name, max_tokens_in_conversation)
    else:
        chat_history = await fetch_chat_history_for_use_case(use_case_id, gpt_id, gpt_name, max_tokens_in_conversation)  # Fetch chat history from MongoDB
    logger.info(f"Chat history {chat_history}")

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

@router.put("/clear_chat_history/{gpt_id}/{gpt_name}")
async def clear_chat_history(request: Request, gpt_id: str, gpt_name: str):
    logger.info(f"Clearing chat history for GPT: {gpt_id} Name: {gpt_name}")
    loggedUser = await getUserName(request, "clear_chat_history")
    logger.info(f"Logged User: {loggedUser}")

    result = await delete_chat_history(gpt_id, gpt_name)  # Delete all documents in the collection

    logger.info(f"Modified count: {result.modified_count}")
    
    if result.modified_count > 0:
        response = JSONResponse({"message": "Cleared conversations successfully!"})
    else:
        response = JSONResponse({"error": "No messages found in GPT"}, status_code=404)
    
    return response
    
@router.get("/usecases/{gpt_id}")
async def fetch_usecases(request: Request, gpt_id: str):
    try:
        loggedUser = await getUserName(request, "fetch_usecases")
        logger.info(f"Logged User: {loggedUser}")
        result = await get_usecases(gpt_id)
        logger.info(f"Use cases fetched successfully: {len(result)}")
        response = JSONResponse({"message": "SUCCESS", "usecases": result}, status_code=200)
    except Exception as e:
        logger.error(f"Error occurred while fetching usecases: {e}", exc_info=True)
        response = JSONResponse({"error": f"Error occurred while fetching usecases: {e}"}, status_code=500)
    
    return response

@router.get("/get_prompts/{gpt_id}/{usecase}/{user}")
async def get_prompts_for_usecase(request: Request, gpt_id: str, usecase: str, user: str):
    """
    Fetch the use case by ID and return the 'prompt' field.
    """
    loggedUser = await getUserName(request, "get_prompts_for_usecase")
    logger.info(f"Logged User: {loggedUser}")
    try:
        # Fetch the use case details for the given GPT ID and use case ID
        prompts_default = await get_prompts(gpt_id, usecase, "Default")
        logger.info(f"Prompts Default: {prompts_default}")
        prompts = await get_prompts(gpt_id, usecase, user)
        # Merge prompts_default and prompts, avoiding duplicates by 'key'
        if prompts_default and prompts:
            existing_keys = {p.get("key") for p in prompts}
            merged_prompts = prompts.copy()
            for p in prompts_default:
                if p.get("key") not in existing_keys:
                    merged_prompts.append(p)
            prompts = merged_prompts
        elif prompts_default:
            prompts = prompts_default
        #logger.info(f"Prompts fetched successfully: {len(prompts)}")
        logger.info(f"Prompts: {prompts}")

        if not usecase:
            return JSONResponse({"error": "Use case not found"}, status_code=404)

        # Extract the 'prompt' field from the use case
        

        return JSONResponse({"prompts": prompts}, status_code=200)
    except Exception as e:
        logger.error(f"Error occurred while fetching prompts: {e}", exc_info=True)
        return JSONResponse({"error": f"Error occurred while fetching prompts: {e}"}, status_code=500)

@router.post("/update_prompt/{gpt_id}/{usecase}/{user}/{refinedPrompt}/{promptTitle}")
async def update_prompt_for_usecase(request: Request, gpt_id: str, usecase: str, user: str, refinedPrompt: str, promptTitle: str):
    try:

        user = getUserName(request, "update_prompt_for_usecase")  # Extract the username from the user token payload
        logger.info(f"Logged User: {user}")

        if not all([gpt_id, usecase, user, refinedPrompt]):
            return JSONResponse({"success": False, "error": "Missing required fields"}, status_code=400)

        result = await update_prompt(gpt_id, usecase, user, refinedPrompt, promptTitle)
        logger.info(f"Prompt updated successfully: {result}")
        return JSONResponse({"success": True}, status_code=200)
        

    except Exception as e:
        logger.error(f"Error in update_prompt_for_usecase: {e}", exc_info=True)
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@router.delete("/delete_prompt/{gpt_id}/{usecase}/{user}/{key}")
async def delete_prompt_for_usecase(request: Request, gpt_id: str, usecase: str, user: str, key: str):
    try:
        user = getUserName(request, "delete_prompt_for_usecase")
        logger.info(f"Logged User: {user}")
    
        if not all([gpt_id, usecase, user, key]):
            return JSONResponse({"success": False, "error": "Missing required fields"}, status_code=400)

        result = await delete_prompt(gpt_id, usecase, user, key)
        logger.info(f"Prompt deleted successfully: {result}")
        return JSONResponse({"success": True}, status_code=200)

    except Exception as e:
        logger.error(f"Error in delete_prompt_for_usecase: {e}", exc_info=True)
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@router.get("/logs")
async def get_logs():
    """Fetch the contents of the app.log file."""
    log_file_path = "logs/app.log" # Update with your actual log file path

    if not os.path.exists(log_file_path):
        raise HTTPException(status_code=404, detail="Log file not found")

    with open(log_file_path, "r") as f:
        log_content = f.read()

    #logger.info(log_filename)  

    return {"log_content": log_content}

@router.get("/deployedModels")
async def getDeployedModelsFromAzure():
    """Fetch the open ai models deployed in azure open ai portal."""
    try:
        deployments = await getDeployments2()
        logger.info(f"Deployments fetched successfully: {len(deployments)}")
        if deployments is None:
            response = JSONResponse({"message": "No deployments found"}, status_code=200)
        else:
            response = JSONResponse({"message": "SUCCESS", "model_deployments": deployments}, status_code=200)
    except Exception as e:
        logger.error(f"Error occurred while fetching deployments: {e}", exc_info=True)
        response = JSONResponse({"error": f"Error occurred while fetching deployments: {e}"}, status_code=500)
    return response

@router.post("/refinePrompt/{gpt_id}/{usecase}/{user}")
async def refinePrompt(
    request: Request,
    gpt_id: str,
    usecase: str,
    user: str,
    loggedUser: Annotated[dict, Depends(get_current_user)],
    body: InputPrompt = Body(...)
):
    """Refine the prompt based on the user query."""
    validator = PromptValidator()
    response: str = ""
    system_prompt: str = None

    try:
        user = loggedUser.get("name", "N/A")  # Extract the username from the user token payload
        logger.info(f"Logged User: {user}")
        input_prompt = body.prompt
        logger.info(f"Input prompt (Original) : {input_prompt} Length : {len(input_prompt)}")

        if gpt_id is not None:
            gpt_data: GPTData = await get_gpt_by_id(gpt_id)
            system_prompt = gpt_data["instructions"]

        # Process prompt
        response = await validator.process_prompt_optimized(input_prompt, system_prompt)
        refinedPrompt = response.refined_prompt
        promptTitle = response.title if hasattr(response, "title") else "Simple Prompt"
        logger.info(f"Title: {promptTitle} Refined prompt : {refinedPrompt} Length : {len(refinedPrompt)} ")
        update_response = await update_prompt(gpt_id, usecase, user, refinedPrompt, promptTitle)
        logger.info(f"Prompt updated: {update_response}")

        return JSONResponse({"refined_prompt": response.dict() if hasattr(response, "dict") else response.__dict__}, status_code=200)
    except Exception as e:
        logger.error(f"Error occurred while refining prompt: {e}", exc_info=True)
        return JSONResponse({"refined_prompt": input_prompt}, status_code=200)

@router.get("/get_image/{imagePath}",

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

async def getDeployments2():
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

# async def getUserName(request: Request, callee: str,  = None) -> str:
#     """
#     Get the authenticated user's name from the Azure AD token.
    
#     Args:
#         request: The FastAPI request object
#         callee: The name of the calling method (for logging)
#         user: The user token payload from Azure AD (injected by FastAPI)
        
#     Returns:
#         str: The authenticated user's name or email
#     """
#     try:
#         # Extract user information from the token claims
#         # The exact claim depends on how your Azure AD app is configured
#         # Common options: name, preferred_username, email
        
#         # Try to get the name from various possible claims
#         if isinstance(user, dict):
#             if "name" in user:
#                 username = user["name"]
#             elif "preferred_username" in user:
#                 username = user["preferred_username"]
#             elif "email" in user:
#                 username = user["email"]
#             elif "upn" in user:
#                 username = user["upn"]
#             else:
#                 # If no recognizable name field, use the object ID as fallback
#                 username = user.get("oid", "Unknown User")
            
#             logger.info(f"Calling Method: {callee}, Authenticated User: {username}")
#             return username
#         else:
#             logger.warning(f"User object is not a dictionary: {type(user)}")
#             return "Unknown User"
#     except Exception as e:
#         logger.error(f"Error extracting username from token: {str(e)}", exc_info=True)
#         return "Unknown User"

async def getUserName(request:Request, callee: str):
    #return getSessionUser(request)
    return "Dharmeshwaran S"