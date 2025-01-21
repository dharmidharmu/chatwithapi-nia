from pydantic import BaseModel
from datetime import datetime
from bson import ObjectId

class Usecase(BaseModel): 
    _id: ObjectId
    gpt_id: str
    name: str
    description: str
    instructions: str
    created_at: str = datetime.now().isoformat()
