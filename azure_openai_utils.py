import os
import base64
import logging
import json
import re
from fastapi.responses import StreamingResponse
import requests
import datetime
import tiktoken

from fastapi import UploadFile
from openai import APIConnectionError, AsyncAzureOpenAI, AzureOpenAI, BadRequestError, RateLimitError
from azure.storage.blob import BlobServiceClient
from azure.storage.blob import generate_blob_sas, BlobSasPermissions

from data.GPTData import GPTData
from data.ModelConfiguration import ModelConfiguration

from azure.identity import DefaultAzureCredential, ClientSecretCredential
from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient
from azure.search.documents import SearchClient

from dependencies import NiaAzureOpenAIClient
from gpt_utils import extract_json_content, extract_response, get_previous_context_conversations, get_token_count, handle_upload_files
from standalone_programs.image_analyzer import analyze_image
from dotenv import load_dotenv # For environment variables (recommended)

from mongo_service import fetch_chat_history, delete_chat_history, update_message, get_usecases
from role_mapping import ALL_FIELDS, FORMAT_RESPONSE_AS_MARKDOWN, FUNCTION_CALLING_USER_MESSAGE, NIA_FINOLEX_PDF_SEARCH_SEMANTIC_CONFIGURATION_NAME, NIA_FINOLEX_SEARCH_INDEX, NIA_SEMANTIC_CONFIGURATION_NAME, USE_CASE_CONFIG, CONTEXTUAL_PROMPT, SUMMARIZE_MODEL_CONFIGURATION, USE_CASES_LIST, FUNCTION_CALLING_SYSTEM_MESSAGE, get_role_information
from standalone_programs.simple_gpt import run_conversation, ticket_conversations, get_conversation
from routes.ilama32_routes import chat2
from constants import ALLOWED_DOCUMENT_EXTENSIONS, ALLOWED_IMAGE_EXTENSIONS

# from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient

load_dotenv()  # Load environment variables from .env file

# Create a logger for this module
logger = logging.getLogger(__name__)

token_encoder = tiktoken.encoding_for_model("gpt-4o") 

# Model = should match the deployment name you chose for your model deployment
delimiter = "```"
DEFAULT_RESPONSE = "N/A"
search_endpoint = os.getenv("SEARCH_ENDPOINT_URL")
search_key = os.getenv("SEARCH_KEY")
search_index = os.getenv("SEARCH_INDEX_NAME")
review_bytes_index = os.getenv("NIA_REVIEW_BYTES_INDEX_NAME")
nia_semantic_configuration_name = os.getenv("NIA_SEMANTIC_CONFIGURATION_NAME")

# Azure Open AI - Model parameters
DEFAULT_MODEL_NAME = os.getenv("DEFAULT_MODEL_NAME")
ECOMMERCE_MODEL_NAME = os.getenv("ECOMMERCE_MODEL_NAME")
AZURE_ENDPOINT_URL = os.getenv("AZURE_ENDPOINT_URL")
AZURE_OPENAI_KEY = os.getenv("OPENAI_API_KEY")
AZURE_OPENAI_MODEL_API_VERSION = os.getenv("API_VERSION")

# Azure GPT 4o parameters
GPT_4o_MODEL_NAME = os.getenv("GPT4O_MODEL_NAME")
GPT_4o_2_MODEL_NAME = os.getenv("GPT4O_2_MODEL_NAME")
GPT_4o_API_KEY=os.getenv("GPT4O_API_KEY")
GPT_4o_ENDPOINT_URL=os.getenv("GPT4O_ENDPOINT_URL")
GPT_4o_API_VERSION = os.getenv("GPT4O_API_VERSION")

subscription_id = os.getenv("SUBSCRIPTION_ID")
resource_group_name = os.getenv("RESOURCE_GROUP_NAME")
openai_account_name = os.getenv("OPENAI_ACCOUNT_NAME")
#previous_conversations_count = os.getenv("PREVIOUS_CONVERSATIONS_TO_CONSIDER")

# Azure Blob Storage - Used for storing image uploads
AZURE_BLOB_STORAGE_CONNECTION_STRING=os.getenv("BLOB_STORAGE_CONNECTION_STRING")
AZURE_BLOB_STORAGE_CONTAINER=os.getenv("BLOB_STORAGE_CONTAINER_NAME")
AZURE_BLOB_STORAGE_ACCOUNT_NAME=os.getenv("BLOB_STORAGE_ACCOUNT_NAME")
AZURE_BLOB_STORAGE_ACCESS_KEY=os.getenv("BLOB_STORAGE_ACCESS_KEY")

DEFAULT_ERROR_RESPONSE_FROM_MODEL="The requested information is not available in the retrieved data. Please try another query or topic."
DEFAULT_FOLLOW_UP_QUESTIONS = ["I would like to know more about this topic", "I need further clarification", "Rephrase your findings"]

blob_service_client = BlobServiceClient(f"https://{AZURE_BLOB_STORAGE_ACCOUNT_NAME}.blob.core.windows.net",
    credential=AZURE_BLOB_STORAGE_ACCESS_KEY
)

async def getAzureOpenAIClient(azure_endpoint: str, api_key: str, api_version: str, stream: bool):
    #logger.info(f"delimiter: {delimiter} \ndefault_model_name: {default_model_name} \necomm_model_name: {ecomm_model_name} \nazure_endpoint: {azure_endpoint} \napi_key: {api_key} \napi_version: {api_version} \nsearch_endpoint: {search_endpoint} \nsearch_key: {search_key} \nsearch_index: {search_index}")
    
    # # Establish connection to Azure Open AI
    # if stream:
    #     client = AsyncAzureOpenAI(
    #         azure_endpoint=azure_endpoint,
    #         api_key=api_key,
    #         api_version=api_version)
    # else:
    #     client = AzureOpenAI(
    #     azure_endpoint=azure_endpoint,
    #     api_key=api_key,
    #     api_version=api_version)

    # Create the singleton instance
    nia_azure_client = await NiaAzureOpenAIClient().create()

    # Retrieve the client
    client = nia_azure_client.get_azure_client()
    
    return client

def get_azure_search_parameters(search_endpoint: str, index_name: str, search_key: str, role_information: str, index_fields: list):
    extra_body = {
        "data_sources": [{
            "type": "azure_search",
            "parameters": {
                "authentication": {
                    "type": "api_key",
                    "key": f"{search_key}"
                },
                "endpoint": f"{search_endpoint}",
                "index_name": f"{index_name}",
                "fields_mapping": {
                    "content_fields_separator": "\n",
                    "content_fields": index_fields,
                    "filepath_field": None,
                    "title_field": None,
                    "url_field": None,
                    "vector_fields": []
                },
                "filter": None,
                "in_scope": True,
                "top_n_documents": 10,
                #"strictness": 3,
                "query_type": "semantic",
                "semantic_configuration": NIA_SEMANTIC_CONFIGURATION_NAME, #"default",
                #"role_information": instructions,
                "role_information": role_information
            }
        }]
    }
    
    logger.info(f"Extra Body for Azure Search: {extra_body}")
    return extra_body

