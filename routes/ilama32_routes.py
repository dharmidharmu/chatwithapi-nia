import json
from typing import Dict, List
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
import requests
import httpx
import logging
from dotenv import load_dotenv # For environment variables (recommended)

# create the router
router = APIRouter()

load_dotenv()  # Load environment variables from .env file

# Create a logger for this module
logger = logging.getLogger(__name__)

options = {
            "num_ctx": 8192 # set no. of tokens in the context
          }

class Query(BaseModel):
    model: str = Field(..., example="Ilama3.2")
    prompt: str = Field(..., example="Write a summary about climate change.")
    messages: list

class Conversation(BaseModel):
    id: str
    messages: List[Dict[str, str]] = []

@router.get("/listModels")
async def listModels(request: Request):
    try:
        async with httpx.AsyncClient() as client:
            result = make_get_request("http://localhost:11434/api/tags")
            return JSONResponse({"response": result}, status_code=200)
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
        return JSONResponse({"error": f"HTTP error occurred: {e.response.status_code} - {e.response.text}"}, status_code=e.response.status_code)
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        return JSONResponse({"error": f"An error occurred: {str(e)}"}, status_code=500)

@router.post("/generate", summary="Generate text using the specified model and prompt")
async def generateCompletion(query: Query):
    logger.info(f"query: {query}")
    try:
        result = await make_post_request("http://localhost:11434/api/generate", {"model": query.model, "prompt": query.prompt, "stream" : False, "keep_alive":-1})
        return JSONResponse({"response": result}, status_code=200)
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
        return JSONResponse({"error": f"HTTP error occurred: {e.response.status_code} - {e.response.text}"}, status_code=e.response.status_code)
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        return JSONResponse({"error": f"An error occurred: {str(e)}"}, status_code=500)
    
@router.post("/chat", summary="Start a conversation with the specified model and prompt")
async def chat(query: Query):
    try:
        result = await make_post_request("http://localhost:11434/api/chat", {"model": query.model, "messages": query.messages, "stream" : False})
        logger.info(f"llama Response {result}")
        return JSONResponse({"response": result}, status_code=200)
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
        return JSONResponse({"error": f"HTTP error occurred: {e.response.status_code} - {e.response.text}"}, status_code=e.response.status_code)
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        return JSONResponse({"error": f"An error occurred: {str(e)}"}, status_code=500)
    
async def chat2(model: str, messages: list[str]):
    message_content = "No response from Llama"
    try:
        # Make the POST request and get the result as a dictionary
        llama_response = await make_post_request(
            "http://localhost:11434/api/chat", 
            {"model": model, "messages": messages, "stream": False, "options": options}
        )
        #logger.debug(f"Llama Response: {llama_response}, type: {type(llama_response)}")

        # Correctly extract the message content
        if "message" in llama_response:
            message_content = llama_response["message"].get("content", "No response from Llama")
        else:
            message_content = "No message in Llama response"
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
        message_content = f"HTTP error occurred: {e.response.status_code} - {e.response.text}"
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        message_content = f"An error occurred: {str(e)}"
    
    return message_content

async def make_post_request(url: str, data: dict):
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, json=data)
        response.raise_for_status()
        # Log raw response
        logger.debug(f"Raw response: {response.text}")
        return response.json()

async def make_get_request(url: str, params: dict = None):
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        # Log raw response
        logger.debug(f"Raw response: {response.text}")
        return response.json()

async def make_put_request(url: str, data: dict):
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.put(url, json=data)
        response.raise_for_status()
        # Log raw response
        logger.debug(f"Raw response: {response.text}")
        return response.json()

async def make_delete_request(url: str, params: dict = None):
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.delete(url, params=params)
        response.raise_for_status()
        # Log raw response
        logger.debug(f"Raw response: {response.text}")
        return response.json()
