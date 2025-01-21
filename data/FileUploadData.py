from pydantic import BaseModel

class FileUploadResponse(BaseModel):
    filename: str
    content_type: str
    size: int