async def store_to_blob_storage(uploadedImage: UploadFile = None):
    try:
        file_name = uploadedImage.filename

        # Initialize Blob Service Client
        blob_client = blob_service_client.get_blob_client(container=AZURE_BLOB_STORAGE_CONTAINER, blob=file_name)

        # Upload image to Azure Blob Storage
        blob_client.upload_blob(uploadedImage.file, overwrite=True)

        # Generate a SAS token (valid for 60 minutes)
        sas_token = generate_blob_sas(
            account_name=AZURE_BLOB_STORAGE_ACCOUNT_NAME,
            container_name=AZURE_BLOB_STORAGE_CONTAINER,
            blob_name=file_name,
            account_key=AZURE_BLOB_STORAGE_ACCESS_KEY,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=60)
        )

        # Generate URL
        #blob_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{azure_blob_storage_container}/{file_name}"

        # Generate the full URL with SAS token
        blob_url_with_sas = f"{blob_client.url}?{sas_token}"
        logger.info(f"Blob URL: {blob_url_with_sas}")
        return blob_url_with_sas
    except Exception as e:
        logger.error(f"Error occurred while storing image to Azure Blob Storage: {e}", exc_info=True)
        return DEFAULT_RESPONSE
    
    #return DEFAULT_RESPONSE if blob_url_with_sas == None or blob_url_with_sas == "" else blob_url_with_sas

# async def fetch_image_from_blob_storage(blob_url: str):
#     try:
#         # Extract the blob client from the URL
#         blob_client = blob_service_client.get_blob_client(container=AZURE_BLOB_STORAGE_CONTAINER, blob=blob_url.split("/")[-1].split("?")[0])

#         # Download the blob content
#         download_stream = await blob_client.download_blob()
#         image_data = await download_stream.readall()

#         # Convert the image data to base64
#         base64_image = base64.b64encode(image_data).decode('utf-8')
#         logger.info(f"Fetched image from blob storage and converted to base64")

#         return base64_image
#     except Exception as e:
#         logger.error(f"Error occurred while fetching image from blob storage: {e}", exc_info=True)
#         return str(e)

async def saveAssistantResponse(response: str, gpt: GPTData, conversations: list):
    # Log the response to database
        await update_message({
            "gpt_id": gpt["_id"], # Make sure gpt is accessible here
            "gpt_name": gpt["name"], # Make sure gpt is accessible here
            "role": "assistant",
            "content": response,
            "user": gpt["user"],
            "use_case_id": gpt["use_case_id"],
        })

        conversations.append({"role": "assistant", "content": response}) # Append the response to the conversation history

async def get_completion_from_messages_standard(gpt: GPTData, model_configuration, conversations, use_case, role_information):
    model_response = "No Response from Model"
    main_response = ""
    total_tokens = 0
    follow_up_questions = []
    reasoning = ""

    # This client is synchronous and doesn't need await signal. Set stream=False

    try:
        # Get Azure Open AI Client and fetch response
        client = await getAzureOpenAIClient(AZURE_ENDPOINT_URL, AZURE_OPENAI_KEY, AZURE_OPENAI_MODEL_API_VERSION, False)
        model_configuration: ModelConfiguration = model_configuration if  isinstance(model_configuration, ModelConfiguration) else ModelConfiguration(**model_configuration)
        extra_body = {}
        
        if gpt["use_rag"] == True:
            logger.info("Assigning additional search parameters for E-commerce model")
            if use_case == "REVIEW_BYTES":
                #extra_body = get_azure_search_parameters(search_endpoint, review_bytes_index, search_key, role_information, review_bytes_index_fields)
                pass
            else:
                #extra_body = get_azure_search_parameters(search_endpoint, search_index, search_key, role_information, ecomm_rag_demo_index_fields)
                pass
        
        response = await client.chat.completions.create(
            model=gpt["name"],
            messages=conversations,
            max_tokens=model_configuration.max_tokens, #max_tokens is now deprecated with o1 models
            temperature=model_configuration.temperature,
            top_p=model_configuration.top_p,
            frequency_penalty=model_configuration.frequency_penalty,
            presence_penalty=model_configuration.presence_penalty,
            extra_body=extra_body,
            seed=100,
            stop=None,
            stream=False,
            user=gpt["user"]
            #n=2,
            #reasoning_effort="low", # available for o1,o3 models only
            #timeout=30,
        )
        model_response = response.choices[0].message.content
        logger.info(f"Full Model Response is {response}")

        
        if model_response is None or model_response == "":
            main_response = "No Response from Model. Please try again."
        else:            
            main_response, follow_up_questions, total_tokens = await extract_json_content(response)
    
    except (APIConnectionError, RateLimitError) as retryable_ex:
        logger.warning(f"Retryable error: {type(retryable_ex).__name__} - {retryable_ex}", exc_info=True)

        from dependencies import NiaAzureOpenAIClient
        logger.info(f"Retrying with next endpoint")
        client = await NiaAzureOpenAIClient().retry_with_next_endpoint()
        try:
            response = await client.chat.completions.create(
                model=gpt["name"],
                messages=conversations,
                max_tokens=model_configuration.max_tokens,
                temperature=model_configuration.temperature,
                top_p=model_configuration.top_p,
                frequency_penalty=model_configuration.frequency_penalty,
                presence_penalty=model_configuration.presence_penalty,
                extra_body=extra_body,
                seed=100,
                stop=None,
                stream=False,
                user=gpt["user"]
            )
            model_response = response.choices[0].message.content
            logger.info(f"Retry Model Response is {response}")

            if model_response is None or model_response == "":
                main_response = "No Response from Model. Please try again."
            else:
                main_response, follow_up_questions, total_tokens = await extract_json_content(response)

        except Exception as final_ex:
            logger.error(f"Retry also failed: {final_ex}", exc_info=True)
            total_tokens = len(token_encoder.encode(str(conversations)))
            main_response = f"All Azure OpenAI endpoints failed. Please try again later.\n\n Exception Details : {str(final_ex)}"

    
    except BadRequestError as be:
        logger.error(f"BadRequestError occurred while fetching model response: {be}", exc_info=True)
        total_tokens = len(token_encoder.encode(str(conversations)))
        main_response = f"Bad Request error occurred while reaching to Azure Open AI. \n\n Exception Details : " + be.message
    
    except Exception as e:
        logger.error(f"Error occurred while fetching model response: {e}", exc_info=True)
        main_response = f"Error occurred while fetching model response: \n\n" + str(e)
    finally:
         # Log the response to database
        await saveAssistantResponse(main_response, gpt, conversations)
        
    return {
        "model_response" : main_response,
        "total_tokens": total_tokens,
        "follow_up_questions": follow_up_questions,
        "reasoning" : reasoning
    }

