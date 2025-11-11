from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Sequence
import shutil

try:  # pragma: no cover
    from kps.core.unified_pipeline import PipelineConfig, UnifiedPipeline
except ImportError:  # pragma: no cover
    UnifiedPipeline = None  # type: ignore
    PipelineConfig = None  # type: ignore


def _default_pipeline():  # pragma: no cover
    if UnifiedPipeline and PipelineConfig:
        return UnifiedPipeline(PipelineConfig())
    return None


def run_pipeline_job(
    *,
    job_id: str,
    source_path: Path,
    target_languages: Sequence[str],
    output_root: Path,
    pipeline=None,
) -> List[Path]:
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    pipeline = pipeline or _default_pipeline()

    artifact_paths: List[Path] = []
    if pipeline is not None:
        result = pipeline.process(
            input_file=source_path,
            target_languages=list(target_languages),
            output_dir=output_root,
        )
        for lang, file_path in result.output_files.items():
            src = Path(file_path)
            dest = output_root / lang / src.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            artifact_paths.append(dest)
    else:
        for lang in target_languages:
            dest = output_root / lang / f"{source_path.stem}_{lang}{source_path.suffix}"
            with dest.open("w", encoding="utf-8") as fh:
                fh.write(f"Placeholder translation for {lang}\n")
            artifact_paths.append(dest)
    return artifact_paths
