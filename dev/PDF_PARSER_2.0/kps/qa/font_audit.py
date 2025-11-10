"""Font audit system for KPS v2.0 QA Suite.

Validates font embedding and subsetting in output PDF:
- Lists all fonts used
- Checks embedding status (embedded vs referenced)
- Checks subsetting (full vs subset)
- Detects missing/referenced fonts
- Ensures PDF/X compliance

Part of Day 5: DPI Validator and Font Audit
"""

from dataclasses import dataclass, field
from typing import List, Set, Dict, Optional, TYPE_CHECKING
from pathlib import Path

try:  # pragma: no cover - optional dependency
    import fitz  # PyMuPDF
except ImportError:  # pragma: no cover
    fitz = None

if TYPE_CHECKING:  # pragma: no cover
    from fitz import Document


@dataclass
class FontInfo:
    """Information about single font in PDF."""

    name: str  # Font name (may include subset prefix)
    base_name: str  # Clean name without subset prefix
    font_type: str  # TrueType, Type1, Type0, CIDFont, etc.
    is_embedded: bool  # True if font data is in PDF
    is_subset: bool  # True if only used glyphs included
    encoding: str  # Font encoding
    pages_used: Set[int]  # Pages where font appears
    xref: int  # PDF object reference

    # Additional metadata
    glyph_count: Optional[int] = None  # Number of glyphs (if available)
    file_size: Optional[int] = None  # Font data size in bytes

    def __post_init__(self):
        """Extract base name and detect subsetting."""
        # Subset fonts have prefix like "ABCDEF+" or "ABCDEF_"
        if '+' in self.name:
            parts = self.name.split('+', 1)
            if len(parts) == 2 and len(parts[0]) == 6:
                self.is_subset = True
                self.base_name = parts[1]
            else:
                self.base_name = self.name
        elif self.name.count('_') == 1:
            parts = self.name.split('_', 1)
            if len(parts[0]) == 6:
                self.is_subset = True
                self.base_name = parts[1]
            else:
                self.base_name = self.name
        else:
            self.base_name = self.name

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "base_name": self.base_name,
            "type": self.font_type,
            "embedded": self.is_embedded,
            "subset": self.is_subset,
            "encoding": self.encoding,
            "pages": sorted(list(self.pages_used)),
            "xref": self.xref,
            "glyph_count": self.glyph_count,
            "file_size_bytes": self.file_size,
        }

    def __str__(self) -> str:
        """Human-readable string."""
        status = []
        if self.is_embedded:
            status.append("embedded")
        else:
            status.append("REFERENCED")

        if self.is_subset:
            status.append("subset")
        else:
            status.append("full")

        return (
            f"{self.base_name} [{self.font_type}] - "
            f"{', '.join(status)} - "
            f"pages {sorted(list(self.pages_used))}"
        )


@dataclass
class FontReport:
    """Font audit report."""

    total_fonts: int
    embedded_fonts: int
    subset_fonts: int
    referenced_fonts: int  # Not embedded (critical issue)

    fonts: List[FontInfo]
    missing_fonts: List[FontInfo]  # Referenced/not embedded

    # Font type breakdown
    font_types: Dict[str, int]

    # Pass/fail
    passed: bool  # True if all fonts embedded
    pdf_x_compliant: bool  # True if all fonts embedded and subset

    # Feedback
    errors: List[str]
    warnings: List[str]
    recommendations: List[str]
    summary: str

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "summary": self.summary,
            "passed": self.passed,
            "pdf_x_compliant": self.pdf_x_compliant,
            "statistics": {
                "total_fonts": self.total_fonts,
                "embedded_fonts": self.embedded_fonts,
                "subset_fonts": self.subset_fonts,
                "referenced_fonts": self.referenced_fonts,
                "font_types": self.font_types,
            },
            "fonts": [font.to_dict() for font in self.fonts],
            "missing_fonts": [font.to_dict() for font in self.missing_fonts],
            "errors": self.errors,
            "warnings": self.warnings,
            "recommendations": self.recommendations,
        }

    def print_report(self) -> str:
        """Generate human-readable report."""
        lines = []
        lines.append("=" * 80)
        lines.append("FONT AUDIT REPORT")
        lines.append("=" * 80)
        lines.append("")

        lines.append(f"Status: {'✓ PASSED' if self.passed else '✗ FAILED'}")
        lines.append(f"PDF/X Compliant: {'✓ YES' if self.pdf_x_compliant else '✗ NO'}")
        lines.append("")

        lines.append(f"Total Fonts: {self.total_fonts}")
        lines.append(f"  - Embedded: {self.embedded_fonts}")
        lines.append(f"  - Subset: {self.subset_fonts}")
        lines.append(f"  - Referenced (not embedded): {self.referenced_fonts}")
        lines.append("")

        if self.font_types:
            lines.append("Font Types:")
            for ftype, count in sorted(self.font_types.items()):
                lines.append(f"  - {ftype}: {count}")
            lines.append("")

        if self.errors:
            lines.append("ERRORS:")
            for error in self.errors:
                lines.append(f"  ✗ {error}")
            lines.append("")

        if self.warnings:
            lines.append("WARNINGS:")
            for warning in self.warnings:
                lines.append(f"  ⚠ {warning}")
            lines.append("")

        if self.fonts:
            lines.append("FONT DETAILS:")
            for font in sorted(self.fonts, key=lambda f: f.base_name):
                status = "✓" if font.is_embedded else "✗"
                lines.append(f"  {status} {font}")
            lines.append("")

        if self.recommendations:
            lines.append("RECOMMENDATIONS:")
            for rec in self.recommendations:
                lines.append(f"  → {rec}")
            lines.append("")

        lines.append(self.summary)
        lines.append("=" * 80)

        return "\n".join(lines)


