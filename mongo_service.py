import os
import logging
import datetime as date
from bson import ObjectId
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.results import UpdateResult, InsertOneResult, DeleteResult
from pymongo.errors import DuplicateKeyError
import re

from data.GPTData import GPTData
from data.MessageData import Message
from data.Usecase import Usecase
from mongo_client import get_mongo_db
from role_mapping import SYSTEM_SAFETY_MESSAGE

logger = logging.getLogger(__name__)

ignored_content = "The requested information is not found in the retrieved data. Please try another query or topic."

# Create a unique index on the 'name' field (optional but recommended)
#gpts_collection.create_index("_id", unique=True)

async def get_collection(collection_name:str):
    mongo_collection = None

    db = await get_mongo_db() # Getting the db instance from the global pool

    if collection_name == "gpts":
        mongo_collection = db["gpts"]
    elif collection_name == "messages":
        mongo_collection = db["messages"]
    elif collection_name == "usecases":
        mongo_collection = db["usecases"]
    elif collection_name == "orders":
        mongo_collection = db["orders"]
    elif collection_name == "prompts":
        mongo_collection = db["prompts"]
    
    return mongo_collection

async def create_new_gpt(gpt: GPTData):
    # if gpts_collection.find_one({"name": gpt.name}):
    #     raise DuplicateKeyError(error="GPT with this name already exists")

    gpt_id: str = None

    if gpt is not None:
        gpts_collection = await get_collection("gpts")

        # Insert GPT data into MongoDB
        result: InsertOneResult = await gpts_collection.insert_one(vars(gpt))
        gpt_id = str(result.inserted_id)

        # Get the inserted _id
        logger.info(f"Created GPT: {gpt.name} successfully. GPT ID: {gpt_id}")

        # Update in messages table as well to maintain consistency
        await update_system_message(gpt_id, gpt.instructions)

    return gpt_id

async def update_gpt(gpt_id: str, gpt_name: str, updated_gpt: GPTData):
    result = None
    gpts_collection = await get_collection("gpts")
    gpt: GPTData = await gpts_collection.find_one({"_id": ObjectId(gpt_id)})

    if gpt is not None:
        gpt["instructions"] = updated_gpt.instructions
        gpt["use_rag"] = updated_gpt.use_rag
        gpt["user"] = updated_gpt.user
        gpt["description"] = updated_gpt.description

        # while updating gpt, update in messages table as well to maintain consistency
        result: UpdateResult = await gpts_collection.update_one(
            {"_id": ObjectId(gpt_id)}, 
            {"$set": dict(gpt)}
        )

        # Update in messages table as well to maintain consistency
        await update_system_message(gpt_id, updated_gpt.description)

    logger.info(f"Updated GPT: {gpt_name} successfully.")

    return result

async def delete_rag_use_case(gpt_id: str = None):
    is_deleted: bool = False
    
    # Get all the use cases starting with "Chat with"
    usecases_collection = await get_collection("usecases")
    if gpt_id is not None:
        existing_use_cases = await usecases_collection.find({"gpt_id": ObjectId(gpt_id), "name": {"$regex": "^DOC_SEARCH"}}).to_list(None)
    else:
        existing_use_cases = await usecases_collection.find({"name": {"$regex": "^DOC_SEARCH"}}).to_list(None)

    if existing_use_cases is not None and len(existing_use_cases) > 0:
        result: DeleteResult = await usecases_collection.delete_many({"_id": {"$in": [use_case["_id"] for use_case in existing_use_cases]}})
        logger.info(f"Deleted existing use case for RAG use case successfully : {result.deleted_count}")
        # result: DeleteResult = await delete_usecase(str(existing_use_case["_id"]))
        # logger.info(f"Step 1: Deleted existing use case for document search successfully. usecase_id : {result.deleted_count}")
        is_deleted = True
    else:
        logger.info("No existing use case found for RAG use case")
        is_deleted = False
    
    return is_deleted

