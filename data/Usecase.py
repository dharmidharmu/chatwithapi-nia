from pydantic import BaseModel
from datetime import datetime
from bson import ObjectId
from typing import List, Dict
class Prompt(BaseModel):
    role: str
    prompt: str
    key: str
    title: str
    user: str

class Usecase(BaseModel): 
    _id: ObjectId
    gpt_id: str
    name: str
    description: str
    instructions: str
    index_name: str
    semantic_configuration_name: str
    prompts: List[Prompt]
    created_at: str = datetime.now().isoformat()