async def get_completion_from_messages_stream(gpt: GPTData, model_configuration, conversations, use_case, role_information):
     # This client is asynchronous and needs await signal. Set stream=True
    try:
        # Get Azure Open AI Client and fetch response
        client = await getAzureOpenAIClient(AZURE_ENDPOINT_URL, AZURE_OPENAI_KEY, AZURE_OPENAI_MODEL_API_VERSION, True)
        model_configuration: ModelConfiguration = model_configuration if  isinstance(model_configuration, ModelConfiguration) else ModelConfiguration(**model_configuration)
        extra_body = {}

        if gpt["use_rag"] == True:
            logger.info("Assigning additional search parameters for E-commerce model")
            if use_case == "REVIEW_BYTES":
                #extra_body = get_azure_search_parameters(search_endpoint, review_bytes_index, search_key, role_information, review_bytes_index_fields)
                pass
            else:
                #extra_body = get_azure_search_parameters(search_endpoint, search_index, search_key, role_information, ecomm_rag_demo_index_fields)
                pass
        
        full_response_content = ""
        
        async def stream_processor():
            nonlocal full_response_content
            nonlocal client

            try:
                response = await client.chat.completions.create(
                    model=gpt["name"],
                    messages=conversations,
                    max_tokens=model_configuration.max_tokens,
                    temperature=model_configuration.temperature,
                    top_p=model_configuration.top_p,
                    frequency_penalty=model_configuration.frequency_penalty,
                    presence_penalty=model_configuration.presence_penalty,
                    stop=None,
                    stream=True,
                    extra_body=extra_body,
                    seed=100,
                    user=gpt["user"]
                )

                async for chunk in response:
                    if len(chunk.choices) > 0 and hasattr(chunk.choices[0].delta, 'content'):
                        chunkContent = chunk.choices[0].delta.content
                        if chunkContent is not None:
                            full_response_content += chunkContent
                            yield chunkContent

            except (APIConnectionError, RateLimitError) as conn_ex:
                logger.warning(f"Connection/Rate limit error encountered: {conn_ex}")
                try:
                    client = await NiaAzureOpenAIClient().retry_with_next_endpoint()
                    response = await client.chat.completions.create(
                        model=gpt["name"],
                        messages=conversations,
                        max_tokens=model_configuration.max_tokens,
                        temperature=model_configuration.temperature,
                        top_p=model_configuration.top_p,
                        frequency_penalty=model_configuration.frequency_penalty,
                        presence_penalty=model_configuration.presence_penalty,
                        stop=None,
                        stream=True,
                        extra_body=extra_body,
                        seed=100,
                        user=gpt["user"]
                    )

                    async for chunk in response:
                        if len(chunk.choices) > 0 and hasattr(chunk.choices[0].delta, 'content'):
                            chunkContent = chunk.choices[0].delta.content
                            if chunkContent is not None:
                                full_response_content += chunkContent
                                yield chunkContent
                except Exception as retry_ex:
                    logger.error(f"Retry also failed: {retry_ex}")
                    full_response_content = f"All endpoints failed due to: {str(retry_ex)}"
                    yield full_response_content
        
        # Create a wrapper generator that handles post-stream processing
        async def response_wrapper():
            nonlocal full_response_content
            nonlocal gpt
            try:
                async for chunk in stream_processor():
                    #logger.info(f"chunk data {chunk}")
                    yield chunk
            
            except BadRequestError as be:
                logger.error(f"BadRequestError occurred while fetching model response: {be}", exc_info=True)
                full_response_content = f"Bad Request error occurred while reaching to Azure Open AI. \n\n Exception Details : " + be.message
                yield full_response_content
            
            except Exception as e:
                logger.error(f"Exception occurred while fetching model response: {e}", exc_info=True)
                #yield str(re)
                full_response_content = f"Exception occurred while fetching model response: {str(e)}."
                yield full_response_content
            finally:
                # This block ensures post-stream processing happens after the stream is complete
                if full_response_content is not None:
                    # update the response to database
                    await saveAssistantResponse(full_response_content, gpt, conversations)
        
        return StreamingResponse(response_wrapper(), media_type="text/event-stream")
    
    except Exception as e:
        logger.error(f"Error occurred while fetching model response: {e}", exc_info=True)
        return StreamingResponse(iter([str(e)]), media_type="text/event-stream")

async def get_completion_from_messages_default(model_name: str, use_rag: bool, messages: list, model_configuration: ModelConfiguration):

    model_response = "No Response from Model"

    # Get Azure Open AI Client and fetch response
    client = await getAzureOpenAIClient(AZURE_ENDPOINT_URL, AZURE_OPENAI_KEY, AZURE_OPENAI_MODEL_API_VERSION, False)
    model_configuration: ModelConfiguration = model_configuration if  isinstance(model_configuration, ModelConfiguration) else ModelConfiguration(**model_configuration)

    try:
        response = await client.chat.completions.create(
            model=model_name,
            messages=messages,
            max_tokens=model_configuration.max_tokens,
            temperature=model_configuration.temperature,
            top_p=model_configuration.top_p,
            frequency_penalty=model_configuration.frequency_penalty,
            presence_penalty=model_configuration.presence_penalty,
            stop=None,
            stream=False,
            seed=100
        )
        logger.info(f"Default Model Response is {response}")
        model_response = response.choices[0].message.content
        #logger.info(f"Tokens used: {response.usage.total_tokens}")
    except Exception as e:
        logger.error(f"Error occurred while fetching model response: {e}", exc_info=True)
        model_response = str(e)
    
    return model_response