async def create_usecase_for_document_search(gpt_id: str, use_case_name: str, index_name: str, semantic_configuration_name: str):
    usecases_collection = await get_collection("usecases")
    gpts_collection = await get_collection("usecases")

    use_case_created = False
    label = "DOC_SEARCH"

    use_case_document = {
        "name": label,
        "description": label,
        "instructions": "You are an AI document analysis specialist. When answering user queries, base your response solely on the retrieved documentation without adding external information. Begin by directly addressing the user's question, structuring your response in a clear, professional format. Reference specific sections or keywords from the documentation to support your points. For multi-part queries, organize with appropriate headers or numbering for clarity. If the documentation is insufficient to fully answer the query, acknowledge these limitations transparently. For ambiguous requests, ask specific clarifying questions. Present information in the user's preferred format when specified.",
        "gpt_id": ObjectId(gpt_id),
        "index_name": index_name,
        "semantic_configuration_name": semantic_configuration_name
    }

    # Step 1 : Delete the existing use case
    # Search for gpt that starts with Chat with (only one should be available per gpt)
    await delete_rag_use_case(gpt_id=gpt_id)

    # Step 2 : Insert the new use case
    result: InsertOneResult = await usecases_collection.insert_one(use_case_document)
    if result.inserted_id is not None:
        logger.info(f"Step 2: Use case created for document search for GPT: {gpt_id}. Usecase ID : {result.inserted_id}")
        use_case_created = True

        # Step 3: update the usecase id to the gpt
        result: UpdateResult = await gpts_collection.update_one(
            {"_id": ObjectId(gpt_id)},
            {"$set": {"use_case_id": result.inserted_id}}
        )
        logger.info(f"Step 3: Use case connected with GPT: {gpt_id}. Usecase ID : {result.upserted_id}")
    
    return use_case_created

async def update_gpt_instruction(gpt_id: str, gpt_name: str, usecase_id: str, loggedUser: str) -> UpdateResult:
    logger.info(f"Updating GPT instruction for GPT: {gpt_id} and {gpt_name} for usecase : {usecase_id}")

    gpts_collection = await get_collection("gpts")
    usecases_collection = await get_collection("usecases")

    # Get the use case from the usecase collection
    useCase: Usecase = await usecases_collection.find_one({"_id": ObjectId(usecase_id)})

    if useCase is None:
        logger.error(f"Use case with ID: {usecase_id} not found.")
        return None
    else:
        # get the gpt 
        gpt: GPTData = gpts_collection.find_one({"_id": ObjectId(gpt_id)})
        if gpt is not None:
            # Update the instruction in the GPT collection
            result: UpdateResult = await gpts_collection.update_one(
                {"_id": ObjectId(gpt_id)},
                {"$set": {"instructions": useCase["name"] +"@@@@@\n"+ useCase["instructions"] + "\n" + SYSTEM_SAFETY_MESSAGE, 
                          "user": loggedUser, 
                          "use_case_id": usecase_id}}
            )

            # Update in messages table as well to maintain consistency
            await update_system_message(gpt_id, useCase["instructions"])

        logger.info(f"Updated GPT instruction for GPT: {gpt_name} successfully. {result}")

        return result
    
async def delete_gpt(gpt_id: str, gpt_name: str):
    gpts_collection = await get_collection("gpts")
    result = await gpts_collection.delete_one({"_id": ObjectId(gpt_id)})

    if result.deleted_count == 1:
        # clear related chat history as well
        logger.info(f"Deleted GPT: {gpt_name} successfully.")
        await delete_chat_history(gpt_id, gpt_name)

    return result

async def delete_gpts(loggedUser: str):
     gpts_collection = await get_collection("gpts")
     result = await gpts_collection.delete_many({"user": loggedUser}) #delete all the GPTs created by the user
     #gpts_collection.delete_many({}) 

     if result.deleted_count > 0:
        logger.info(f"Deleted all GPTs successfully. Total records deleted: {result.deleted_count}")
        
        # clear related chat histories as well
        await delete_all_chat_history()

     return result

