from pydantic import BaseModel
from datetime import datetime
from bson import ObjectId

class GPTData(BaseModel):
    _id: ObjectId
    name: str
    description: str
    instructions: str
    use_rag: bool = False
    user: str
    use_case_id: str
    #token_count: int
    created_at: str = datetime.now().isoformat()