async def analyzeImage_standard(gpt: GPTData, conversations, model_configuration, save_response_to_db: bool):
    model_response = "No Response from Model"
    main_response = "No Response from Model"
    total_tokens = 0
    follow_up_questions = []

    # Get Azure Open AI Client and fetch response
    #client = getAzureOpenAIClient(gpt4o_endpoint, gpt4o_api_key, gpt4o_api_version, False)
    try:
        client = await getAzureOpenAIClient(AZURE_ENDPOINT_URL, AZURE_OPENAI_KEY, AZURE_OPENAI_MODEL_API_VERSION, False)
        model_configuration: ModelConfiguration = model_configuration if  isinstance(model_configuration, ModelConfiguration) else ModelConfiguration(**model_configuration)

        try:
            response = await client.chat.completions.create(
                model=GPT_4o_2_MODEL_NAME,
                messages=conversations,
                max_tokens=model_configuration.max_tokens,
                temperature=model_configuration.temperature,
                top_p=model_configuration.top_p,
                frequency_penalty=model_configuration.frequency_penalty,
                presence_penalty=model_configuration.presence_penalty,
                stop=None,
                stream=False,
                seed=100
            )
            model_response = response.choices[0].message.content
            #logger.info(f"Model Response is {response}")
            #logger.info(f"Tokens used: {response.usage.total_tokens}")

            if model_response is None or model_response == "":
                model_response = "No Response from Model. Please try again."
            else:
                main_response, follow_up_questions, total_tokens = await processResponse(response)

            # Log the response to database
            if save_response_to_db:
                await saveAssistantResponse(main_response, gpt, conversations)

        except Exception as e:
            logger.error(f"Error occurred while fetching model response: {e}", exc_info=True)
            main_response = str(e)

    except (APIConnectionError, RateLimitError) as retryable_ex:
        logger.warning(f"Retryable error: {type(retryable_ex).__name__} - {retryable_ex}", exc_info=True)

        from dependencies import NiaAzureOpenAIClient
        client = await NiaAzureOpenAIClient().retry_with_next_endpoint()
        try:
            response = await client.chat.completions.create(
                model=GPT_4o_2_MODEL_NAME,
                messages=conversations,
                max_tokens=model_configuration.max_tokens,
                temperature=model_configuration.temperature,
                top_p=model_configuration.top_p,
                frequency_penalty=model_configuration.frequency_penalty,
                presence_penalty=model_configuration.presence_penalty,
                stop=None,
                stream=False,
                seed=100
            )
            model_response = response.choices[0].message.content
            logger.info(f"Retry Model Response is {response}")

            if model_response is None or model_response == "":
                main_response = "No Response from Model. Please try again."
            else:
                main_response, follow_up_questions, total_tokens = await extract_json_content(response)

        except Exception as final_ex:
            logger.error(f"Retry also failed: {final_ex}", exc_info=True)
            total_tokens = len(token_encoder.encode(str(conversations)))
            main_response = f"All Azure OpenAI endpoints failed. Please try again later.\n\n Exception Details : {str(final_ex)}"
    
    except BadRequestError as be:
        logger.error(f"BadRequestError occurred while fetching model response: {be}", exc_info=True)
        total_tokens = len(token_encoder.encode(str(conversations)))
        main_response = f"Bad Request error occurred while reaching to Azure Open AI. \n\n Exception Details : " + be.message
    
    except Exception as e:
        logger.error(f"Error occurred while fetching model response: {e}", exc_info=True)
        main_response = f"Error occurred while fetching model response: \n\n" + str(e)
    return {
        "model_response": main_response,
        "total_tokens": total_tokens,
        "follow_up_questions": follow_up_questions
    }

async def analyzeImage_stream(gpt: GPTData, conversations, model_configuration, save_response_to_db: bool):
    # Get Azure Open AI Client and fetch response
    #client = getAzureOpenAIClient(gpt4o_endpoint, gpt4o_api_key, gpt4o_api_version, True)
    try:
        client = await getAzureOpenAIClient(AZURE_ENDPOINT_URL, AZURE_OPENAI_KEY, AZURE_OPENAI_MODEL_API_VERSION, True)
        model_configuration: ModelConfiguration = model_configuration if  isinstance(model_configuration, ModelConfiguration) else ModelConfiguration(**model_configuration)

        try:
            full_response_content = ""
            
            async def stream_processor():
                nonlocal full_response_content
                nonlocal client
                
                try:
                    response = await client.chat.completions.create(
                        model=GPT_4o_2_MODEL_NAME,
                        messages=conversations,
                        max_completion_tokens=model_configuration.max_tokens,
                        temperature=model_configuration.temperature,
                        top_p=model_configuration.top_p,
                        frequency_penalty=model_configuration.frequency_penalty,
                        presence_penalty=model_configuration.presence_penalty,
                        stop=None,
                        stream=True,
                        seed=100
                    )
                    
                    async for chunk in response:
                        nonlocal full_response_content

                        if len(chunk.choices) > 0 and hasattr(chunk.choices[0].delta, 'content'):
                            logger.info(f"chunk.choices[0].delta {chunk.choices[0].delta}")
                            chunkContent = chunk.choices[0].delta.content
                            if chunkContent is not None:
                                full_response_content += chunkContent
                                yield chunkContent
                except (APIConnectionError, RateLimitError) as conn_ex:
                    logger.warning(f"Connection/Rate limit error encountered: {conn_ex}")
                    try:
                        client = await NiaAzureOpenAIClient().retry_with_next_endpoint()
                        response = await client.chat.completions.create(
                            model=GPT_4o_2_MODEL_NAME,
                            messages=conversations,
                            max_completion_tokens=model_configuration.max_tokens,
                            temperature=model_configuration.temperature,
                            top_p=model_configuration.top_p,
                            frequency_penalty=model_configuration.frequency_penalty,
                            presence_penalty=model_configuration.presence_penalty,
                            stop=None,
                            stream=True,
                            seed=100
                        )

                        async for chunk in response:
                            if len(chunk.choices) > 0 and hasattr(chunk.choices[0].delta, 'content'):
                                chunkContent = chunk.choices[0].delta.content
                                if chunkContent is not None:
                                    full_response_content += chunkContent
                                    yield chunkContent
                    except Exception as retry_ex:
                        logger.error(f"Retry also failed: {retry_ex}")
                        full_response_content = f"All endpoints failed due to: {str(retry_ex)}"
                        yield full_response_content
            
            # Create a wrapper generator that handles post-stream processing
            async def response_wrapper():
                nonlocal full_response_content

                try:
                    async for chunk in stream_processor():
                        yield chunk

                except BadRequestError as be:
                    logger.error(f"BadRequestError occurred while fetching model response: {be}", exc_info=True)
                    full_response_content = f"Bad Request error occurred while reaching to Azure Open AI. \n\n Exception Details : " + be.message
                    yield full_response_content

                except Exception as e:
                    logger.error(f"Exception occurred while fetching model response: {e}", exc_info=True)
                    #yield str(re)
                    full_response_content = f"Exception occurred while fetching model response: {str(e)}."
                    yield full_response_content
                finally:
                    # This block ensures post-stream processing happens after the stream is complete
                    if full_response_content is not None:
                        nonlocal gpt
                        # update the response to database
                        if save_response_to_db:
                            await saveAssistantResponse(full_response_content, gpt, conversations)
            
            return StreamingResponse(response_wrapper(), media_type="text/event-stream")
        
        except Exception as e:
            logger.error(f"Error occurred while fetching model response: {e}", exc_info=True)
            return StreamingResponse(iter([str(e)]), media_type="text/event-stream")
    except Exception as e:
        logger.error(f"Error occurred while fetching model response: {e}", exc_info=True)
        return StreamingResponse(iter([str(e)]), media_type="text/event-stream")
    
