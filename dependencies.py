import os
from openai import AsyncAzureOpenAI
from openai import APIConnectionError, RateLimitError
from dotenv import load_dotenv
import asyncio
import logging

load_dotenv()

# Create a logger for this module
logger = logging.getLogger(__name__)
class NiaAzureOpenAIClient:
    _instance = None
    _clients = []
    _configs = []
    _current_index = 0

    def __init__(self):
        pass  # Initialization logic is handled in async create method

    @classmethod
    async def create(cls):
        if cls._instance is None:
            cls._instance = cls()
            await cls._instance._initialize()
        return cls._instance

    async def _initialize(self):
        endpoints = self._collect_env_endpoints()

        for endpoint in endpoints:
            try:
                client = AsyncAzureOpenAI(
                    azure_endpoint=endpoint["name"],
                    api_key=endpoint["api_key"],
                    api_version=endpoint["api_version"],
                    max_retries=0
                )

                # Test connection
                await client.models.list()

                logger.info(f"Connected to Azure OpenAI: {endpoint['name']}")
                self._clients.append(client)
                self._configs.append(endpoint)

            except Exception as e:
                logger.info(f"Failed to connect to {endpoint['name']}: {str(e)}")

        if not self._clients:
            raise Exception("No available Azure OpenAI endpoints.")

    def get_azure_client(self):
        if not self._clients:
            raise ValueError("Azure clients have not been initialized.")
        return self._clients[self._current_index]

    def get_config(self):
        if not self._configs:
            raise ValueError("Azure configs have not been initialized.")
        return self._configs[self._current_index]

    async def retry_with_next_endpoint(self):
        if not self._clients:
            raise ValueError("No available clients to retry.")

        original_index = self._current_index
        total = len(self._clients)

        for _ in range(total):
            self._current_index = (self._current_index + 1) % total
            try:
                await self._clients[self._current_index].models.list()
                logger.info(f"Switched to Azure OpenAI: {self._configs[self._current_index]['name']}")
                return self._clients[self._current_index]
            except Exception as e:
                logger.info(f"Failed on retry with {self._configs[self._current_index]['name']}: {e}")
                continue

        raise Exception("All Azure OpenAI endpoints failed during retry.")

    def _collect_env_endpoints(self):
        endpoints = []

        i = 1
        while True:
            suffix = "" if i == 1 else f"_{i}"
            name = os.getenv(f"AZURE_ENDPOINT_URL{suffix}")
            api_key = os.getenv(f"OPENAI_API_KEY{suffix}")
            api_version = os.getenv(f"API_VERSION{suffix}")

            if not any([api_key, api_version]):
                break

            if all([api_key, api_version]):
                endpoints.append({
                    "name": name,
                    "api_key": api_key,
                    "api_version": api_version
                })
            else:
                logger.info(f"Incomplete config for set {i}, skipping.")

            i += 1

        return endpoints