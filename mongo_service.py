import os
import logging
import datetime as date
from bson import ObjectId
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.results import UpdateResult, InsertOneResult
from pymongo.errors import DuplicateKeyError
import re

from data.GPTData import GPTData
from data.MessageData import Message
from data.Usecase import Usecase

logger = logging.getLogger(__name__)

MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)  # Update with your MongoDB connection string 
db = client["chatbot_db"]  # Database name
gpts_collection = db["gpts"]  # Collection name
messages_collection = db["messages"] # Collection name
usecases_collection = db["usecases"] # Collection name
order_collection = db["orders"] # Collection name
ignored_content = "The requested information is not found in the retrieved data. Please try another query or topic."

DEFAULT_SYSTEM_MESSAGE = """
You are a professional and helpful AI assistant designed for e-commerce order analysis.  You have access to order, product, customer, and review data via Azure AI Search.

Your primary goal is to provide accurate and concise information based on user queries.  

Follow these guidelines:

1. **Understand the Query:** Carefully analyze the user's request to determine the specific task.
2. **Retrieve Relevant Data (using provided keywords):**  Use the provided keywords to efficiently search the data.
3. **Process and Analyze:** Extract, summarize, and analyze the retrieved data to answer the query.
4. **Structured Output:** When presenting multiple data points, use a structured format (e.g., a table or bullet points).
5. **Professional Tone:** Maintain a professional and informative tone in all responses.  Avoid casual language.
6. **Handle Missing Information:** If you cannot find the requested information, clearly state that the information is not available.  Do not fabricate information.  If possible, suggest alternative search terms or queries.
7. **Clarify Ambiguity:** If the user's request is ambiguous, ask clarifying questions to understand their intent before providing an answer.  Do not make assumptions.
8. **Avoid Unnecessary Conversation:** Focus on answering the user's query efficiently.  Do not engage in chit-chat or deviate from the task at hand.  Do not ask generic follow-up questions.  Only ask questions if they are essential to clarify the user's request.

You will receive user queries delimited by ``` characters. Keywords for Azure AI Search will be provided separately. Respond directly to the user's request.
"""


# Create a unique index on the 'name' field (optional but recommended)
#gpts_collection.create_index("_id", unique=True)

def create_new_gpt(gpt: GPTData):
    # if gpts_collection.find_one({"name": gpt.name}):
    #     raise DuplicateKeyError(error="GPT with this name already exists")

    gpt_id: str = None

    if gpt is not None:
        # Insert GPT data into MongoDB
        result: InsertOneResult = gpts_collection.insert_one(vars(gpt))

        gpt_id = str(result.inserted_id)

        # Get the inserted _id
        logger.info(f"Created GPT: {gpt.name} successfully. GPT ID: {gpt_id}")

        # Update in messages table as well to maintain consistency
        update_system_message(gpt_id, gpt.instructions)

    return gpt_id

def update_gpt(gpt_id: str, gpt_name: str, gpt: GPTData):
    # while updating gpt, update in messages table as well to maintain consistency
    result: UpdateResult = gpts_collection.update_one(
        {"_id": ObjectId(gpt_id)}, 
        {"$set": dict(gpt)}
    )

    # Update in messages table as well to maintain consistency
    update_system_message(gpt_id, gpt.instructions)
    logger.info(f"Updated GPT: {gpt_name} successfully.")

    return result

def update_gpt_instruction(gpt_id: str, gpt_name: str, usecase_id: str, loggedUser: str) -> UpdateResult:
    logger.info(f"Updating GPT instruction for GPT: {gpt_id} and {gpt_name} for usecase : {usecase_id}")
    
    # Get the use case from the usecase collection
    useCase: Usecase = usecases_collection.find_one({"_id": ObjectId(usecase_id)})

    if useCase is None:
        logger.error(f"Use case with ID: {usecase_id} not found.")
        return None
    else:
        result: UpdateResult = gpts_collection.update_one(
            {"_id": ObjectId(gpt_id)},
            {"$set": {"instructions": useCase["name"] +"@@@@@\n"+ useCase["instructions"], "user": loggedUser}}
        )

        # Update in messages table as well to maintain consistency
        update_system_message(gpt_id, useCase["instructions"])
        logger.info(f"Updated GPT instruction for GPT: {gpt_name} successfully.")

        return result
    
