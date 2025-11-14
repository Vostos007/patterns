from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class JobCreate(BaseModel):
    target_languages: List[str]


class Artifact(BaseModel):
    language: str
    path: str
    mime_type: str


class JobStatus(BaseModel):
    job_id: str
    status: str
    created_at: datetime
    target_languages: List[str]
    artifacts: List[Artifact] = Field(default_factory=list)
    download_urls: Optional[Dict[str, str]] = None
    logs_url: Optional[str] = None