async def preprocessForRAG(user_message: str, image_response:str, use_case:str, gpt: GPTData, conversations: list, model_configuration: ModelConfiguration):
    
    context_information, additional_context_information, conversations = await determineFunctionCalling(user_message, image_response, use_case, gpt, conversations, model_configuration)

    # Step 4: Append the current user query with additional context into the conversation. 
    # This additional context is only to generate the response from the model and won't be saved in the conversation history for aesthetic reasons.
    if context_information is not None and context_information != "" and len(context_information) > 0:
        USER_PROMPT = USE_CASE_CONFIG[use_case]["user_message"]
        logger.info(f"USE_CASE_CONFIG[use_case]: {USER_PROMPT}")
        conversations.append({
                                "role": "user",
                                "content" : USER_PROMPT.format(
                                                query=user_message, sources=context_information, additional_sources=additional_context_information) + FORMAT_RESPONSE_AS_MARKDOWN
                            })
    else:
        conversations.append({"role": "user", "content": user_message})
    
    token_data = await get_token_count(gpt["name"], gpt["instructions"],  conversations, user_message, int(model_configuration.max_tokens))
    logger.info(f"Token Calculation : stage 1.3 - preprocessForRAG {token_data}")

async def processImage(streaming_response: bool, save_response_to_db: bool, user_message: str, model_configuration: ModelConfiguration, gpt: GPTData, conversations: list, uploadedImage: UploadFile = None):
    image_url = ""
    base64_image = ""
    try:
        if uploadedImage is not None and uploadedImage.filename != "blob" and uploadedImage.filename != "dummy":
            image_url = await store_to_blob_storage(uploadedImage)

            if image_url == None or image_url == "" or image_url == "N/A":
                logger.info(f"Image URL is empty. Passing Base64 encoded image for inference {image_url}")
                # 1. Read image content
                contents = await uploadedImage.read()

                # 2. Encode as base64 
                base64_image = base64.b64encode(contents).decode('utf-8')
                logger.info(f"Image size (bytes): {len(contents)}")

                image_url = f"data:image/jpeg;base64,{base64_image}"

            logger.info(f"Image URL before sending to model is {image_url}")

            # 3. Prepare messages with image_url
            image_message = {
                                "role": "user", 
                                "content": [
                                    #{"type": "text", "text": user_message},
                                    {
                                        "type": "image_url", 
                                        "image_url": {"url": image_url}
                                    }
                                ]
                            }
            
            # 4. Add image message to the conversation
            conversations.append(image_message)

            await update_message({
                "gpt_id": gpt["_id"],
                "gpt_name": gpt["name"],
                "role": "user",
                #"content": f"data:image/jpeg;base64,{base64_image}"
                "content": image_url,
                "user": gpt["user"],
                "use_case_id": gpt["use_case_id"]
            })

            token_data = await get_token_count(gpt["name"], gpt["instructions"],  conversations, user_message, int(model_configuration.max_tokens))
            logger.info(f"Token Calculation : stage 1.1 - Image analysis {token_data}")

            # 5. Call Azure OpenAI API for image analysis
            if streaming_response:
                response = await analyzeImage_stream(gpt, conversations, model_configuration, save_response_to_db)
            else:
                response = await analyzeImage_standard(gpt, conversations, model_configuration, save_response_to_db)

            logger.info(f"Image Response: {response}")

    except Exception as e:
        logger.error(f"Error occurred while processing image: {e}", exc_info=True)
        response = str(e) # Return the error message as response
    
    return response

async def processResponse(response):
    total_tokens = response.usage.total_tokens
    follow_up_questions=[]
    model_response = response.choices[0].message.content
    main_response = ""

    if model_response is not None and model_response != "" and model_response.find("follow_up_questions") != -1: 
        try:
             response_json = await extract_response(model_response) # Extract the JSON response from the model response. The model response is expected to be wrapped in triple backticks
             main_response = response_json["model_response"]
             follow_up_questions = response_json["follow_up_questions"]

            #main_response, follow_up_questions = extract_response_from_markdown(model_response)
        except Exception as e:
            logger.error(f"Error occurred while processing model response: {e}", exc_info=True)
            main_response = model_response
            follow_up_questions = [] # do not send follow-up questions in exception scenarios
    else:
        # Handle cases where the follow-up questions are missing
        main_response = model_response
        follow_up_questions = DEFAULT_FOLLOW_UP_QUESTIONS

    return main_response, follow_up_questions, total_tokens