async def fetch_chat_history(gpt_id: str, gpt_name: str, limit: int): 
    """ 
        chat history with limit we use to show in the UI
        chat history without limit we use in the conversation context
    """
    messages_collection = await get_collection("messages")
    chat_history = []

    if gpt_name == "export_pdf":
        chat_history = await messages_collection.find({"gpt_id": ObjectId(gpt_id), "role" : {"$ne": "system"}, "hiddenFlag" : False}).sort("created_at", ASCENDING).to_list(None)
    else:
        if limit > 0:
            chat_history = await messages_collection.find({"gpt_id": ObjectId(gpt_id), "role" : {"$ne": "system"}, "hiddenFlag" : False}).sort("created_at", DESCENDING).limit(limit).to_list(None) #only the last 10 conversations are picked. Since we are using the same call for adding to the conversations we have the same answer repeating problem
        else:
            chat_history = await messages_collection.find({"gpt_id": ObjectId(gpt_id), "name" : {"$ne": ignored_content}, "hiddenFlag" : False}).sort("created_at", ASCENDING).to_list(None) #discard message content with ignored_content

    if chat_history is not None:
        chat_history = list(chat_history)

        # Convert ObjectId to string (_id and gpt_id)
        for chat in chat_history:
            chat["_id"] = str(chat["_id"])
            chat["gpt_id"] = str(chat["gpt_id"]) 
            chat["use_case_id"] = str(chat["use_case_id"]) 
    
        logger.info(f"Chat History Length for {gpt_name}: {len(chat_history)}")

    return chat_history

async def fetch_chat_history_for_use_case(use_case_id: str, gpt_id: str, gpt_name: str, limit: int = 10): 
    """ 
        chat history with limit we use to show in the UI
        chat history without limit we use in the conversation context
    """
    messages_collection = await get_collection("messages")
    chat_history = []
    
    chat_history = await messages_collection.find({"gpt_id": ObjectId(gpt_id), "role" : {"$ne": "system"}, "hiddenFlag" : False, "use_case_id" : use_case_id}).sort("created_at", DESCENDING).limit(limit).to_list(None) #only the last 10 conversations are picked. Since we are using the same call for adding to the conversations we have the same answer repeating problem
    logger.info(f"Chat History {chat_history}")
    if chat_history is not None:
        chat_history = list(chat_history)

        # Convert ObjectId to string (_id and gpt_id)
        for chat in chat_history:
            chat["_id"] = str(chat["_id"])
            chat["gpt_id"] = str(chat["gpt_id"]) 
            chat["use_case_id"] = str(chat["use_case_id"]) 
    
        logger.info(f"Chat History Length for {gpt_name}: {len(chat_history)}")

    return chat_history

async def delete_chat_history(gpt_id: str, gpt_name: str):
    #result = messages_collection.delete_many({"gpt_id": ObjectId(gpt_id)})
    messages_collection = await get_collection("messages")

    result: UpdateResult = await messages_collection.update_many(
            {"gpt_id": ObjectId(gpt_id)},
            {"$set": {"hiddenFlag" : True}}
        )
    
    logger.info(f"Modified count: {result.modified_count}")
    if result.modified_count > 0:
        logger.info(f"Deleted chat history for GPT: {gpt_name} successfully. Total records deleted: {result.modified_count}")
    else:
        logger.info(f"No chat history found for GPT: {gpt_name}")
    return result

async def delete_all_chat_history():
    #result = messages_collection.delete_many({})
    messages_collection = await get_collection("messages")

    result: UpdateResult = await messages_collection.update_many(
        {},  # This matches all documents
        {"$set": {"hiddenFlag": True}}  # Update to set hiddenFlag to True
    )
    
    if result.modified_count > 0:
        logger.info(f"Deleted chat history for all GPTs successfully. Total records deleted: {result.modified_count}")
    else:
        logger.info(f"No chat history found for deletion")
    return result

async def update_message(message: dict):
    """
    Update the message in the database
    """

    messages_collection = await get_collection("messages")

    # Add message to the messages Collection
    await messages_collection.insert_one({
        "gpt_id": ObjectId(message["gpt_id"]),
        "gpt_name": message["gpt_name"],
        "role": message["role"],
        "content": message["content"],
        "created_at": date.datetime.now().isoformat(),
        "hiddenFlag" : False,
        "user": message["user"],
        "use_case_id": message["use_case_id"]
    })

async def update_system_message(gpt_id: str, system_message: str) -> UpdateResult:

    logger.info(f"Updating system message for GPT ID: {gpt_id} and system message: {system_message}")

    messages_collection = await get_collection("messages")
    gpts_collection = await get_collection("gpts")

    # Get the gpt
    gpt: GPTData = await gpts_collection.find_one({"_id": ObjectId(gpt_id)})

    # fetch the respective record from the messages collection
    message: Message = await messages_collection.find_one({"gpt_id": ObjectId(gpt_id), "role": "system"})
    
    if message is None:
        # insert new record
        result: InsertOneResult = await messages_collection.insert_one({
            "gpt_id": ObjectId(gpt_id),
            "role": "system",
            "content": system_message,
            "created_at": date.datetime.now().isoformat(),
            "hiddenFlag" : False,
            "user": gpt["user"],
            "use_case_id": gpt["use_case_id"]
        })
        logger.info(f"Created New Message to update instruction for GPT ID: {gpt_id} successfully.")
        return result
        
    else:
        result: UpdateResult = await messages_collection.update_one(
            {"_id": ObjectId(message["_id"])},
            {"$set": {"content": system_message,
                      "user": gpt["user"],
                      "use_case_id": gpt["use_case_id"]}}
        )

        logger.info(f"Updated GPT instruction for GPT ID: {gpt_id} successfully.")
        return result