def delete_gpt(gpt_id: str, gpt_name: str):
    result = gpts_collection.delete_one({"_id": ObjectId(gpt_id)})

    if result.deleted_count == 1:
        # clear related chat history as well
        logger.info(f"Deleted GPT: {gpt_name} successfully.")
        delete_chat_history(gpt_id, gpt_name)

    return result

def delete_gpts(loggedUser: str):
     result = gpts_collection.delete_many({"user": loggedUser}) #delete all the GPTs created by the user
     #gpts_collection.delete_many({}) 

     if result.deleted_count > 0:
        logger.info(f"Deleted all GPTs successfully. Total records deleted: {result.deleted_count}")
        
        # clear related chat histories as well
        delete_all_chat_history()

     return result

def fetch_chat_history(gpt_id: str, gpt_name: str, limit: int): 
    """ 
        chat history with limit we use to show in the UI
        chat history without limit we use in the conversation context
    """
    if limit > 0:
        chat_history = messages_collection.find({"gpt_id": ObjectId(gpt_id), "role" : {"$ne": "system"}, "hiddenFlag" : False}).sort("created_at", DESCENDING).limit(limit) #only the last 10 conversations are picked. Since we are using the same call for adding to the conversations we have the same answer repeating problem
    else:
        chat_history = messages_collection.find({"gpt_id": ObjectId(gpt_id), "name" : {"$ne": ignored_content}, "hiddenFlag" : False}).sort("created_at", ASCENDING) #discard message content with ignored_content

    if chat_history is not None:
        chat_history = list(chat_history)

        # Convert ObjectId to string (_id and gpt_id)
        for chat in chat_history:
            chat["_id"] = str(chat["_id"])
            chat["gpt_id"] = str(chat["gpt_id"]) 
    
        logger.info(f"Chat History Length for {gpt_name}: {len(chat_history)}")

    return chat_history

def delete_chat_history(gpt_id: str, gpt_name: str):
    #result = messages_collection.delete_many({"gpt_id": ObjectId(gpt_id)})
    result: UpdateResult = messages_collection.update_many(
            {"gpt_id": ObjectId(gpt_id)},
            {"$set": {"hiddenFlag" : True}}
        )
    
    logger.info(f"Modified count: {result.modified_count}")
    if result.modified_count > 0:
        logger.info(f"Deleted chat history for GPT: {gpt_name} successfully. Total records deleted: {result.modified_count}")
    else:
        logger.info(f"No chat history found for GPT: {gpt_name}")
    return result

def delete_all_chat_history():
    #result = messages_collection.delete_many({})
    result: UpdateResult = messages_collection.update_many(
        {},  # This matches all documents
        {"$set": {"hiddenFlag": True}}  # Update to set hiddenFlag to True
    )
    
    if result.modified_count > 0:
        logger.info(f"Deleted chat history for all GPTs successfully. Total records deleted: {result.modified_count}")
    else:
        logger.info(f"No chat history found for deletion")
    return result

def update_message(message: dict):
    """
    Update the message in the database
    """
    # Add message to the messages Collection
    messages_collection.insert_one({
        "gpt_id": ObjectId(message["gpt_id"]),
        "gpt_name": message["gpt_name"],
        "role": message["role"],
        "content": message["content"],
        "created_at": date.datetime.now().isoformat(),
        "hiddenFlag" : False
    })

def update_system_message(gpt_id: str, system_message: str) -> UpdateResult:

    logger.info(f"Updating system message for GPT ID: {gpt_id} and system message: {system_message}")

    # fetch the respective record from the messages collection
    message: Message = messages_collection.find_one({"gpt_id": ObjectId(gpt_id), "role": "system"})
    
    if message is None:
        # insert new record
        result: InsertOneResult = messages_collection.insert_one({
            "gpt_id": ObjectId(gpt_id),
            "role": "system",
            "content": system_message,
            "created_at": date.datetime.now().isoformat(),
            "hiddenFlag" : False
        })
        logger.info(f"Created New Message to update instruction for GPT ID: {gpt_id} successfully.")
        return result
        
    else:
        result: UpdateResult = messages_collection.update_one(
            {"_id": ObjectId(message["_id"])},
            {"$set": {"content": system_message}}
        )

        logger.info(f"Updated GPT instruction for GPT ID: {gpt_id} successfully.")
        return result

