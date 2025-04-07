from pydantic import BaseModel
from datetime import datetime
from bson import ObjectId

class Usecase(BaseModel): 
    _id: ObjectId
    gpt_id: str
    name: str
    description: str
    instructions: str
    index_name: str
    semantic_configuration_name: str
    created_at: str = datetime.now().isoformat()