async def get_usecases(gpt_id: str):
    """
    Fetch the list of usecases from the "usecase" collection
    """
    usecases_collection = await get_collection("usecases")
    usecases = await usecases_collection.find({"gpt_id": ObjectId(gpt_id)}).to_list(None) 

    if usecases is not None:
        usecases = list(usecases)

        # Convert ObjectId to string (_id)
        for usecase in usecases:
            usecase["_id"] = str(usecase["_id"])
            usecase["gpt_id"] = str(usecase["gpt_id"])

    logger.info(f"Fetched usecases successfully.")

    return usecases

async def convert_json_to_mongo_format(json_data):
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

async def update_usecases(gpt_id: str, updated_use_cases: list):
    """
    Update the list of usecases in the "usecase" collection
    """
    usecases_collection = await get_collection("usecases")
    existing_use_cases = await usecases_collection.find({"gpt_id": ObjectId(gpt_id)}).to_list(None)

    if existing_use_cases is not None and len(existing_use_cases) > 0:
        # Delete the existing use cases
        await usecases_collection.delete_many({"gpt_id": ObjectId(gpt_id)})
        logger.info(f"Deleted existing usecases for {gpt_id} successfully.")

    # Insert the new list of use cases into the collection
    updated_use_cases = await convert_json_to_mongo_format(updated_use_cases)
    result = await usecases_collection.insert_many(updated_use_cases)
    logger.info(f"{result.inserted_ids} Updated usecases successfully.")

async def update_orders(orders):
    """
    Update the list of usecases in the "usecase" collection
    """
    orders_collection = await get_collection("orders")

    # Insert the new list of use cases into the collection
    orders = await convert_json_to_mongo_format(orders)
    result = await orders_collection.insert_many(orders)

    #logger.info(f"{result.inserted_ids} Updated usecases successfully.")

async def get_orders_by_user(user_name: str):
    """
    Fetch the list of orders from the "orders" collection
    """
    orders_collection = await get_collection("orders")
    orders = await orders_collection.find({"user_name": user_name}).to_list(None) 

    if orders is not None:
        orders = list(orders)

        # Convert ObjectId to string (_id)
        for order in orders:
            order["_id"] = str(order["_id"])

    logger.info(f"Fetched orders successfully.")

    return orders

async def get_orders_by_date(date: str):
    """
    Fetch the list of orders from the "orders" collection
    """
    orders_collection = await get_collection("orders")
    orders = await orders_collection.find({"order_date": date}).to_list(None)

    if orders is not None:
        orders = list(orders)

        # Convert ObjectId to string (_id)
        for order in orders:
            order["_id"] = str(order["_id"])

    logger.info(f"Fetched orders successfully.")

    return orders

async def get_order_by_id(order_id: str):
    """
    Fetch the order from the "orders" collection
    """
    orders_collection = await get_collection("orders")
    order = await orders_collection.find_one({"_id": ObjectId(order_id)}) 

    if order is not None:
        order["_id"] = str(order["_id"])

    logger.info(f"Fetched order successfully.")

    return order

async def get_gpts_for_user(username):
    gpts_collection = await get_collection("gpts")
    gpts = await gpts_collection.find({'user': username}).to_list(None) # Get all GPTs from MongoDB
    for gpt in gpts:
        gpt["_id"] = str(gpt.get("_id", "")) # Convert ObjectId to string
        gpt["use_case_id"] = str(gpt.get("use_case_id", "")) # Convert ObjectId to string or set to empty string if not available

    return gpts

async def get_gpt_by_id(gpt_id):
    gpts_collection = await get_collection("gpts")
    gpt: GPTData = await gpts_collection.find_one({"_id": ObjectId(gpt_id)})
    return gpt
