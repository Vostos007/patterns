"""Audit trail generation for the QA suite."""

from __future__ import annotations

import json
import hashlib
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, TYPE_CHECKING

from kps.core import AssetLedger, AssetType

if TYPE_CHECKING:  # pragma: no cover
    from kps.translation.orchestrator import BatchTranslationResult, TranslationResult


class AuditTrailGenerator:
    """Aggregate pipeline metadata and QA reports into a persistent audit trail."""

    def __init__(self, pipeline_version: str = "2.0.0") -> None:
        self.pipeline_version = pipeline_version

    def generate(
        self,
        *,
        source_pdf: Path,
        output_pdf: Path,
        output_dir: Path,
        ledger: AssetLedger,
        placed_labels: Sequence[dict],
        translation_result: Optional[Any] = None,
        qa_reports: Optional[Mapping[str, object]] = None,
        extra_metadata: Optional[dict] = None,
    ) -> Dict[str, object]:
        """Produce a comprehensive audit payload."""

        qa_reports = qa_reports or {}

        audit = {
            "pipeline_version": self.pipeline_version,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": self._source_block(source_pdf, ledger),
            "extraction": self._extraction_block(ledger),
            "placement": self._placement_block(ledger, placed_labels),
            "output": self._output_block(output_pdf, output_dir),
            "qa": self._qa_block(qa_reports),
        }

        if translation_result is not None:
            audit["translation"] = self._translation_block(translation_result)

        if extra_metadata:
            audit["extra"] = extra_metadata

        return audit

    def write_json(self, audit: Dict[str, object], destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(audit, indent=2, ensure_ascii=False))

    # ------------------------------------------------------------------
    # Block builders
    # ------------------------------------------------------------------

    def _source_block(self, source_pdf: Path, ledger: AssetLedger) -> Dict[str, object]:
        info = {
            "path": str(source_pdf),
            "sha256": self._hash_file(source_pdf),
            "pages": ledger.total_pages,
        }

        try:
            info["size_bytes"] = source_pdf.stat().st_size
        except OSError:
            info["size_bytes"] = None

        return info

    def _extraction_block(self, ledger: AssetLedger) -> Dict[str, object]:
        by_type = {
            asset_type.value: len(ledger.by_type(asset_type))
            for asset_type in AssetType
        }

        completeness = ledger.completeness_check()

        captions = sum(1 for asset in ledger.assets if getattr(asset, "caption_text", None))

        return {
            "total_assets": len(ledger.assets),
            "by_type": by_type,
            "by_page": completeness.get("by_page", {}),
            "captions_detected": captions,
        }

    def _placement_block(
        self, ledger: AssetLedger, placed_labels: Sequence[dict]
    ) -> Dict[str, object]:
        total_assets = len(ledger.assets) or 1
        placed = [label for label in placed_labels if label.get("asset_id")]
        rate = len(placed) / total_assets

        return {
            "total_placed": len(placed),
            "placement_rate": rate,
            "labels_with_ids": len(placed),
        }

    def _output_block(self, output_pdf: Path, output_dir: Path) -> Dict[str, object]:
        info = {
            "pdf_path": str(output_pdf),
            "pdf_sha256": self._hash_file(output_pdf),
            "artifacts": self._list_artifacts(output_dir),
        }

        try:
            info["pdf_size_bytes"] = output_pdf.stat().st_size
        except OSError:
            info["pdf_size_bytes"] = None

        return info

    def _translation_block(self, translation_result: Any) -> Dict[str, object]:
        languages = {}
        translations = getattr(translation_result, "translations", {})
        for lang, result in translations.items():
            languages[lang] = self._translation_result_snapshot(result)

        return {
            "detected_source_language": getattr(
                translation_result, "detected_source_language", None
            ),
            "languages": languages,
            "total_cost_usd": getattr(translation_result, "total_cost", None),
            "input_tokens": getattr(translation_result, "total_input_tokens", None),
            "output_tokens": getattr(translation_result, "total_output_tokens", None),
        }

    def _qa_block(self, qa_reports: Mapping[str, object]) -> Dict[str, object]:
        summaries = {}
        for name, report in qa_reports.items():
            summaries[name] = self._serialise_report(report)
        return summaries

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _serialise_report(self, report: object) -> Dict[str, object]:
        snapshot: Dict[str, object] = {}

        passed = getattr(report, "passed", True)
        snapshot["passed"] = passed

        warnings = list(getattr(report, "warnings", []))
        errors = list(getattr(report, "errors", []))
        recommendations = list(getattr(report, "recommendations", []))

        if warnings:
            snapshot["warnings"] = warnings
        if errors:
            snapshot["errors"] = errors
        if recommendations:
            snapshot["recommendations"] = recommendations

        if hasattr(report, "metrics") and report.metrics is not None:
            metrics = report.metrics
            if hasattr(metrics, "__dict__"):
                snapshot["metrics"] = {
                    key: getattr(metrics, key)
                    for key in dir(metrics)
                    if not key.startswith("_") and not callable(getattr(metrics, key))
                }

        if hasattr(report, "to_dict"):
            snapshot["details"] = report.to_dict()  # type: ignore[attr-defined]
        elif is_dataclass(report):
            snapshot["details"] = asdict(report)

        return snapshot

    def _translation_result_snapshot(self, result: Any) -> Dict[str, object]:
        segments = getattr(result, "segments", None)
        count = len(segments) if segments is not None else None
        return {
            "segments_translated": count,
        }

    def _hash_file(self, path: Path) -> Optional[str]:
        if not path.exists() or not path.is_file():
            return None

        sha = hashlib.sha256()
        try:
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(8192), b""):
                    sha.update(chunk)
        except OSError:
            return None

        return sha.hexdigest()

    def _list_artifacts(self, output_dir: Path) -> Iterable[str]:
        if not output_dir.exists():
            return []

        artifacts: List[str] = []
        for path in sorted(output_dir.glob("**/*")):
            if path.is_file():
                try:
                    artifacts.append(str(path.relative_to(output_dir)))
                except ValueError:
                    artifacts.append(str(path))
        return artifacts
