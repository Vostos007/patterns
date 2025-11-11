from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class Artifact(BaseModel):
    language: str
    file_name: str
    download_url: str
    status: str = "pending"


class JobCreate(BaseModel):
    target_languages: List[str] = Field(default_factory=list)


class JobStatus(BaseModel):
    job_id: str
    status: str
    target_languages: List[str]
    source_filename: str
    artifacts: List[Artifact] = Field(default_factory=list)
    logs_url: Optional[str] = None
