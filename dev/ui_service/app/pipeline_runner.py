"""Utilities for executing KPS pipeline jobs."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Iterable, List, Optional, Sequence, Tuple


class PipelineProtocol:
    """Protocol-like helper describing the pipeline interface we rely on."""

    def process(self, input_file: str, target_languages: Sequence[str], output_dir: str):  # pragma: no cover - documentation only
        """Execute pipeline run."""


def _load_pipeline():
    if os.getenv("KPS_PIPELINE_IMPLEMENTATION", "real").lower() == "stub":
        return StubPipeline()

    from kps.core import UnifiedPipeline  # Lazy import to avoid heavy startup when unused

    return UnifiedPipeline()


class StubPipeline:
    """Lightweight dev pipeline that mirrors input into language folders."""

    def process(self, input_file: str, target_languages: Sequence[str], output_dir: str):
        output_files: dict[str, dict[str, str]] = {}
        source_path = Path(input_file)
        for language in target_languages:
            lang_dir = Path(output_dir) / language
            lang_dir.mkdir(parents=True, exist_ok=True)
            dest = lang_dir / f"{source_path.stem}_{language.upper()}{source_path.suffix or '.pdf'}"
            shutil.copyfile(source_path, dest)
            output_files.setdefault(language, {})["pdf"] = str(dest)
        return SimpleNamespace(output_files=output_files)


def run_pipeline_job(
    *,
    pipeline: Optional[PipelineProtocol],
    job_id: str,
    source_path: Path,
    target_languages: Sequence[str],
    output_root: Path,
) -> List[Tuple[str, Path]]:
    """Run the document pipeline and collect artifact paths per language."""

    job_output_dir = Path(output_root) / job_id
    job_output_dir.mkdir(parents=True, exist_ok=True)

    pipeline_instance = pipeline or _load_pipeline()
    result = pipeline_instance.process(
        input_file=str(source_path),
        target_languages=list(target_languages),
        output_dir=str(job_output_dir),
    )

    artifact_map = []
    output_files = getattr(result, "output_files", {}) if result else {}
    for language, files in output_files.items():
        values: Iterable[str]
        if isinstance(files, dict):
            values = files.values()
        else:
            values = files
        for file_path in values:
            artifact_map.append((language, Path(file_path)))

    return artifact_map
