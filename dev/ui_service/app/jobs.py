from __future__ import annotations

import mimetypes
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from . import schemas
from .pipeline_runner import run_pipeline_job


@dataclass
class JobRecord:
    job_id: str
    status: str
    created_at: datetime
    filename: str
    content_type: str
    target_languages: List[str]
    source_path: Path
    output_dir: Path
    artifacts: Dict[str, List[Path]] = field(default_factory=dict)
    logs: List[str] = field(default_factory=list)

    def to_schema(self) -> schemas.JobStatus:
        flat_artifacts = []
        for language, paths in self.artifacts.items():
            for artifact_path in paths:
                flat_artifacts.append(
                    schemas.Artifact(
                        language=language,
                        path=str(artifact_path),
                        mime_type=mimetypes.guess_type(artifact_path.name)[0]
                        or "application/octet-stream",
                    )
                )

        download_urls = {
            language: f"/jobs/{self.job_id}/artifacts/{language}"
            for language in self.target_languages
        }

        return schemas.JobStatus(
            job_id=self.job_id,
            status=self.status,
            created_at=self.created_at,
            target_languages=self.target_languages,
            artifacts=flat_artifacts,
            download_urls=download_urls,
            logs_url=f"/jobs/{self.job_id}/logs",
        )


class JobStore:
    def __init__(
        self,
        uploads_dir: Path,
        output_dir: Path,
        pipeline_factory: Optional[Callable[[], object]] = None,
    ) -> None:
        self.uploads_dir = Path(uploads_dir)
        self.output_dir = Path(output_dir)
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._jobs: Dict[str, JobRecord] = {}
        self._pipeline_factory = pipeline_factory
        self._pipeline: Optional[object] = None

    def create_job(
        self,
        *,
        filename: Optional[str] = None,
        content: Optional[bytes] = None,
        content_type: str = "application/octet-stream",
        target_languages: List[str],
        source_path: Optional[Path] = None,
    ) -> JobRecord:
        job_id = str(uuid.uuid4())
        job_upload_dir = self.uploads_dir / job_id
        job_upload_dir.mkdir(parents=True, exist_ok=True)

        if source_path is not None:
            safe_name = filename or source_path.name
            final_source_path = job_upload_dir / safe_name
            data = Path(source_path).read_bytes()
            final_source_path.write_bytes(data)
        else:
            if content is None:
                raise ValueError("Either content or source_path must be provided")
            safe_name = filename or "document"
            final_source_path = job_upload_dir / safe_name
            final_source_path.write_bytes(content)

        record = JobRecord(
            job_id=job_id,
            status="queued",
            created_at=datetime.utcnow(),
            filename=safe_name,
            content_type=content_type,
            target_languages=target_languages,
            source_path=final_source_path,
            output_dir=self.output_dir / job_id,
        )
        self._jobs[job_id] = record
        return record

    def get_job(self, job_id: str) -> JobRecord:
        return self._jobs[job_id]

    def list_jobs(self) -> List[JobRecord]:
        return list(self._jobs.values())

    def mark_processing(self, job_id: str) -> None:
        job = self._jobs[job_id]
        job.status = "processing"
        job.logs.append("Job started")

    def mark_completed(
        self,
        job_id: str,
        artifacts: Sequence[Tuple[str, Path]] | Sequence[Path],
    ) -> None:
        job = self._jobs[job_id]
        for artifact in artifacts:
            if isinstance(artifact, tuple):
                language, path = artifact
            else:
                path = Path(artifact)
                language = path.parent.name
            job.artifacts.setdefault(language, []).append(Path(path))
        job.status = "succeeded"
        job.logs.append("Job completed")

    def mark_failed(self, job_id: str, reason: str) -> None:
        job = self._jobs[job_id]
        job.status = "failed"
        job.logs.append(reason)

    def get_logs(self, job_id: str) -> List[str]:
        return list(self._jobs[job_id].logs)

    def enqueue(self, job_id: str, background_tasks) -> None:
        background_tasks.add_task(self._execute_job, job_id)

    def _execute_job(self, job_id: str) -> None:
        job = self._jobs[job_id]
        self.mark_processing(job_id)
        try:
            pipeline = self._get_pipeline()
            artifacts = run_pipeline_job(
                pipeline=pipeline,
                job_id=job.job_id,
                source_path=job.source_path,
                target_languages=job.target_languages,
                output_root=self.output_dir,
            )
            self.mark_completed(job_id, artifacts)
        except Exception as exc:  # pragma: no cover - defensive guard
            self.mark_failed(job_id, f"Job failed: {exc}")

    def _get_pipeline(self):
        if self._pipeline is None:
            if self._pipeline_factory:
                self._pipeline = self._pipeline_factory()
            else:
                self._pipeline = None
        return self._pipeline
