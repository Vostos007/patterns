from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .jobs import JobStore
from .schemas import JobStatus


DEFAULT_UPLOADS = Path("/tmp/kps_uploads")
DEFAULT_OUTPUTS = Path("/tmp/kps_outputs")


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() not in {"0", "false", "no", "off"}


def create_app(
    uploads_dir: str | Path = DEFAULT_UPLOADS,
    output_dir: str | Path = DEFAULT_OUTPUTS,
    cors_origins: Optional[List[str]] = None,
    auto_start_jobs: Optional[bool] = None,
    pipeline_factory=None,
) -> FastAPI:
    app = FastAPI(title="KPS UI Service", version="0.1.0")

    auto_start = auto_start_jobs if auto_start_jobs is not None else _env_bool("AUTO_START_JOBS", True)
    app.state.jobs = JobStore(
        str(uploads_dir),
        str(output_dir),
        auto_start=auto_start,
        pipeline_factory=pipeline_factory,
    )

    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/jobs", status_code=201)
    async def create_job(
        file: UploadFile = File(...),
        target_languages: str = Form("en"),
    ) -> dict:
        languages = [lang.strip() for lang in target_languages.split(",") if lang.strip()]
        if not languages:
            raise HTTPException(status_code=422, detail="target_languages required")
        job = app.state.jobs.create_job(file=file, target_languages=languages)
        return {"job_id": job.job_id}

    @app.get("/jobs", response_model=List[JobStatus])
    def list_jobs():
        return app.state.jobs.list_jobs()

    @app.get("/jobs/{job_id}", response_model=JobStatus)
    def get_job(job_id: str):
        job = app.state.jobs.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job

    @app.get("/jobs/{job_id}/artifacts/{language}")
    def download(job_id: str, language: str):
        job = app.state.jobs.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        record = app.state.jobs._jobs[job_id]
        artifact_path = record.output_dir / language
        if not artifact_path.exists():
            raise HTTPException(status_code=404, detail="Artifact unavailable")
        files = list(artifact_path.glob("*"))
        if not files:
            raise HTTPException(status_code=404, detail="Artifact pending")
        return FileResponse(files[0])

    return app


app = create_app()
