from openai import AsyncAzureOpenAI, AzureOpenAI

class NiaAzureOpenAIClient:
    _instance = None

    def __new__(cls, azure_endpoint: str, api_key: str, api_version: str, stream: bool):
        if cls._instance is None:
            cls._instance = super(NiaAzureOpenAIClient, cls).__new__(cls)
            cls._instance._initialize(azure_endpoint, api_key, api_version, stream)
        return cls._instance

    def _initialize(self, azure_endpoint: str, api_key: str, api_version: str, stream: bool):
        #if stream:
            self.client = AsyncAzureOpenAI(
                azure_endpoint=azure_endpoint,
                api_key=api_key,
                api_version=api_version,
                max_retries=0) # Turn off the max_retries (default is 2 tries)
        # else:
        #     self.client = AzureOpenAI(
        #         azure_endpoint=azure_endpoint,
        #         api_key=api_key,
        #         api_version=api_version)

    def get_azure_client(self):
        return self.client