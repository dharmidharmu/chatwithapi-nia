import os
from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv # For environment variables (recommended)

endpoint = os.getenv("AZURE_ENDPOINT_URL")
api_key = os.getenv("OPENAI_API_KEY")
# set the deployment name for the model we want to use
deployment = os.getenv("ECOMMERCE_MODEL_NAME")

load_dotenv()  # Load environment variables from .env file

client = AzureOpenAI(
    base_url=f"{endpoint}/openai/deployments/{deployment}/extensions",
    azure_ad_token_provider=get_bearer_token_provider(DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"),
    api_version=os.getenv("API_VERSION")
)

completion = client.chat.completions.create(
messages=[{"role": "user", "content": "What are the differences between Azure Machine Learning and Azure AI services?"}],
model=deployment,
extra_body={
    "dataSources": [
            {
                "type": "AzureCognitiveSearch",
                "parameters": {
                    "endpoint": os.getenv("SEARCH_ENDPOINT_URL"),
                    "key": os.getenv("SEARCH_KEY"),
                    "indexName": os.getenv("SEARCH_INDEX_NAME"),
                }
            }
        ]
    }
)
print(f"{completion.choices[0].message.role}: {completion.choices[0].message.content}")

# `context` is in the model_extra for Azure
print(f"\nContext: {completion.choices[0].message.model_extra['context']['messages'][0]['content']}")