def get_usecases(gpt_id: str):
    """
    Fetch the list of usecases from the "usecase" collection
    """
    usecases = usecases_collection.find({"gpt_id": ObjectId(gpt_id)}) 

    if usecases is not None:
        usecases = list(usecases)

        # Convert ObjectId to string (_id)
        for usecase in usecases:
            usecase["_id"] = str(usecase["_id"])
            usecase["gpt_id"] = str(usecase["gpt_id"])

    logger.info(f"Fetched usecases successfully.")

    return usecases

def convert_json_to_mongo_format(json_data):
    # Convert the json with ObjectId strings into a proper MongoDB format
    converted_data = []
    
    for item in json_data:
        converted_item = {}
        for key, value in item.items():
            if isinstance(value, str) and value.startswith("ObjectId("):
                # Extract the ID from the string and convert to ObjectId
                extracted_id = value.split("'")[1]
                converted_item[key] = ObjectId(extracted_id)
            else:
                converted_item[key] = value
        converted_data.append(converted_item)

    return converted_data

def update_usecases(use_cases):
    """
    Update the list of usecases in the "usecase" collection
    """
    # Insert the new list of use cases into the collection
    use_cases = convert_json_to_mongo_format(use_cases)
    result = usecases_collection.insert_many(use_cases)

    logger.info(f"{result.inserted_ids} Updated usecases successfully.")

def update_orders(orders):
    """
    Update the list of usecases in the "usecase" collection
    """
    # Insert the new list of use cases into the collection
    orders = convert_json_to_mongo_format(orders)
    result = order_collection.insert_many(orders)

    logger.info(f"{result.inserted_ids} Updated usecases successfully.")

def get_orders_by_user(user_name: str):
    """
    Fetch the list of orders from the "orders" collection
    """
    orders = order_collection.find({"user_name": user_name}) 

    if orders is not None:
        orders = list(orders)

        # Convert ObjectId to string (_id)
        for order in orders:
            order["_id"] = str(order["_id"])

    logger.info(f"Fetched orders successfully.")

    return orders

def get_orders_by_date(date: str):
    """
    Fetch the list of orders from the "orders" collection
    """
    orders = order_collection.find({"order_date": date}) 

    if orders is not None:
        orders = list(orders)

        # Convert ObjectId to string (_id)
        for order in orders:
            order["_id"] = str(order["_id"])

    logger.info(f"Fetched orders successfully.")

    return orders

def get_order_by_id(order_id: str):
    """
    Fetch the order from the "orders" collection
    """
    order = order_collection.find_one({"_id": ObjectId(order_id)}) 

    if order is not None:
        order["_id"] = str(order["_id"])

    logger.info(f"Fetched order successfully.")

    return order
    

    
# # Example usage:
# usecases = [{"gpt_id": gpt_id, "name": usecase_name, "system_message": system_message}, 
#             {"gpt_id": gpt_id, "name": usecase_name, "system_message": system_message}, 
#             {"gpt_id": gpt_id, "name": usecase_name, "system_message": system_message}]
# update_usecases(usecases)

''' Example Use cases to upload [{
  "name": "PREFIX",
  "description": "PREFIX",
  "instructions": "You are an intelligent virtual assistant designed to assist store employees in analyzing order, product, customer information. \nYou will be provided with customer service queries delimited with ``` characters. \n",
  "gpt_id": "ObjectId('67066030fa30a2589d669c03')"
},
{
  "name": "DATA_SET",
  "description": "DATA_SET",
  "instructions": "\n\n            [\n                order details (quantity, order_date, order_id), \n                product details (product_id, product_description, brand, price), \n                customer review (customer_rating), \n                customer information (user_name, email, phone_number, state, country),\n                delivery information (delivery_date, status, agent_contact_number) \n            ]\n        ",
  "gpt_id": "ObjectId('67066030fa30a2589d669c03')"
}]'''