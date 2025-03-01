import os
import base64
import logging
import json
import re
import requests

from fastapi import UploadFile
from openai import AzureOpenAI

from data.GPTData import GPTData
from data.ModelConfiguration import ModelConfiguration

from azure.identity import DefaultAzureCredential, ClientSecretCredential
from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient
from azure.search.documents import SearchClient

from gpt_utils import extract_response, get_previous_context_conversations
from standalone_programs.image_analyzer import analyze_image
from dotenv import load_dotenv # For environment variables (recommended)

from mongo_service import fetch_chat_history, delete_chat_history, update_message
from role_mapping import USE_CASE_CONFIG, CONTEXTUAL_PROMPT, SUMMARIZE_MODEL_CONFIGURATION, USE_CASES_LIST, FUNCTION_CALLING_SYSTEM_MESSAGE, get_role_information
from standalone_programs.simple_gpt import run_conversation, ticket_conversations, get_conversation
from routes.ilama32_routes import chat2

# from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient

load_dotenv()  # Load environment variables from .env file

# Create a logger for this module
logger = logging.getLogger(__name__)


# Model = should match the deployment name you chose for your model deployment
delimiter = "```"
default_model_name = os.getenv("DEFAULT_MODEL_NAME")
ecomm_model_name = os.getenv("ECOMMERCE_MODEL_NAME")
azure_endpoint = os.getenv("AZURE_ENDPOINT_URL")
api_key = os.getenv("OPEN_API_KEY")
api_version = os.getenv("API_VERSION")
search_endpoint = os.getenv("SEARCH_ENDPOINT_URL")
search_key = os.getenv("SEARCH_KEY")
search_index = os.getenv("SEARCH_INDEX_NAME")
review_bytes_index = os.getenv("NIA_REVIEW_BYTES_INDEX_NAME")
nia_semantic_configuration_name = os.getenv("NIA_SEMANTIC_CONFIGURATION_NAME")

gpt4o_model_name = os.getenv("GPT4O_MODEL_NAME")
gpt4o_api_key=os.getenv("GPT4O_API_KEY")
gpt4o_endpoint=os.getenv("GPT4O_ENDPOINT_URL")
gpt4o_api_version = os.getenv("GPT4O_API_VERSION")

subscription_id = os.getenv("SUBSCRIPTION_ID")
resource_group_name = os.getenv("RESOURCE_GROUP_NAME")
openai_account_name = os.getenv("OPENAI_ACCOUNT_NAME")
#previous_conversations_count = os.getenv("PREVIOUS_CONVERSATIONS_TO_CONSIDER")

DEFAULT_ERROR_RESPONSE_FROM_MODEL="The requested information is not available in the retrieved data. Please try another query or topic."
DEFAULT_FOLLOW_UP_QUESTIONS = ["I would like to know more about this topic", "I need further clarification", "Rephrase your findings"]

def getAzureOpenAIClient(azure_endpoint: str, api_key: str, api_version: str):
    logger.info(f"delimiter: {delimiter} \ndefault_model_name: {default_model_name} \necomm_model_name: {ecomm_model_name} \nazure_endpoint: {azure_endpoint} \napi_key: {api_key} \napi_version: {api_version} \nsearch_endpoint: {search_endpoint} \nsearch_key: {search_key} \nsearch_index: {search_index}")
    # Establish connection to Azure Open AI
    client = AzureOpenAI(
        azure_endpoint=azure_endpoint,
        api_key=api_key,
        api_version=api_version)
   
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
                "top_n_documents": 20,
                #"strictness": 3,
                "query_type": "semantic",
                "semantic_configuration": nia_semantic_configuration_name, #"default",
                #"role_information": instructions,
                "role_information": role_information
            }
        }]
    }
    
    logger.info(f"Extra Body for Azure Search: {extra_body}")
    
    return extra_body

