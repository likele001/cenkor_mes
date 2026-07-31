from datetime import datetime

from pydantic import BaseModel


class AttachmentOut(BaseModel):
    id: int
    uploader_id: int
    original_filename: str
    content_type: str
    size: int
    sha256: str
    created_at: datetime
    url: str

