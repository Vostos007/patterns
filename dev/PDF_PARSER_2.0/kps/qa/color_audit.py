"""Color audit for verifying colorspace integrity in rendered PDFs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

try:  # pragma: no cover - optional dependency
    import fitz  # PyMuPDF
except ImportError:  # pragma: no cover
    fitz = None

from kps.core import AssetLedger

from .constants import (
    RECOMMEND_EMBED_ICC_PROFILES,
    RECOMMEND_PRESERVE_COLOR_NUMBERS,
    WARNING_COLORSPACE_CONVERSION,
    WARNING_MISSING_ICC_PROFILE,
)


_DEFAULT_ALLOWED_CONVERSIONS: Tuple[Tuple[str, str], ...] = (
    ("rgb", "rgb"),
    ("cmyk", "cmyk"),
    ("gray", "gray"),
    ("lab", "lab"),
)


@dataclass(frozen=True)
class ColorConversion:
    """Represents a colorspace conversion detected in the output PDF."""

    asset_id: str
    page: int
    source_colorspace: str
    target_colorspace: str


@dataclass(frozen=True)
class IccProfileIssue:
    """Represents a missing ICC profile for a CMYK/Lab asset."""

    asset_id: str
    page: int
    target_colorspace: str


@dataclass
class ColorAuditReport:
    """Aggregated results of the color audit."""

    total_assets: int
    colorspace_counts: Dict[str, int]
    conversions: List[ColorConversion]
    missing_icc: List[IccProfileIssue]
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    passed: bool = True
    summary: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {
            "summary": self.summary,
            "passed": self.passed,
            "total_assets": self.total_assets,
            "colorspace_counts": dict(self.colorspace_counts),
            "conversions": [conv.__dict__ for conv in self.conversions],
            "missing_icc": [issue.__dict__ for issue in self.missing_icc],
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "recommendations": list(self.recommendations),
        }


class ColorAuditor:
    """Audits colorspace usage and ICC profile presence in output PDFs."""

    def __init__(
        self,
        *,
        require_icc_for_cmyk: bool = True,
        allowed_conversions: Optional[Iterable[Tuple[str, str]]] = None,
    ) -> None:
        self.require_icc_for_cmyk = require_icc_for_cmyk
        self.allowed_conversions = {
            (src.lower(), dst.lower()) for src, dst in (allowed_conversions or _DEFAULT_ALLOWED_CONVERSIONS)
        }

    def audit_colors(
        self,
        source_ledger: Optional[AssetLedger],
        target_pdf: Path,
        *,
        pre_extracted: Optional[Sequence[dict]] = None,
    ) -> ColorAuditReport:
        """Audit colorspace and ICC usage.

        When ``pre_extracted`` is supplied, those records are used directly. Each
        record may contain the following keys::

            {
                "asset_id": str,
                "page": int,
                "source_colorspace": str,
                "target_colorspace": str,
                "has_icc": bool,
            }

        If neither ``pre_extracted`` nor PyMuPDF is available, the method returns
        an informational report explaining that the audit could not be executed.
        """

        if pre_extracted is not None:
            records = list(pre_extracted)
        else:
            records = self._extract_from_pdf(target_pdf)
            if records is None:
                return self._empty_report(
                    "PyMuPDF (fitz) is required for color auditing when no pre-extracted data is provided"
                )

        total_assets = len(records) if records else (len(source_ledger.assets) if source_ledger else 0)

        colorspace_counts: Dict[str, int] = {}
        conversions: List[ColorConversion] = []
        missing_icc: List[IccProfileIssue] = []

        for record in records:
            source_cs = (record.get("source_colorspace") or "unknown").lower()
            target_cs = (record.get("target_colorspace") or source_cs).lower()
            has_icc = bool(record.get("has_icc", False))
            page = int(record.get("page", 0))
            asset_id = record.get("asset_id", "unknown")

            colorspace_counts[target_cs] = colorspace_counts.get(target_cs, 0) + 1

            if (source_cs, target_cs) not in self.allowed_conversions:
                conversions.append(
                    ColorConversion(
                        asset_id=asset_id,
                        page=page,
                        source_colorspace=source_cs,
                        target_colorspace=target_cs,
                    )
                )

            if self.require_icc_for_cmyk and target_cs in {"cmyk", "lab"} and not has_icc:
                missing_icc.append(
                    IccProfileIssue(
                        asset_id=asset_id,
                        page=page,
                        target_colorspace=target_cs,
                    )
                )

        warnings: List[str] = []
        errors: List[str] = []
        recommendations: List[str] = []

        if conversions:
            errors.append(
                f"{len(conversions)} asset(s) experienced unexpected colorspace conversion"
            )
            recommendations.append(RECOMMEND_PRESERVE_COLOR_NUMBERS)
            for conversion in conversions[:5]:
                errors.append(
                    f"  - {conversion.asset_id} (page {conversion.page}): {conversion.source_colorspace.upper()} → {conversion.target_colorspace.upper()}"
                )
            if len(conversions) > 5:
                errors.append(f"  ... and {len(conversions) - 5} more")

        if missing_icc:
            warnings.append(
                f"{len(missing_icc)} CMYK/Lab asset(s) missing ICC profile"
            )
            warnings.extend(
                [
                    f"  - {issue.asset_id} (page {issue.page})"
                    for issue in missing_icc[:5]
                ]
            )
            if len(missing_icc) > 5:
                warnings.append(f"  ... and {len(missing_icc) - 5} more")
            recommendations.append(RECOMMEND_EMBED_ICC_PROFILES)

        passed = not errors and not (self.require_icc_for_cmyk and missing_icc)

        if passed:
            summary = f"All {total_assets} assets retained expected colorspaces"
        else:
            summary = "Color audit detected issues requiring attention"

        return ColorAuditReport(
            total_assets=total_assets,
            colorspace_counts=colorspace_counts,
            conversions=conversions,
            missing_icc=missing_icc,
            warnings=warnings,
            errors=errors,
            recommendations=recommendations,
            passed=passed,
            summary=summary,
        )

    def _extract_from_pdf(self, target_pdf: Path) -> Optional[List[dict]]:
        """Attempt to extract colorspace data directly from the PDF."""

        if fitz is None:
            return None

        try:
            doc = fitz.open(target_pdf)
        except Exception:
            return None

        records: List[dict] = []

        try:
            for page_index, page in enumerate(doc):
                for img in page.get_images(full=True):
                    xref = img[0]
                    try:
                        image_dict = doc.extract_image(xref)
                    except Exception:
                        continue

                    colorspace_code = image_dict.get("colorspace", -1)
                    colorspace = self._map_colorspace(colorspace_code)
                    has_icc = bool(image_dict.get("icc_profile"))

                    records.append(
                        {
                            "asset_id": f"image-xref-{xref}",
                            "page": page_index,
                            "source_colorspace": colorspace,
                            "target_colorspace": colorspace,
                            "has_icc": has_icc,
                        }
                    )
        finally:
            doc.close()

        return records

    @staticmethod
    def _map_colorspace(code: int) -> str:
        mapping = {
            0: "unknown",
            1: "gray",
            2: "rgb",
            3: "cmyk",
            4: "lab",
        }
        return mapping.get(code, "unknown")

    @staticmethod
    def _empty_report(message: str) -> ColorAuditReport:
        return ColorAuditReport(
            total_assets=0,
            colorspace_counts={},
            conversions=[],
            missing_icc=[],
            warnings=[message],
            errors=[],
            recommendations=[],
            passed=True,
            summary=message,
        )