async def get_completion_from_messages(model_name, model_configuration, messages, use_case, role_information):
    model_response = "No Response from Model"
    main_response = ""
    total_tokens = 0
    follow_up_questions = []

    try:
       # Get Azure Open AI Client and fetch response
        client = getAzureOpenAIClient(azure_endpoint, api_key, api_version)
        model_configuration: ModelConfiguration = ModelConfiguration(**model_configuration)

        extra_body = {}
        if model_name == "ecommerce-rag-demo" or model_name == "Nia":
            logger.info("Assigning additional search parameters for E-commerce model")
            if use_case == "REVIEW_BYTES":
                #extra_body = get_azure_search_parameters(search_endpoint, review_bytes_index, search_key, role_information, review_bytes_index_fields)
                pass
            else:
                #extra_body = get_azure_search_parameters(search_endpoint, search_index, search_key, role_information, ecomm_rag_demo_index_fields)
                pass

        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            max_tokens=model_configuration.max_tokens,
            temperature=model_configuration.temperature,
            top_p=model_configuration.top_p,
            frequency_penalty=model_configuration.frequency_penalty,
            presence_penalty=model_configuration.presence_penalty,
            stop=None,
            stream=False,
            extra_body=extra_body
        )

        # Call llama and get response
        #llama_response = await chat2("llama3.2", messages=messages)
        
        model_response = response.choices[0].message.content
        logger.info(f"Full Model Response is {response}")

        if model_response is None or model_response == "":
            model_response, main_response = "No Response from Model. Please try again."
        else:            
            main_response, follow_up_questions, total_tokens = processResponse(response) # considering as json response

    except Exception as e:
        logger.error(f"Error occurred while fetching model response: {e}", exc_info=True)
        main_response = str(e)
        
    # return modelResponse
    return {
        #"model_response": f"Open AI Response:\n {main_response} \n\n Llama Response:\n{llama_response}",
        "model_response": f"Open AI Response:\n {main_response}",
        "total_tokens": total_tokens,
        "follow_up_questions": follow_up_questions
    }

async def get_completion_from_messages_default(model_name: str, messages: list, model_configuration: ModelConfiguration):

    model_response = "No Response from Model"

    # Get Azure Open AI Client and fetch response
    client = getAzureOpenAIClient(azure_endpoint, api_key, api_version)
    model_configuration: ModelConfiguration = ModelConfiguration(**model_configuration)

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            max_tokens=model_configuration.max_tokens,
            temperature=model_configuration.temperature,
            top_p=model_configuration.top_p,
            frequency_penalty=model_configuration.frequency_penalty,
            presence_penalty=model_configuration.presence_penalty,
            stop=None,
            stream=False
        )
        logger.info(f"Default Model Response is {response}")
        model_response = response.choices[0].message.content
        #logger.info(f"Tokens used: {response.usage.total_tokens}")
    except Exception as e:
        logger.error(f"Error occurred while fetching model response: {e}", exc_info=True)
        model_response = str(e)
    
    return model_response

async def analyzeImage(model_name, messages, model_configuration):
    #logger.info(f"Conversations: {messages}")
    model_response = "No Response from Model"
    main_response = "No Response from Model"
    total_tokens = 0
    follow_up_questions = []

    # Get Azure Open AI Client and fetch response
    client = getAzureOpenAIClient(gpt4o_endpoint, gpt4o_api_key, gpt4o_api_version)
    model_configuration: ModelConfiguration = ModelConfiguration(**model_configuration)

    try:
        response = client.chat.completions.create(
            model=gpt4o_model_name,
            messages=messages,
            max_tokens=model_configuration.max_tokens,
            temperature=model_configuration.temperature,
            top_p=model_configuration.top_p,
            frequency_penalty=model_configuration.frequency_penalty,
            presence_penalty=model_configuration.presence_penalty,
            stop=None,
            stream=False
        )
        model_response = response.choices[0].message.content
        #logger.info(f"Model Response is {response}")
        #logger.info(f"Tokens used: {response.usage.total_tokens}")

        if model_response is None or model_response == "":
            model_response = "No Response from Model. Please try again."
        else:
            main_response, follow_up_questions, total_tokens = processResponse(response)

    except Exception as e:
        logger.error(f"Error occurred while fetching model response: {e}", exc_info=True)
        main_response = str(e)
    
    return {
        "model_response": main_response,
        "total_tokens": total_tokens,
        "follow_up_questions": follow_up_questions
    }

