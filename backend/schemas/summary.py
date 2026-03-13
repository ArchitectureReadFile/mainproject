from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SummaryListItemResponse(BaseModel):
    id: int
    title: Optional[str] = None
    filename: str
    status: str
    created_at: datetime


class BatchItemResponse(BaseModel):
    filename: str
    status: str
    message: Optional[str] = None
    download_link: Optional[str] = None


class BatchResponse(BaseModel):
    batch_total: int
    results: list[BatchItemResponse]