async def generate_response(streaming_response: bool, user_message: str, model_configuration: ModelConfiguration, gpt: GPTData, uploadedFile: UploadFile = None):

    instruction_data = gpt["instructions"].split("@@@@@")
    # ALLOWED_IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg')
    has_image = False
    use_case = instruction_data[0]
    previous_conversations_count = 6
    proceed = False
    model_name = gpt["name"]
    use_rag = bool(gpt["use_rag"])
    role_information, model_configuration = await get_role_information(use_case) if use_rag else ("AI Assistant", model_configuration)
    model_configuration = ModelConfiguration(**model_configuration)

    # if gpt["name"] == "ecommerce-rag-demo":
    #     context_information = await get_data_from_azure_search(user_message, use_case)

    # Step 1 : Get last conversation history 
    #chat_history = await fetch_chat_history(gpt["_id"], model_name, limit=-1) # We need entire conversation history to be passed to the model
    chat_history = await fetch_chat_history(gpt["_id"], model_name, limit=6)
    
    # Step 3: Format the conversation to support OpenAI format (System Message, User Message, Assistant Message)
    conversations = [{"role": "system", "content": gpt["instructions"]}]
    for msg in chat_history:
        conversations.append({"role": msg["role"], "content": msg["content"]})

    # Construct the token request
    token_data = await get_token_count(model_name, gpt["instructions"],  conversations, user_message, int(model_configuration.max_tokens))
    logger.info(f"Token Calculation : stage 1 {token_data}")
    
    # Get previous conversation for context
    #previous_conversations = get_previous_context_conversations(conversation_list=conversations, previous_conversations_count=previous_conversations_count)

    # Step 5: Add the current user query to the messages Collection (Chat History). Avoid saving the query with additional grounded prompt information
    await update_message({
        "gpt_id": gpt["_id"],
        "gpt_name": gpt["name"],
        "role": "user",
        "content": f"{user_message}",
        "user": gpt["user"],
        "use_case_id": gpt["use_case_id"]
    })
        
    
    #has_image = (uploadedFile is not None and uploadedFile.filename != "blob" and uploadedFile.filename != "dummy")
    file_extension = os.path.splitext(uploadedFile.filename)[1].lower()
    if use_rag and file_extension in ALLOWED_IMAGE_EXTENSIONS:
        has_image = True
    
    if file_extension in [".pdf"]:
        use_rag = True
        await handle_upload_files(gpt["_id"], gpt, [uploadedFile])
    DEFAULT_IMAGE_RESPONSE = ""

    logger.info(f"use_rag is {use_rag}and has_image is {has_image}")
    
    # Step 6: Handle images/attachments if any or the user query
    logger.info(f"Uploaded File {uploadedFile}")
    if not use_rag and has_image:
        logger.info("CASE 1 : No RAG but Image is present")
        proceed = False
        response = await processImage(streaming_response, True, user_message, model_configuration, gpt, conversations, uploadedFile)
    elif use_rag and has_image:
        logger.info("CASE 2 : RAG and Image is present")
        proceed = True
        #Step 1 : Process the image (Always keep the stream flag as False when processing the image with RAG. Because we need 
        # full information of the image for the function calling to take a decision. Streaming will cause problems)
        conversation_for_image_analysis = []
        conversation_for_image_analysis.append({"role":"system", "content": "You are helpful AI Assistant who can analyze the given image and return the description in maximum 100 words as response."})
        image_response = await processImage(False, False, user_message, model_configuration, gpt, conversation_for_image_analysis, uploadedFile)
        conversation_for_image_analysis.clear()

        #Step 2 : Function Calling
        if image_response is not None:
            conversations.append({"role": "user", "content": user_message})
            conversations.append({"role": "assistant", "content": "Image Analysis Result : " + image_response.get("model_response")})
            await preprocessForRAG(user_message, image_response, use_case, gpt, conversations, model_configuration)
    elif use_rag and not has_image:
        logger.info("CASE 3 : RAG and No Image")
        proceed = True
        await preprocessForRAG(user_message, DEFAULT_IMAGE_RESPONSE, use_case, gpt, conversations, model_configuration)
        conversations.append({"role": "user", "content": user_message})
    else:
        logger.info("CASE 4 : No RAG and No Image")
        proceed = True
        logger.info("No function calling. Plain query used as user message")
        conversations.append({"role": "user", "content": user_message})
        
    # Step 7: Get the token count after the user message is added to the conversation
    token_data = await get_token_count(model_name, gpt["instructions"],  conversations, user_message, int(model_configuration.max_tokens))
    logger.info(f"Token Calculation : stage 2 (Before generating response) {token_data}")

    # Azure OpenAI API call
    if proceed == True:
        if streaming_response:
            response = await get_completion_from_messages_stream(gpt, model_configuration, conversations, use_case, role_information)
        else:
            response = await get_completion_from_messages_standard(gpt, model_configuration, conversations, use_case, role_information)

    # Sometimes model returns "null" which is not supported by python
    # the null gets into the chat history and ruins all the subsequent calls to the model
    # hence, we need this check
    if response is None:
        response = "No response from model"
    else:
        pass
        
    logger.info(f"Conversation : {conversations}")
    logger.info(f"Tokens in the conversation {len(token_encoder.encode(str(conversations)))}")

    # summarize the conversation history if its close to 90% of the token limit
    # if int(response["total_tokens"]) >= int(model_configuration["max_tokens"]) * 0.9:
    #     conversation_summary = await summarize_conversations(conversations, gpt)
    #     # Insert the summarization into the messages collection with role "assistant"
    #     update_message({
    #         "gpt_id": gpt["_id"],
    #         "gpt_name": gpt["name"],
    #         "role": "assistant",
    #         "content": f"Below is the summary of the previous conversations with the assistant. \n{conversation_summary}"
    #     })

    return response

