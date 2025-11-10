"""Fail-closed QA orchestrator that combines all individual checks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from kps.core import AssetLedger

from .audit_trail import AuditTrailGenerator
from .color_audit import ColorAuditor
from .completeness_checker import CompletenessChecker
from .dpi_validator import DPIValidator
from .font_audit import FontAuditor
from .geometry_validator import GeometryValidator
from .visual_diff import VisualDiffer, VisualDiffReport


@dataclass
class QAPipelineResult:
    """Final outcome of the QA pipeline."""

    passed: bool
    qa_reports: Dict[str, object]
    audit: Dict[str, object]
    failed_check: Optional[str] = None


class QAPipeline:
    """Coordinate the individual QA checks in a fail-closed fashion."""

    def __init__(
        self,
        *,
        completeness_checker: Optional[CompletenessChecker] = None,
        geometry_validator: Optional[GeometryValidator] = None,
        visual_differ: Optional[VisualDiffer] = None,
        dpi_validator: Optional[DPIValidator] = None,
        font_auditor: Optional[FontAuditor] = None,
        color_auditor: Optional[ColorAuditor] = None,
        audit_generator: Optional[AuditTrailGenerator] = None,
    ) -> None:
        self.completeness_checker = completeness_checker or CompletenessChecker()
        self.geometry_validator = geometry_validator
        self.visual_differ = visual_differ
        self.dpi_validator = dpi_validator
        self.font_auditor = font_auditor
        self.color_auditor = color_auditor
        self.audit_generator = audit_generator or AuditTrailGenerator()

    def run(
        self,
        *,
        source_pdf: Path,
        reference_pdf: Optional[Path],
        output_pdf: Path,
        output_dir: Path,
        ledger: AssetLedger,
        placed_labels: Sequence[dict],
        page_dimensions: Optional[Sequence[tuple]] = None,
        translation_result: Optional[Any] = None,
        audit_path: Optional[Path] = None,
        extra_metadata: Optional[dict] = None,
    ) -> QAPipelineResult:
        qa_reports: Dict[str, object] = {}

        # Completeness check (always required)
        completeness_report = self.completeness_checker.check_completeness(
            source_ledger=ledger,
            output_pdf=output_pdf,
            placed_labels=placed_labels,
        )
        qa_reports["completeness"] = completeness_report
        if not completeness_report.passed:
            return self._finalise(
                qa_reports,
                failed_check="completeness",
                source_pdf=source_pdf,
                output_pdf=output_pdf,
                output_dir=output_dir,
                ledger=ledger,
                placed_labels=placed_labels,
                translation_result=translation_result,
                audit_path=audit_path,
                extra_metadata=extra_metadata,
            )

        # Geometry validator (optional)
        if self.geometry_validator is not None:
            geometry_report = self.geometry_validator.validate_geometry(
                source_ledger=ledger,
                placed_labels=list(placed_labels),
            )
            qa_reports["geometry"] = geometry_report
            if not geometry_report.passed:
                return self._finalise(
                    qa_reports,
                    failed_check="geometry",
                    source_pdf=source_pdf,
                    output_pdf=output_pdf,
                    output_dir=output_dir,
                    ledger=ledger,
                    placed_labels=placed_labels,
                    translation_result=translation_result,
                    audit_path=audit_path,
                    extra_metadata=extra_metadata,
                )

        # Visual diff (requires reference PDF and differ)
        if self.visual_differ is not None and reference_pdf is not None and page_dimensions is not None:
            visual_passed, page_reports = self.visual_differ.compare_documents(
                source_pdf=reference_pdf,
                target_pdf=output_pdf,
                ledger=ledger,
                page_dimensions=page_dimensions,
                return_diff_images=False,
            )
            visual_report = self._summarise_visual_diff(visual_passed, page_reports)
            qa_reports["visual_diff"] = visual_report
            if not visual_report.passed:
                return self._finalise(
                    qa_reports,
                    failed_check="visual_diff",
                    source_pdf=source_pdf,
                    output_pdf=output_pdf,
                    output_dir=output_dir,
                    ledger=ledger,
                    placed_labels=placed_labels,
                    translation_result=translation_result,
                    audit_path=audit_path,
                    extra_metadata=extra_metadata,
                )

        # DPI validation
        if self.dpi_validator is not None:
            dpi_report = self.dpi_validator.validate_dpi(
                pdf_path=output_pdf,
                source_ledger=ledger,
                placed_labels=list(placed_labels),
            )
            qa_reports["dpi"] = dpi_report
            if not dpi_report.passed:
                return self._finalise(
                    qa_reports,
                    failed_check="dpi",
                    source_pdf=source_pdf,
                    output_pdf=output_pdf,
                    output_dir=output_dir,
                    ledger=ledger,
                    placed_labels=placed_labels,
                    translation_result=translation_result,
                    audit_path=audit_path,
                    extra_metadata=extra_metadata,
                )

        if self.font_auditor is not None:
            font_report = self.font_auditor.audit_fonts(output_pdf)
            qa_reports["font"] = font_report
            if not font_report.passed:
                return self._finalise(
                    qa_reports,
                    failed_check="font",
                    source_pdf=source_pdf,
                    output_pdf=output_pdf,
                    output_dir=output_dir,
                    ledger=ledger,
                    placed_labels=placed_labels,
                    translation_result=translation_result,
                    audit_path=audit_path,
                    extra_metadata=extra_metadata,
                )

        if self.color_auditor is not None:
            color_report = self.color_auditor.audit_colors(
                source_ledger=ledger,
                target_pdf=output_pdf,
            )
            qa_reports["color"] = color_report
            if not color_report.passed:
                return self._finalise(
                    qa_reports,
                    failed_check="color",
                    source_pdf=source_pdf,
                    output_pdf=output_pdf,
                    output_dir=output_dir,
                    ledger=ledger,
                    placed_labels=placed_labels,
                    translation_result=translation_result,
                    audit_path=audit_path,
                    extra_metadata=extra_metadata,
                )

        # All checks passed
        return self._finalise(
            qa_reports,
            failed_check=None,
            source_pdf=source_pdf,
            output_pdf=output_pdf,
            output_dir=output_dir,
            ledger=ledger,
            placed_labels=placed_labels,
            translation_result=translation_result,
            audit_path=audit_path,
            extra_metadata=extra_metadata,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _summarise_visual_diff(
        self,
        passed: bool,
        page_reports: Sequence[VisualDiffReport],
    ) -> object:
        total_pages = len(page_reports)
        failing_pages = [report for report in page_reports if not report.passed]

        warnings = []
        recommendations = []
        for report in failing_pages:
            warnings.extend(getattr(report, "warnings", []))
            recommendations.extend(getattr(report, "recommendations", []))

        class VisualDiffSummary:
            def __init__(self, passed, total_pages, failing_pages, warnings, recommendations):
                self.passed = passed
                self.total_pages = total_pages
                self.failing_pages = failing_pages
                self.warnings = warnings
                self.recommendations = recommendations

            def to_dict(self):
                return {
                    "passed": self.passed,
                    "total_pages": self.total_pages,
                    "failing_pages": [
                        {
                            "page": getattr(report, "page_index", idx),
                            "warnings": getattr(report, "warnings", []),
                        }
                        for idx, report in enumerate(self.failing_pages)
                    ],
                }

        return VisualDiffSummary(passed, total_pages, failing_pages, warnings, recommendations)

    def _finalise(
        self,
        qa_reports: Dict[str, object],
        *,
        failed_check: Optional[str],
        source_pdf: Path,
        output_pdf: Path,
        output_dir: Path,
        ledger: AssetLedger,
        placed_labels: Sequence[dict],
        translation_result: Optional[Any],
        audit_path: Optional[Path],
        extra_metadata: Optional[dict],
    ) -> QAPipelineResult:
        audit_payload = self.audit_generator.generate(
            source_pdf=source_pdf,
            output_pdf=output_pdf,
            output_dir=output_dir,
            ledger=ledger,
            placed_labels=placed_labels,
            translation_result=translation_result,
            qa_reports=qa_reports,
            extra_metadata=extra_metadata,
        )

        if audit_path is None:
            audit_path = output_dir / "audit.json"

        self.audit_generator.write_json(audit_payload, audit_path)

        passed = failed_check is None
        return QAPipelineResult(
            passed=passed,
            qa_reports=qa_reports,
            audit=audit_payload,
            failed_check=failed_check,
        )
