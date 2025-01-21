from pydantic import BaseModel
from datetime import datetime
from bson import ObjectId

class Message(BaseModel):
    _id: ObjectId
    gpt_id: str
    role: str  
    content: str
    #user_name: str
    created_at: str = datetime.now().isoformat()
    hiddenFlag: bool