async def get_data_from_azure_search(search_query: str, use_case: str, gpt_id: str, get_extra_data: bool):
    """
    # PREREQUISITES
        pip install azure-identity
        pip install azure-search-documents
    # USAGE
        python search_documents.py
    """
    logger.info("Inside fetch data from Azure Search")

    sources_formatted = ""
    additional_results_formatted = ""
    logger.info(f"Search Query: {search_query} \nUse Case: {use_case} \nGet Extra Data: {get_extra_data}")
    get_extra_data = True if get_extra_data is not None else False

    # Your MSAL app credentials (Client ID, Client Secret, Tenant ID)
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET_VALUE")
    tenant_id = os.getenv("TENANT_ID")

    logger.info(f"Client ID: {client_id} \nClient Secret: {client_secret} \nTenant ID: {tenant_id}")
    use_cases = await get_usecases(gpt_id)
    # Extract the matching use case from the collection
    use_case_data = next((uc for uc in use_cases if uc["name"] == use_case), None)

    index_name = None
    semantic_configuration_name = None
    if use_case_data:
        index_name = use_case_data.get("index_name", None)
        logger.info(f"Index Name found: {index_name}")
        semantic_configuration_name = use_case_data.get("semantic_configuration_name", None)
        logger.info(f"Semantic Configuration Name found: {semantic_configuration_name}")
    else:
        logger.warning(f"No matching Index and Semantic Configuration found for: {use_case}")

    #logger.info(f"use_case: {use_case}")

    try:
         # Use the token with Azure SDK's client
        credential = ClientSecretCredential(tenant_id, client_id, client_secret)

        # Create a search client
        azure_ai_search_client = SearchClient(
            endpoint=os.getenv("SEARCH_ENDPOINT_URL"),
            #index_name=os.getenv("SEARCH_INDEX_NAME"),
            # index_name=USE_CASE_CONFIG[use_case]["index_name"],
            index_name = index_name,
            credential=credential)
        
        if not all([client_id, client_secret, tenant_id, search_endpoint, search_index]):
            raise ValueError("Missing environment variables.")
        
        logger.info(f"Search Client: {azure_ai_search_client} \nSearch Query: {search_query}")

        # Get the documents
        if use_case == "TRACK_ORDERS_TKE" or use_case == "MANAGE_TICKETS" or use_case == "REVIEW_BYTES" or use_case == "COMPLAINTS_AND_FEEDBACK" or use_case == "SEASONAL_SALES" or use_case == "DOC_SEARCH":
            selected_fields = USE_CASE_CONFIG[use_case]["fields_to_select"]
        else:
            selected_fields = ALL_FIELDS 

        logger.info(f"Selected Fields: {selected_fields}")
        # semantic_config_name = USE_CASE_CONFIG[use_case]["semantic_configuration_name"]
        # logger.info(f"Semantic Config Name {semantic_config_name}")
        #selected_fields = ["user_name", "order_id", "product_description", "brand", "order_date", "status", "delivery_date"]
        search_results = azure_ai_search_client.search(search_text=search_query, 
                                                 #top = 5,
                                                 top=USE_CASE_CONFIG.get(use_case, {}).get("document_count", 30), 
                                                 include_total_count=True, 
                                                 query_type="semantic",
                                                #  semantic_configuration_name=USE_CASE_CONFIG[use_case]["semantic_configuration_name"],
                                                 semantic_configuration_name = semantic_configuration_name,
                                                 select=selected_fields)
        additional_search_results = []
        if get_extra_data:
            logger.info("Fetching additional data from Azure Search")
            # Create a search client
            additional_azure_ai_search_client = SearchClient(
                endpoint=os.getenv("SEARCH_ENDPOINT_URL"),
                index_name = NIA_FINOLEX_SEARCH_INDEX,
                credential=credential
            )

            additional_search_results = additional_azure_ai_search_client.search(search_text=search_query, 
                                                 top=USE_CASE_CONFIG.get(use_case, {}).get("document_count", 30), 
                                                 include_total_count=True, 
                                                 query_type="semantic",
                                                 semantic_configuration_name = NIA_FINOLEX_PDF_SEARCH_SEMANTIC_CONFIGURATION_NAME,
                                                 select=["Name_of_Supplier", "Purchase_Order_Number", "Purchase_Order_Date", "Expense_Made_For", "Quantity", "Net_Price", "Total_Expense", "Supplier_Supplying_Plant", "Currency"])
            
            logger.info(f"search endpoint url {NIA_FINOLEX_SEARCH_INDEX}\n semantic config {NIA_FINOLEX_PDF_SEARCH_SEMANTIC_CONFIGURATION_NAME}")
            
            logger.info(f"Additional Context Information: {additional_search_results}")
            additional_results_list = [result for result in additional_search_results]
            additional_results_formatted = json.dumps(additional_results_list, default=lambda x: x.__dict__, indent=2)
            logger.info(f"Additional Context Information: {additional_results_formatted}")
        
        logger.info("Documents in Azure Search:")

        # Convert SearchItemPaged to a list of dictionaries
        results_list = [result for result in search_results]

        # Serialize the results
        sources_formatted = json.dumps(results_list, default=lambda x: x.__dict__, indent=2)
        logger.info(f"Context Information: {sources_formatted}")
        
    except Exception as e:
        sources_formatted = ""
        additional_results_formatted = ""
        logger.error(f"Exception while fetching data from Azure Search {str(e)}", exc_info=True)
    
    return sources_formatted, additional_results_formatted

def get_azure_openai_deployments():
    """
    # PREREQUISITES
        pip install azure-identity
        pip install azure-mgmt-cognitiveservices
    # USAGE
        python list_deployments.py

        Before run the sample, please set the values of the client ID, tenant ID and client secret
        of the AAD application as environment variables: AZURE_CLIENT_ID, AZURE_TENANT_ID,
        AZURE_CLIENT_SECRET. For more info about how to get the value, please see:
        https://docs.microsoft.com/azure/active-directory/develop/howto-create-service-principal-portal
    """
    logger.info("Inside fetch deployments from Azure")

    try:
        client = CognitiveServicesManagementClient(
            credential=DefaultAzureCredential(),
            subscription_id=subscription_id
        )

        response = client.deployments.list(
            resource_group_name=resource_group_name,
            account_name=openai_account_name,
        )

        logger.info("Deployments in Azure:")
        for item in response:
            logger.info(item)
    except Exception as e:
        logger.error("Exception while fetching deployments from Azure OpenAI", exc_info=True)

async def summarize_conversations(chat_history, gpt):
    """
    Summarize the conversations using LLM (replace with your code)
    """
    logger.info(f"Length of chat history: {len(chat_history)}")

    gpt_name = gpt["name"]

    if chat_history is not None and len(chat_history) > 0:
        summarization_system_prompt = f"""
            You are a text summarizer. 
            Your task is to read, analyze and understand the conversations provided in the triple backticks (```) and summarize into a meaningful text.
        """

        summarization_user_prompt = f"""
            Analyze and rephrase the conversations wrapped in triple backticks (```), 
            Perform a inner monologue to understand each conversation and generate summary capturing the highlights.
            Skip any irrelevant parts in the conversation that doesn't add value.
            The summary should be detailed, informative with all the available factual data statistics and within 800 words.
            
            {delimiter} {json.dumps(chat_history)} {delimiter}
        """

        messages = [
                    {"role": "system", "content": summarization_system_prompt },
                    {"role": "user", "content": summarization_user_prompt }
                   ]

        #model_configuration: ModelConfiguration = ModelConfiguration(**SUMMARIZE_MODEL_CONFIGURATION)
        model_configuration: ModelConfiguration = model_configuration if  isinstance(model_configuration, ModelConfiguration) else ModelConfiguration(**SUMMARIZE_MODEL_CONFIGURATION)

        # Get Azure Open AI Client and fetch response
        conversation_summary = await get_completion_from_messages_default(DEFAULT_MODEL_NAME, messages, model_configuration)

        # Remove the summarized conversations from the messages collection
        delete_chat_history(gpt["_id"], gpt["name"])
        logger.info(f"Deleted chat history (post summarization) for GPT: { gpt_name} successfully.")

    return conversation_summary

