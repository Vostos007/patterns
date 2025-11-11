from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence
from uuid import uuid4

from fastapi import UploadFile

from .pipeline_runner import run_pipeline_job
from .schemas import Artifact, JobStatus


class JobRecord:
    def __init__(self, status: JobStatus, source_path: Path, output_dir: Path):
        self.status = status
        self.source_path = source_path
        self.output_dir = output_dir


def _build_pipeline():  # pragma: no cover
    try:
        from kps.core.unified_pipeline import PipelineConfig, UnifiedPipeline

        return UnifiedPipeline(PipelineConfig())
    except Exception as exc:
        print(f"[JobStore] Unable to load UnifiedPipeline: {exc}")
        return None


class JobStore:
    def __init__(
        self,
        uploads_dir: str,
        outputs_dir: str,
        *,
        runner=run_pipeline_job,
        auto_start: bool = True,
        pipeline_factory: Optional[Callable[[], object]] = _build_pipeline,
    ):
        self.uploads_dir = Path(uploads_dir)
        self.outputs_dir = Path(outputs_dir)
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.outputs_dir.mkdir(parents=True, exist_ok=True)
        self._jobs: Dict[str, JobRecord] = {}
        self._runner = runner
        self._auto_start = auto_start
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._pipeline = pipeline_factory() if pipeline_factory is not None else None

    def create_job(self, file: UploadFile, target_languages: List[str]) -> JobStatus:
        job_id = str(uuid4())
        job_upload_dir = self.uploads_dir / job_id
        job_upload_dir.mkdir(parents=True, exist_ok=True)
        source_path = job_upload_dir / file.filename
        with source_path.open("wb") as dest:
            dest.write(file.file.read())

        status = JobStatus(
            job_id=job_id,
            status="queued",
            target_languages=target_languages,
            source_filename=file.filename,
            artifacts=[
                Artifact(
                    language=lang,
                    file_name=f"{source_path.stem}_{lang}{source_path.suffix}",
                    download_url=f"/jobs/{job_id}/artifacts/{lang}",
                )
                for lang in target_languages
            ],
            logs_url=f"/jobs/{job_id}/logs",
        )
        record = JobRecord(status=status, source_path=source_path, output_dir=self.outputs_dir / job_id)
        self._jobs[job_id] = record

        if self._auto_start:
            self._submit_job(job_id, target_languages)

        return status

    def _submit_job(self, job_id: str, target_languages: Sequence[str]) -> None:
        record = self._jobs[job_id]
        record.status.status = "processing"

        pipeline = self._pipeline

        def task():
            try:
                paths = self._runner(
                    job_id=job_id,
                    source_path=record.source_path,
                    target_languages=target_languages,
                    output_root=record.output_dir,
                    pipeline=pipeline,
                )
                self._mark_completed(record, paths)
            except Exception as exc:  # pragma: no cover - background failures
                record.status.status = "failed"
                record.status.logs_url = str(exc)

        self._executor.submit(task)

    def _mark_completed(self, record: JobRecord, artifact_paths: Sequence[Path]) -> None:
        updated = []
        for path in artifact_paths:
            lang = path.parent.name
            updated.append(
                Artifact(
                    language=lang,
                    file_name=path.name,
                    download_url=f"/jobs/{record.status.job_id}/artifacts/{lang}",
                    status="ready",
                )
            )
        record.status.artifacts = updated
        record.status.status = "succeeded"

    def list_jobs(self) -> List[JobStatus]:
        return [record.status for record in self._jobs.values()]

    def get_job(self, job_id: str) -> JobStatus | None:
        record = self._jobs.get(job_id)
        return record.status if record else None

    def mark_completed(self, job_id: str, artifact_paths: Sequence[Path]) -> None:
        record = self._jobs[job_id]
        self._mark_completed(record, artifact_paths)
