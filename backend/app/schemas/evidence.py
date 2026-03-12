from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class EvidenceOut(BaseModel):
    id: int
    billing_id: int
    original_filename: str
    file_url: str
    uploaded_at: datetime

    model_config = {"from_attributes": True}
