from pydantic import BaseModel

class ModelConfiguration(BaseModel):
    max_tokens: int = 300
    temperature: float = 0.7
    top_p: float = 1
    frequency_penalty: float = 0
    presence_penalty: float = 0