class FontAuditor:
    """Audit font usage and embedding in PDF.

    Validates that all fonts are properly embedded and subset
    for print production and PDF/X compliance.
    """

    def __init__(self, require_subsetting: bool = False):
        """Initialize font auditor.

        Args:
            require_subsetting: If True, warn about non-subset fonts
        """
        self.require_subsetting = require_subsetting

    def audit_fonts(
        self,
        pdf_path: Path,
        *,
        pre_extracted: Optional[List[dict]] = None,
    ) -> FontReport:
        """Audit all fonts in PDF.

        Args:
            pdf_path: Path to PDF file
            pre_extracted: Optional pre-parsed font metadata. When provided the
                PDF will not be opened and the supplied data is used instead.

        Returns:
            FontReport with font details and issues
        """
        if pre_extracted is not None:
            fonts = [
                FontInfo(
                    name=record["name"],
                    base_name=record.get("base_name", record["name"]),
                    font_type=record.get("font_type", "Unknown"),
                    is_embedded=record.get("is_embedded", False),
                    is_subset=record.get("is_subset", False),
                    encoding=record.get("encoding", "Unknown"),
                    pages_used=set(record.get("pages", [])),
                    xref=record.get("xref", 0),
                    glyph_count=record.get("glyph_count"),
                    file_size=record.get("file_size"),
                )
                for record in pre_extracted
            ]
            return self._generate_report(fonts)

        if fitz is None:
            return self._empty_report(
                "PyMuPDF (fitz) is required to audit fonts unless pre_extracted data is supplied"
            )

        try:
            doc = fitz.open(pdf_path)
        except Exception as e:
            return self._empty_report(f"Failed to open PDF: {e}")

        # Collect fonts from all pages
        fonts_dict: Dict[str, FontInfo] = {}

        for page_num in range(len(doc)):
            page = doc[page_num]

            # Get fonts on this page
            try:
                font_list = page.get_fonts(full=True)
            except Exception as e:
                continue

            for font_tuple in font_list:
                # Font tuple format (from PyMuPDF):
                # (xref, ext, type, basefont, name, encoding, embedded)
                if len(font_tuple) < 6:
                    continue

                xref = font_tuple[0]
                font_type = font_tuple[2]
                name = font_tuple[3] or font_tuple[4] or "Unknown"
                encoding = font_tuple[5] if len(font_tuple) > 5 else "Unknown"

                # Check if embedded
                is_embedded = self._is_font_embedded(doc, xref)

                # Create or update font info
                if name not in fonts_dict:
                    fonts_dict[name] = FontInfo(
                        name=name,
                        base_name=name,  # Will be updated in __post_init__
                        font_type=font_type,
                        is_embedded=is_embedded,
                        is_subset=False,  # Will be detected in __post_init__
                        encoding=encoding,
                        pages_used=set(),
                        xref=xref,
                    )

                    # Try to get font size
                    try:
                        fonts_dict[name].file_size = self._get_font_size(doc, xref)
                    except:
                        pass

                fonts_dict[name].pages_used.add(page_num)

        doc.close()

        fonts = list(fonts_dict.values())

        # Generate report
        return self._generate_report(fonts)

    def _is_font_embedded(self, doc: "Document", xref: int) -> bool:
        """Check if font is embedded in PDF.

        Args:
            doc: PyMuPDF document
            xref: Font object reference

        Returns:
            True if font data is embedded
        """
        try:
            # Check for font file streams
            for key in ["FontFile", "FontFile2", "FontFile3"]:
                font_file = doc.xref_get_key(xref, key)
                if font_file and font_file != "null":
                    return True

            # Check if font descriptor has embedded data
            desc_xref = doc.xref_get_key(xref, "FontDescriptor")
            if desc_xref and desc_xref != "null":
                # Extract xref number
                desc_num = int(desc_xref.split()[0]) if ' ' in desc_xref else int(desc_xref)

                for key in ["FontFile", "FontFile2", "FontFile3"]:
                    font_file = doc.xref_get_key(desc_num, key)
                    if font_file and font_file != "null":
                        return True

            return False
        except:
            # If we can't determine, assume not embedded (safer)
            return False

    def _get_font_size(self, doc: "Document", xref: int) -> Optional[int]:
        """Get embedded font data size in bytes.

        Args:
            doc: PyMuPDF document
            xref: Font object reference

        Returns:
            Size in bytes, or None
        """
        try:
            # Try to get font stream length
            for key in ["FontFile", "FontFile2", "FontFile3"]:
                font_file = doc.xref_get_key(xref, key)
                if font_file and font_file != "null":
                    # Get stream object
                    stream_xref = int(font_file.split()[0]) if ' ' in font_file else int(font_file)
                    length_str = doc.xref_get_key(stream_xref, "Length")
                    if length_str:
                        return int(length_str.split()[0])
            return None
        except:
            return None

    def _generate_report(self, fonts: List[FontInfo]) -> FontReport:
        """Generate comprehensive font report.

        Args:
            fonts: List of font info objects

        Returns:
            FontReport with statistics and recommendations
        """
        if not fonts:
            return self._empty_report("No fonts found in PDF")

        # Calculate statistics
        embedded_count = sum(1 for f in fonts if f.is_embedded)
        subset_count = sum(1 for f in fonts if f.is_subset)
        referenced_count = sum(1 for f in fonts if not f.is_embedded)

        missing = [f for f in fonts if not f.is_embedded]

        # Font type breakdown
        font_types: Dict[str, int] = {}
        for font in fonts:
            font_types[font.font_type] = font_types.get(font.font_type, 0) + 1

        # Generate errors and warnings
        errors = []
        warnings = []

        if missing:
            errors.append(
                f"{len(missing)} font(s) not embedded - will cause print issues"
            )
            for font in missing[:5]:
                errors.append(
                    f"  - {font.base_name} [{font.font_type}] "
                    f"on pages {sorted(list(font.pages_used))}"
                )

            if len(missing) > 5:
                errors.append(f"  ... and {len(missing) - 5} more")

        # Check subsetting
        non_subset_embedded = [f for f in fonts if f.is_embedded and not f.is_subset]
        if non_subset_embedded and self.require_subsetting:
            warnings.append(
                f"{len(non_subset_embedded)} embedded font(s) not subsetted"
            )
            warnings.append(
                "  - May increase file size unnecessarily"
            )

        # Check for suspicious font types
        if "Type3" in font_types:
            warnings.append(
                f"{font_types['Type3']} Type3 font(s) detected - "
                "may cause compatibility issues"
            )

        # Generate recommendations
        recommendations = self._generate_recommendations(missing, non_subset_embedded)

        # Determine pass/fail
        passed = (referenced_count == 0)
        pdf_x_compliant = passed and (subset_count == len(fonts))

        # Summary
        if passed:
            if pdf_x_compliant:
                summary = f"All {len(fonts)} fonts embedded and subset - PDF/X compliant"
            else:
                summary = f"All {len(fonts)} fonts embedded - ready for print"
        else:
            summary = (
                f"FAILED: {referenced_count} font(s) not embedded - "
                "will cause print failures"
            )

        return FontReport(
            total_fonts=len(fonts),
            embedded_fonts=embedded_count,
            subset_fonts=subset_count,
            referenced_fonts=referenced_count,
            fonts=fonts,
            missing_fonts=missing,
            font_types=font_types,
            passed=passed,
            pdf_x_compliant=pdf_x_compliant,
            errors=errors,
            warnings=warnings,
            recommendations=recommendations,
            summary=summary,
        )

    def _generate_recommendations(
        self,
        missing: List[FontInfo],
        non_subset: List[FontInfo]
    ) -> List[str]:
        """Generate actionable recommendations.

        Args:
            missing: Fonts not embedded
            non_subset: Embedded fonts that aren't subset

        Returns:
            List of recommendation strings
        """
        recommendations = []

        if missing:
            recommendations.append(
                "CRITICAL: Configure InDesign to embed all fonts:"
            )
            recommendations.append(
                "  1. File → Export → Adobe PDF (Print)"
            )
            recommendations.append(
                "  2. Choose PDF/X-4 preset"
            )
            recommendations.append(
                "  3. Verify 'Embed All Fonts' is checked"
            )
            recommendations.append(
                "  4. Check font licenses allow embedding"
            )

            # List specific fonts to check
            recommendations.append("")
            recommendations.append("Fonts to check/replace:")
            for font in missing[:5]:
                recommendations.append(f"  - {font.base_name}")

        if non_subset:
            recommendations.append(
                "Consider enabling font subsetting to reduce file size:"
            )
            recommendations.append(
                "  - InDesign: PDF Export → Advanced → Subset fonts < 100%"
            )

        if not missing:
            recommendations.append(
                "All fonts properly embedded - PDF is print-ready"
            )

        return recommendations

    def _empty_report(self, message: str) -> FontReport:
        """Generate empty report with message.

        Args:
            message: Error or info message

        Returns:
            Empty FontReport
        """
        return FontReport(
            total_fonts=0,
            embedded_fonts=0,
            subset_fonts=0,
            referenced_fonts=0,
            fonts=[],
            missing_fonts=[],
            font_types={},
            passed=True,
            pdf_x_compliant=True,
            errors=[],
            warnings=[message],
            recommendations=[],
            summary=message,
        )
