from __future__ import annotations

import mimetypes
import os
from pathlib import Path
from typing import List

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from .jobs import JobStore


def _default_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _split_languages(raw: str) -> List[str]:
    return [lang.strip() for lang in raw.split(",") if lang.strip()]


def create_app(
    *,
    uploads_dir: str | None = None,
    output_dir: str | None = None,
    auto_start_jobs: bool | None = None,
) -> FastAPI:
    root = _default_root()
    default_uploads = Path(uploads_dir or os.environ.get("UPLOADS_DIR") or root / "to_translate")
    default_outputs = Path(output_dir or os.environ.get("OUTPUT_DIR") or root / "translations")

    app = FastAPI(title="KPS UI Service")
    app.state.jobs = JobStore(default_uploads, default_outputs)
    auto_start = auto_start_jobs
    if auto_start is None:
        env_value = os.environ.get("AUTO_START_JOBS", "true").lower()
        auto_start = env_value in {"1", "true", "yes"}
    app.state.auto_start_jobs = auto_start

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/jobs", status_code=201)
    async def submit_job(
        background_tasks: BackgroundTasks,
        file: UploadFile = File(...),
        target_languages: str = Form(...),
    ):
        langs = _split_languages(target_languages)
        if not langs:
            raise HTTPException(status_code=400, detail="target_languages must not be empty")

        payload = await file.read()
        job = app.state.jobs.create_job(
            filename=file.filename or "document",
            content=payload,
            content_type=file.content_type or "application/octet-stream",
            target_languages=langs,
        )
        if app.state.auto_start_jobs:
            app.state.jobs.enqueue(job.job_id, background_tasks)
        return {"job_id": job.job_id}

    @app.get("/jobs")
    def list_jobs():
        return [job.to_schema() for job in app.state.jobs.list_jobs()]

    @app.get("/jobs/{job_id}")
    def get_job(job_id: str):
        try:
            job = app.state.jobs.get_job(job_id)
        except KeyError as exc:  # noqa: PERF203 - explicit for clarity
            raise HTTPException(status_code=404, detail="Job not found") from exc
        return job.to_schema()

    @app.get("/jobs/{job_id}/artifacts/{language}")
    def download_artifact(job_id: str, language: str):
        try:
            job = app.state.jobs.get_job(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Job not found") from exc

        try:
            artifact_path = job.artifacts[language][0]
        except (KeyError, IndexError) as exc:
            raise HTTPException(status_code=404, detail="Artifact not found") from exc

        return FileResponse(
            path=str(artifact_path),
            media_type=mimetypes.guess_type(artifact_path.name)[0] or "application/octet-stream",
            filename=artifact_path.name,
        )

    @app.get("/jobs/{job_id}/logs")
    def stream_logs(job_id: str):
        try:
            logs = app.state.jobs.get_logs(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Job not found") from exc
        return JSONResponse({"logs": logs})

    return app


app = create_app()
