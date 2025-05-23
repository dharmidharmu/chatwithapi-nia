from pydantic import BaseModel


class InputPrompt(BaseModel):
    prompt: str