import os
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.server_api import ServerApi

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = "chatbot_db"
logger = logging.getLogger(__name__)

# MongoDB Connection Pooling Class (Improved)
class MongoDB:
    def __init__(self, uri: str, db_name: str, maxPoolSize=10, minPoolSize=5):
        self.uri = uri
        self.db_name = db_name
        self.maxPoolSize = maxPoolSize
        self.minPoolSize = minPoolSize
        self._client = None  # Use a private attribute for the client
        self.db = None

    async def get_client(self): # changed connect() to get_client()
        """Get the MongoDB client (create if needed)."""
        if self._client is None:  # efficient double-checked locking 
            self._client = AsyncIOMotorClient(
                self.uri,
                maxPoolSize=self.maxPoolSize,
                minPoolSize=self.minPoolSize,
                server_api=ServerApi('1')
            )
            print(f"MongoDB connection pool created. Max: {self.maxPoolSize}, Min:{self.minPoolSize}")
        return self._client

    async def get_database(self):
        """Get the database instance."""
        if self.db is None:
            client = await self.get_client()
            self.db = client[self.db_name]
            print(f"Database '{self.db_name}' selected.") # Clearer logging

        return self.db

# Global MongoDB instance (modified)
mongo_db_instance: MongoDB = MongoDB(MONGO_URI, DB_NAME)  # Initialize immediately

async def get_mongo_db():  # changed to get_mongo_db()
    """Get the MongoDB database instance (using connection pool)."""
    global mongo_db_instance
    db = await mongo_db_instance.get_database()
    return db