import os
from dotenv import load_dotenv # For environment variables (recommended)
from azure.identity import DefaultAzureCredential, AzureCliCredential
from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient
import os
from azure.identity import ManagedIdentityCredential

load_dotenv()  # Load environment variables from .env file

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
        print(f"Deployment Name: {deployment.name}")
        print(f"Deployment {deployment.as_dict()}")
        deployed_model_names.append(deployment.name)

    return deployed_model_names



   