async def determineFunctionCalling(search_query: str, image_response: str, use_case: str, gpt: GPTData, conversations: list, model_configuration: ModelConfiguration):
    function_calling_conversations = []
    data = []
    additional_data = []

    deployment_name = gpt["name"]
    gpt_id: str = str(gpt["_id"]) 

    logger.info(f"determineFunctionCalling calling Start {deployment_name}")
    use_case_from_db = await get_usecases(gpt_id)
    use_case_list = [use_case["name"] for use_case in use_case_from_db]

    # Azure Open AI Clients for different tasks
    azure_openai_client =  AsyncAzureOpenAI(
        azure_endpoint=GPT_4o_ENDPOINT_URL, 
        api_key=GPT_4o_API_KEY, 
        api_version=GPT_4o_API_VERSION)
    
    if use_case == "TRACKING_ORDERS_TKE":
        search_query = search_query + "(TKE)"

    # Initial user message
    function_calling_conversations.append({"role": "system", "content":FUNCTION_CALLING_SYSTEM_MESSAGE}) # Single function call
    function_calling_conversations.append({"role": "user", "content": FUNCTION_CALLING_USER_MESSAGE.format(query=search_query,use_case=use_case, conversation_history=conversations,image_details=image_response)}) # Single function call
    #messages = [{"role": "user", "content": "What's the current time in San Francisco, Tokyo, and Paris?"}] # Parallel function call with a single tool/function defined

    # Define the function for the model
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_data_from_azure_search",
                "description": "Fetch the e-commerce order related documents from Azure AI Search for the given user query",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "search_query": {
                            "type": "string",
                            "description": "The user query related to e-commerce orders, products, reviews, status, analytics etc, e.g. find all orders by Chris Miller, Summarize the reviews of product P015",
                        },
                        "use_case": {
                            "type": "string", 
                            "enum": use_case_list,
                            "description": f"The actual use case of the user query, e.g. {use_case}"
                            },
                        "get_extra_data":{
                            "type": "boolean",
                            "description": "If true, fetch the extra data from NIA Finolex Search Index. If false, fetch the data from the use case index"
                        }
                    },
                    "required": ["search_query", "use_case", "get_extra_data"],
                },
            }
        }
    ]

    response_from_function_calling_model = ""
    function_calling_model_response = ""

    try:
        # First API call: Ask the model to use the function
        response_from_function_calling_model = await azure_openai_client.chat.completions.create(
            model=GPT_4o_2_MODEL_NAME,
            messages=function_calling_conversations,
            tools=tools,
            #tool_choice="none",
            tool_choice="auto",
            #tool_choice={"type": "function", "function" : {"name"  : "get_data_from_azure_search"}}
            seed=200
        )

        logger.info(f"Full function calling response : {response_from_function_calling_model}")

        # Process the model's response
        function_calling_model_response = response_from_function_calling_model.choices[0].message
        #function_calling_conversations.append(response_message)

        # Handle function calls
        if function_calling_model_response.tool_calls:
            for tool_call in function_calling_model_response.tool_calls:
                if tool_call.function.name == "get_data_from_azure_search":
                    logger.info("get_data_from_azure_search called")
                    function_args = json.loads(tool_call.function.arguments)
                    logger.info(f"Function arguments: {function_args}")  
                    data, additional_data = await get_data_from_azure_search(
                        search_query=function_args.get("search_query"),
                        use_case=function_args.get("use_case"),
                        get_extra_data= function_args.get("get_extra_data") if use_case == "DOC_SEARCH" else False, # Only for doc search the fetch of extra data must be enabled
                        gpt_id = gpt_id
                    )

                    # Append the function response to the original conversation list
                    # conversations.append({
                    #     "tool_call_id": tool_call.id,
                    #     "role": "tool",
                    #     "name": "get_data_from_azure_search",
                    #     "content": data #data, # commenting data because it will be redundant in the conversation history as we are adding the contextual_information to sources in USER_PROMPT
                    # })
            logger.info("Function calling END")
        else:
            logger.info("No tool calls were made by the model.")

    except RateLimitError as rle:
        logger.error(f"RateLimitError occurred while calling the function: {rle}", exc_info=True)
        function_calling_model_response = "ERROR#####" + str(rle) + "Your token utilization is high (Max tokens per window 8000). Please try again later."
    except Exception as e:
        logger.error(f"Error occurred while calling the function: {e}", exc_info=True)
        function_calling_model_response = "ERROR#####" + str(e)
    finally:
        token_data = await get_token_count(gpt["name"], gpt["instructions"],  function_calling_conversations, search_query, int(model_configuration.max_tokens))
        logger.info(f"Token Calculation : stage 1.2 - Function calling {token_data}")
        function_calling_conversations.clear() # Clear the messages list because we do not need the system message, user message in this function
        logger.info(f"function_calling_model_response {function_calling_model_response}")

    return data, additional_data, conversations

# def get_azure_openai_deployments():
#     logger.info("Getting deployments from Azure OpenAI")
#     base_url = "https://management.azure.com/subscriptions/{subscriptionId}/resourceGroups/{resourceGroupName}/providers/Microsoft.CognitiveServices/accounts/{accountName}/deployments?api-version=2023-05-01"
#     url = base_url.format(subscriptionId=subscription_id, resourceGroupName=resource_group_name, accountName=openai_account_name)
    
#     # Send request
#     try:
#         response = requests.get(url, headers=headers)
#     except requests.RequestException as e:
#         raise SystemExit(f"Failed to make the request. Error: {e}")

#     # Handle the response as needed (e.g., print or process)
#     logger.info(response.json())
#     return url

# def imageAnalyzer(uploadedImage: UploadFile):
#     try:
#         # 1. Read image content
#         contents =  uploadedImage.read()

#         openai_headers = {
#             "Authorization": f"Bearer {api_key}",
#             "Content-Type": "application/json"
#         }

#         # 2. Encode as base64 for sending over API
#         base64_image = base64.b64encode(contents).decode('utf-8')

#         ENDPOINT = "https://kesav-openai.openai.azure.com/openai/deployments/gpt-4o/chat/completions?api-version=2024-02-15-preview"

#         # 3. Prepare request payload (adjust based on your model's requirements)
#         payload = {
#             "model": "gpt-4-vision-preview",  # Specify your GPT-4 Vision model
#             "messages": [ 
#                 {"role": "user", "content": [
#                     {"type": "text", "text": "Analyze this image."}, 
#                     {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}} 
#                 ]}
#             ],
#             "max_tokens": 300  # Adjust as needed
#         }

#         # 4. Send the request to OpenAI API
#         response = requests.post(ENDPOINT, headers=openai_headers, json=payload)
#         response.raise_for_status()  # Raise an error for bad status codes
#         result = response.json()

#         # 5. Process and return the response
#         response = response.choices[0].message.content
#     except requests.exceptions.RequestException as e:
#         return {"status": "error", "message": f"Request to OpenAI API failed: {str(e)}"}
#     except Exception as e:
#         return {"status": "error", "message": str(e)}
    
#     return response

async def call_maf(ticketId: str):
    client = await getAzureOpenAIClient(AZURE_ENDPOINT_URL, AZURE_OPENAI_KEY, AZURE_OPENAI_MODEL_API_VERSION, False)
    model_output = await run_conversation(client, ticketId)
    return model_output