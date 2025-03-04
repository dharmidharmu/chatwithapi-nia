from pydantic import BaseModel
from datetime import datetime
from bson import ObjectId

class Message(BaseModel):
    _id: ObjectId
    gpt_id: str
    role: str  
    content: str
    use_case_id: str
    user_name: str
    created_at: str = datetime.now().isoformat()
    hiddenFlag: bool
