# Set up the query for generating responses
from azure.identity import AzureCliCredential
from azure.identity import get_bearer_token_provider
from azure.search.documents import SearchClient
from openai import AzureOpenAI
from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient

import os
from dotenv import load_dotenv # For environment variables (recommended)
load_dotenv()  # Load environment variables from .env file

credential = AzureCliCredential()
client = CognitiveServicesManagementClient(credential, os.getenv("SUBSCRIPTION_ID"))
token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")
# openai_client = AzureOpenAI(
#     api_version=os.getenv("API_VERSION"),
#     azure_endpoint=os.getenv("AZURE_ENDPOINT_URL"),
#     azure_ad_token_provider=token_provider
# )

search_client = SearchClient(
    endpoint=os.getenv("SEARCH_ENDPOINT_URL"),
    index_name=os.getenv("SEARCH_INDEX_NAME"),
    credential=credential
)

# This prompt provides instructions to the model
GROUNDED_PROMPT="""
You are a friendly assistant that helps agents and analysts answer queries about e-commerce orders.
Answer the query using only the sources provided below in a friendly and concise bulleted manner.
Answer ONLY with the facts listed in the list of sources below.
If there isn't enough information below, say you don't know.
Do not generate answers that don't use the sources below.
Query: {query}
Sources:\n{sources}
"""

# Query is the question being asked. It's sent to the search engine and the LLM.
query="Fetch orders of Chris Miller"

# Set up the search results and the chat thread.
# Retrieve the selected fields from the search index related to the question.
search_results = search_client.search(
    search_text=query,
    top=5,
    select="order_id,product_description,brand,order_date,status,delivery_date"
)
#print(f"{str(dict(search_results))}")
context_information = "\n".join([f'{document["order_id"]}:{document["product_description"]}:{document["brand"]}:{document["order_date"]}:{document["status"]}:{document["delivery_date"]}' for document in search_results])
print(f"{context_information}")
# response = openai_client.chat.completions.create(
#     messages=[
#         {
#             "role": "user",
#             "content": GROUNDED_PROMPT.format(query=query, sources=sources_formatted)
#         }
#     ],
#     model=os.getenv("ECOMMERCE_MODEL_NAME")
# )

# print(response.choices[0].message.content)