async def generate_response(user_message: str, model_configuration: ModelConfiguration, gpt: GPTData, uploadedImage: UploadFile = None):

    instruction_data = gpt["instructions"].split("@@@@@")
    use_case = instruction_data[0]
   # logger.info(f"The current usecase is {use_case}")
    role_information, model_configuration = get_role_information(use_case)
    previous_conversations_count = 6

    if gpt["name"] == "ecommerce-rag-demo" or gpt["name"] == "Nia":
        context_information = await get_data_from_azure_search(user_message, use_case)

    # Step 1 : Get last conversation history 
    chat_history = fetch_chat_history(gpt["_id"], gpt["name"], limit=-1) # We need entire conversation history to be passed to the model
    
    # Step 3: Format the conversation to support OpenAI format (System Message, User Message, Assistant Message)
    #conversations = [{"role": "system", "content": gpt["instructions"] + FUNCTION_CALLING_SYSTEM_MESSAGE}]
    conversations = [{"role": "system", "content": gpt["instructions"]}]
    for msg in chat_history:
        conversations.append({"role": msg["role"], "content": msg["content"]})

    # Get previous conversation for context
    #previous_conversations = get_previous_context_conversations(conversation_list=conversations, previous_conversations_count=previous_conversations_count)
    
    # if gpt["name"] == "ecommerce-rag-demo":
    #     context_information, conversations_from_function_calling = await determineFunctionCalling(user_message, use_case, gpt["name"])
    #     conversations.extend(conversations_from_function_calling)

    # Step 4: Append the current user query with additional context into the conversation. 
    # This additional context is only to generate the response from the model and won't be saved in the conversation history for aesthetic reasons.
    #if context_information is not None and context_information != "":
    if  gpt["name"] == "ecommerce-rag-demo" or gpt["name"] == "Nia":
        #if len(context_information) > 0:
            USER_PROMPT = USE_CASE_CONFIG[use_case]["user_message"]
            logger.info(f"USE_CASE_CONFIG[use_case]: {USER_PROMPT}")
            conversations.append({
                                    "role": "user",
                                    "content" : USER_PROMPT.format(
                                                    query=user_message, sources=context_information),
                            })
    else:
        logger.info("No function calling. Plain query used as user message")
        conversations.append({"role": "user", "content": user_message})
    
    # Step 5: Add the current user query to the messages Collection (Chat History). Avoid saving the query with additional grounded prompt information
    update_message({
        "gpt_id": gpt["_id"],
        "gpt_name": gpt["name"],
        "role": "user",
        "content": f"{user_message}", 
    })
    
    # Step 6: Handle images/attachments if any or the user query
    logger.info(f"Uploaded Image {uploadedImage}")
    if uploadedImage is not None and uploadedImage.filename != "blob" and uploadedImage.filename != "dummy":
        # 1. Read image content
        contents = await uploadedImage.read()

        # 2. Encode as base64 
        base64_image = base64.b64encode(contents).decode('utf-8')
        logger.info(f"Image size (bytes): {len(contents)}")
        
        # 3. Prepare messages with image_url
        image_message = {
                            "role": "user", 
                            "content": [
                                {
                                    "type": "image_url", 
                                    "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                                }
                            ]
                        }
        
        # 4. Add image message to the conversation
        conversations.append(image_message)

        update_message({
            "gpt_id": gpt["_id"],
            "gpt_name": gpt["name"],
            "role": "user",
            "content": f"data:image/jpeg;base64,{base64_image}"
        })

        # 5. Call Azure OpenAI API for image analysis
        response = await analyzeImage(gpt["name"], conversations, model_configuration)
    else:
        # Azure OpenAI API call
        response = await get_completion_from_messages(gpt["name"], model_configuration, conversations, use_case, role_information)

    # Sometimes model returns "null" which is not supported by python
    # the null gets into the chat history and ruins all the subsequent calls to the model
    # hence, we need this check
    if response is None:
        response = "No response from model"
    else:
        # Add response from model to the messages Collection
        update_message({
            "gpt_id": gpt["_id"],
            "gpt_name": gpt["name"],
            "role": "assistant",
            "content": response["model_response"]
        })
        
    conversations.append({"role": "assistant", "content": response["model_response"]}) 
    logger.info(f"Conversation : {conversations}")

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

def processResponse(response):
    total_tokens = response.usage.total_tokens
    follow_up_questions=[]
    model_response = response.choices[0].message.content
    main_response = ""

    if model_response is not None and model_response != "": 
        try:
            response_json = extract_response(model_response) # Extract the JSON response from the model response. The model response is expected to be wrapped in triple backticks
            main_response = response_json["model_response"]
            follow_up_questions = response_json["follow_up_questions"]
        except Exception as e:
            logger.error(f"Error occurred while processing model response: {e}", exc_info=True)
            main_response = model_response
            follow_up_questions = [] # do not send follow-up questions in exception scenarios
    else:
        # Handle cases where the follow-up questions are missing
        main_response = model_response
        follow_up_questions = DEFAULT_FOLLOW_UP_QUESTIONS

    return main_response, follow_up_questions, total_tokens

async def get_data_from_azure_search(search_query: str, use_case: str):
    """
    # PREREQUISITES
        pip install azure-identity
        pip install azure-search-documents
    # USAGE
        python search_documents.py
    """
    logger.info("Inside fetch data from Azure Search")

    sources_formatted = ""

    # Your MSAL app credentials (Client ID, Client Secret, Tenant ID)
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET_VALUE")
    tenant_id = os.getenv("TENANT_ID")

    logger.info(f"Client ID: {client_id} \nClient Secret: {client_secret} \nTenant ID: {tenant_id}")

    #logger.info(f"use_case: {use_case}")

    try:
         # Use the token with Azure SDK's client
        credential = ClientSecretCredential(tenant_id, client_id, client_secret)

        # Create a search client
        azure_ai_search_client = SearchClient(
            endpoint=os.getenv("SEARCH_ENDPOINT_URL"),
            #index_name=os.getenv("SEARCH_INDEX_NAME"),
            index_name=USE_CASE_CONFIG[use_case]["index_name"],
            credential=credential)
        
        if not all([client_id, client_secret, tenant_id, search_endpoint, search_index]):
            raise ValueError("Missing environment variables.")
        
        logger.info(f"Search Client: {azure_ai_search_client} \nSearch Query: {search_query}")

        # Get the documents
        selected_fields = USE_CASE_CONFIG[use_case]["fields_to_select"]
        logger.info(f"Selected Fields: {selected_fields}")
        #selected_fields = ["user_name", "order_id", "product_description", "brand", "order_date", "status", "delivery_date"]
        search_results = azure_ai_search_client.search(search_text=search_query, 
                                                 #top = 5,
                                                 top=USE_CASE_CONFIG[use_case]["document_count"], 
                                                 include_total_count=True, 
                                                 query_type="semantic",
                                                 semantic_configuration_name=USE_CASE_CONFIG[use_case]["semantic_configuration_name"],
                                                 select=selected_fields)
        
        logger.info("Documents in Azure Search:")
        # for doc in search_results:
        #     logger.info(doc)

        #sources_filtered = [{field: result[field] for field in selected_fields} for result in search_results]
        #sources_formatted = "\n".join([json.dumps(source) for source in sources_filtered])
        #context_information = "\n".join([f'{document["order_id"]}:{document["product_description"]}:{document["brand"]}:{document["order_date"]}:{document["status"]}:{document["delivery_date"]}' for document in search_results])

        # Convert SearchItemPaged to a list of dictionaries
        results_list = [result for result in search_results]

        # Serialize the results
        sources_formatted = json.dumps(results_list, default=lambda x: x.__dict__, indent=2)
        logger.info(f"Context Information: {sources_formatted}")
    except Exception as e:
        sources_formatted = ""
        logger.error(f"Exception while fetching data from Azure Search {str(e)}", exc_info=True)
    
    return sources_formatted

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

        model_configuration: ModelConfiguration = ModelConfiguration(**SUMMARIZE_MODEL_CONFIGURATION)

        # Get Azure Open AI Client and fetch response
        conversation_summary = await get_completion_from_messages_default(default_model_name, messages, model_configuration)

        # Remove the summarized conversations from the messages collection
        delete_chat_history(gpt["_id"], gpt["name"])
        logger.info(f"Deleted chat history (post summarization) for GPT: { gpt_name} successfully.")

    return conversation_summary

async def determineFunctionCalling(search_query: str, use_case: str, deployment_name: str):
    messages = []
    function_response = []

    # Initialize the Azure OpenAI client
    client = AzureOpenAI(
        azure_endpoint=azure_endpoint,
        api_key=api_key,
        api_version=api_version)

    # Initial user message
    messages.append({"role": "user", "content": search_query}) # Single function call
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
                            "enum": USE_CASES_LIST,
                            "description": f"The actual use case of the user query, e.g. {use_case}"
                            },
                    },
                    "required": ["search_query", "use_case"],
                },
            }  
        }
    ]

    # First API call: Ask the model to use the function
    response = client.chat.completions.create(
        model=deployment_name,
        messages=messages,
        tools=tools,
        #tool_choice="none",
        #tool_choice="auto"
        tool_choice={"type": "function", "function" : {"name"  : "get_data_from_azure_search"}}
    )

    # Process the model's response
    response_message = response.choices[0].message

    messages.clear() # Clear the messages list because we do not need the system message, user message in this function
    messages.append(response_message)

    logger.info(f"Model's response: {response_message}")

    # Handle function calls
    if response_message.tool_calls:
        for tool_call in response_message.tool_calls:
            if tool_call.function.name == "get_data_from_azure_search":
                function_args = json.loads(tool_call.function.arguments)
                logger.info(f"Function arguments: {function_args}")  
                function_response = await get_data_from_azure_search(
                    search_query=function_args.get("search_query"),
                    use_case=function_args.get("use_case")
                )

                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": "get_data_from_azure_search",
                    "content": function_response,
                })
    else:
        logger.info("No tool calls were made by the model.")  

    return function_response, messages

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

def call_maf(ticketId: str):
    client = getAzureOpenAIClient(azure_endpoint, api_key, api_version)
    model_output = run_conversation(client, ticketId)
    return model_output