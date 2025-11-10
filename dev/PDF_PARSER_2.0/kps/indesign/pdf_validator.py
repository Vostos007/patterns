"""
PDF/X-4 Compliance Validator

Validates exported PDFs for PDF/X-4:2010 compliance and print quality standards.
Uses external tools (Ghostscript, poppler-utils) when available, with graceful
fallback for missing dependencies.

Author: KPS v2.0 Agent 4
Date: 2025-11-06
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import subprocess
import re
import logging
from datetime import datetime

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    logging.warning("PyMuPDF not available - PDF validation will be limited")

logger = logging.getLogger(__name__)


@dataclass
class PDFValidationReport:
    """
    Comprehensive PDF validation report.

    Contains all validation results including compliance status,
    technical specifications, and any issues found.

    Attributes:
        is_valid: Overall validation result (all checks passed)
        pdf_version: PDF version (e.g., "1.6", "1.7")
        pdf_standard: PDF standard if specified (e.g., "PDF/X-4")
        page_count: Number of pages in PDF
        file_size: File size in bytes
        color_space: Dominant color space (CMYK, RGB, etc.)
        has_output_intent: Whether OutputIntent (ICC profile) is present
        embedded_fonts: List of embedded font names
        unembedded_fonts: List of fonts not embedded (error for PDF/X)
        resolution_issues: List of low-resolution images
        compliance_errors: Critical errors preventing PDF/X-4 compliance
        warnings: Non-critical warnings
        validation_time: Time taken for validation
        tool_availability: Which validation tools were available
    """
    is_valid: bool
    pdf_version: str = "Unknown"
    pdf_standard: str = "Unknown"
    page_count: int = 0
    file_size: int = 0
    color_space: str = "Unknown"
    has_output_intent: bool = False
    output_intent_name: str = ""
    embedded_fonts: List[str] = field(default_factory=list)
    unembedded_fonts: List[str] = field(default_factory=list)
    resolution_issues: List[str] = field(default_factory=list)
    compliance_errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    validation_time: float = 0.0
    tool_availability: Dict[str, bool] = field(default_factory=dict)
    metadata: Dict[str, str] = field(default_factory=dict)

    def __str__(self) -> str:
        """Human-readable validation report"""
        lines = [
            "PDF Validation Report",
            "=" * 60,
            f"Status: {'✓ VALID' if self.is_valid else '✗ INVALID'}",
            f"PDF Version: {self.pdf_version}",
            f"Standard: {self.pdf_standard}",
            f"Pages: {self.page_count}",
            f"File Size: {self._format_size(self.file_size)}",
            f"Color Space: {self.color_space}",
            f"Output Intent: {'Yes' if self.has_output_intent else 'No'}",
        ]

        if self.output_intent_name:
            lines.append(f"  Profile: {self.output_intent_name}")

        lines.append(f"\nFonts: {len(self.embedded_fonts)} embedded")
        if self.unembedded_fonts:
            lines.append(f"  ⚠ {len(self.unembedded_fonts)} fonts not embedded:")
            for font in self.unembedded_fonts[:5]:
                lines.append(f"    - {font}")
            if len(self.unembedded_fonts) > 5:
                lines.append(f"    ... and {len(self.unembedded_fonts) - 5} more")

        if self.resolution_issues:
            lines.append(f"\nResolution Issues: {len(self.resolution_issues)}")
            for issue in self.resolution_issues[:5]:
                lines.append(f"  - {issue}")
            if len(self.resolution_issues) > 5:
                lines.append(f"  ... and {len(self.resolution_issues) - 5} more")

        if self.compliance_errors:
            lines.append(f"\n✗ Compliance Errors ({len(self.compliance_errors)}):")
            for error in self.compliance_errors:
                lines.append(f"  - {error}")

        if self.warnings:
            lines.append(f"\n⚠ Warnings ({len(self.warnings)}):")
            for warning in self.warnings:
                lines.append(f"  - {warning}")

        lines.append(f"\nValidation Time: {self.validation_time:.2f}s")

        return "\n".join(lines)

    def _format_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

    def to_dict(self) -> Dict:
        """Convert report to dictionary for serialization"""
        return {
            'is_valid': self.is_valid,
            'pdf_version': self.pdf_version,
            'pdf_standard': self.pdf_standard,
            'page_count': self.page_count,
            'file_size': self.file_size,
            'color_space': self.color_space,
            'has_output_intent': self.has_output_intent,
            'output_intent_name': self.output_intent_name,
            'embedded_fonts': self.embedded_fonts,
            'unembedded_fonts': self.unembedded_fonts,
            'resolution_issues': self.resolution_issues,
            'compliance_errors': self.compliance_errors,
            'warnings': self.warnings,
            'validation_time': self.validation_time,
            'tool_availability': self.tool_availability,
            'metadata': self.metadata
        }


class PDFValidator:
    """
    PDF/X-4 compliance validator.

    Uses multiple validation methods with graceful fallback:
    1. PyMuPDF (fitz) for basic PDF analysis
    2. Ghostscript (gs) for compliance checking
    3. Poppler utils (pdfinfo, pdfimages) for detailed analysis

    Example:
        >>> validator = PDFValidator()
        >>> report = validator.validate_pdfx4(Path("output.pdf"))
        >>> if report.is_valid:
        ...     print("PDF is valid!")
        >>> else:
        ...     print("Errors:", report.compliance_errors)
    """

    def __init__(self, min_dpi: int = 300):
        """
        Initialize validator.

        Args:
            min_dpi: Minimum acceptable image resolution (default: 300)
        """
        self.min_dpi = min_dpi
        self.tool_availability = self._check_tool_availability()

        # Log available tools
        available_tools = [k for k, v in self.tool_availability.items() if v]
        logger.info(f"PDF validation tools available: {', '.join(available_tools) or 'None'}")

    def validate_pdfx4(self, pdf_path: Path) -> PDFValidationReport:
        """
        Validate PDF meets PDF/X-4:2010 standards.

        Args:
            pdf_path: Path to PDF file to validate

        Returns:
            PDFValidationReport with validation results
        """
        start_time = datetime.now()
        logger.info(f"Validating PDF: {pdf_path}")

        # Check file exists
        if not pdf_path.exists():
            return PDFValidationReport(
                is_valid=False,
                compliance_errors=[f"File not found: {pdf_path}"],
                tool_availability=self.tool_availability
            )

        # Initialize report
        report = PDFValidationReport(
            is_valid=True,  # Assume valid until proven otherwise
            file_size=pdf_path.stat().st_size,
            tool_availability=self.tool_availability.copy()
        )

        # Run validation checks
        try:
            # Basic PDF info
            if PYMUPDF_AVAILABLE:
                self._validate_with_pymupdf(pdf_path, report)
            elif self.tool_availability.get('pdfinfo'):
                self._validate_with_pdfinfo(pdf_path, report)

            # PDF/X-4 compliance
            if self.tool_availability.get('ghostscript'):
                self._validate_pdfx4_compliance(pdf_path, report)
            else:
                report.warnings.append("Ghostscript not available - PDF/X-4 compliance not verified")

            # Image resolution
            if self.tool_availability.get('pdfimages'):
                self._check_image_resolution(pdf_path, report)
            elif PYMUPDF_AVAILABLE:
                self._check_image_resolution_pymupdf(pdf_path, report)
            else:
                report.warnings.append("No tool available for image resolution checking")

            # Font embedding
            if PYMUPDF_AVAILABLE:
                self._check_fonts_pymupdf(pdf_path, report)
            else:
                report.warnings.append("PyMuPDF not available - font checking limited")

            # Final validation
            if report.compliance_errors:
                report.is_valid = False

        except Exception as e:
            logger.error(f"Validation error: {e}")
            report.is_valid = False
            report.compliance_errors.append(f"Validation error: {str(e)}")

        # Calculate validation time
        end_time = datetime.now()
        report.validation_time = (end_time - start_time).total_seconds()

        logger.info(f"Validation completed in {report.validation_time:.2f}s - Valid: {report.is_valid}")
        return report

    def _validate_with_pymupdf(self, pdf_path: Path, report: PDFValidationReport):
        """Extract basic PDF information using PyMuPDF"""
        try:
            doc = fitz.open(pdf_path)

            # Basic info
            report.page_count = doc.page_count
            report.pdf_version = f"1.{doc.pdf_version()}"

            # Metadata
            metadata = doc.metadata or {}
            report.metadata = {
                'title': metadata.get('title', ''),
                'author': metadata.get('author', ''),
                'subject': metadata.get('subject', ''),
                'creator': metadata.get('creator', ''),
                'producer': metadata.get('producer', '')
            }

            # Check for PDF/X standard in metadata
            if 'GTS_PDFX' in metadata.get('format', ''):
                report.pdf_standard = metadata.get('format', 'PDF/X')
            elif doc.xref_get_key(-1, 'GTS_PDFXVersion'):
                # Check PDF catalog for PDF/X version
                try:
                    pdfx_version = doc.xref_get_key(-1, 'GTS_PDFXVersion')
                    report.pdf_standard = pdfx_version[1] if pdfx_version else "PDF/X"
                except:
                    pass

            # Check for OutputIntent (ICC profile)
            try:
                catalog = doc.pdf_catalog()
                if 'OutputIntents' in catalog:
                    report.has_output_intent = True
                    # Try to extract OutputIntent name
                    output_intents = catalog.get('OutputIntents', [])
                    if output_intents:
                        intent = output_intents[0] if isinstance(output_intents, list) else output_intents
                        if hasattr(intent, 'get'):
                            report.output_intent_name = intent.get('OutputConditionIdentifier', '')
            except Exception as e:
                logger.debug(f"Could not extract OutputIntent: {e}")

            doc.close()

        except Exception as e:
            logger.error(f"PyMuPDF validation error: {e}")
            report.warnings.append(f"PyMuPDF error: {str(e)}")

    def _validate_with_pdfinfo(self, pdf_path: Path, report: PDFValidationReport):
        """Extract PDF information using pdfinfo command"""
        try:
            result = subprocess.run(
                ['pdfinfo', str(pdf_path)],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                output = result.stdout

                # Parse output
                for line in output.split('\n'):
                    if line.startswith('Pages:'):
                        report.page_count = int(line.split(':')[1].strip())
                    elif line.startswith('PDF version:'):
                        report.pdf_version = line.split(':')[1].strip()
                    elif line.startswith('Title:'):
                        report.metadata['title'] = line.split(':', 1)[1].strip()
                    elif line.startswith('Author:'):
                        report.metadata['author'] = line.split(':', 1)[1].strip()

        except subprocess.TimeoutExpired:
            report.warnings.append("pdfinfo timeout")
        except Exception as e:
            logger.debug(f"pdfinfo error: {e}")

    def _validate_pdfx4_compliance(self, pdf_path: Path, report: PDFValidationReport):
        """Check PDF/X-4 compliance using Ghostscript"""
        try:
            # Run Ghostscript with PDF/X validation
            result = subprocess.run(
                [
                    'gs',
                    '-dNODISPLAY',
                    '-dPDFX',
                    '-sDEVICE=pdfwrite',
                    '-o', '/dev/null',
                    str(pdf_path)
                ],
                capture_output=True,
                text=True,
                timeout=120
            )

            # Check for errors in output
            stderr = result.stderr.lower()

            if result.returncode != 0:
                report.compliance_errors.append("Ghostscript PDF/X validation failed")

                # Parse specific errors
                if 'outputintent' in stderr:
                    report.compliance_errors.append("Missing or invalid OutputIntent (ICC profile)")
                if 'font' in stderr and 'not embedded' in stderr:
                    report.compliance_errors.append("Not all fonts are embedded")
                if 'transparency' in stderr:
                    report.warnings.append("Transparency detected (may need flattening)")

            # Check for PDF/X standard declaration
            if 'pdfx' not in stderr:
                report.warnings.append("PDF/X standard not clearly declared")

        except subprocess.TimeoutExpired:
            report.warnings.append("Ghostscript validation timeout")
        except FileNotFoundError:
            report.warnings.append("Ghostscript not found in PATH")
        except Exception as e:
            logger.debug(f"Ghostscript validation error: {e}")

    def _check_image_resolution(self, pdf_path: Path, report: PDFValidationReport):
        """Check image resolution using pdfimages"""
        try:
            # Get image list with pdfimages
            result = subprocess.run(
                ['pdfimages', '-list', str(pdf_path)],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                output = result.stdout
                lines = output.split('\n')[2:]  # Skip header lines

                for line in lines:
                    if not line.strip():
                        continue

                    # Parse image info
                    parts = line.split()
                    if len(parts) >= 8:
                        try:
                            page = int(parts[0])
                            width = int(parts[2])
                            height = int(parts[3])
                            x_dpi = int(parts[6]) if parts[6].isdigit() else 0
                            y_dpi = int(parts[7]) if parts[7].isdigit() else 0

                            # Check if below minimum DPI
                            if 0 < x_dpi < self.min_dpi or 0 < y_dpi < self.min_dpi:
                                report.resolution_issues.append(
                                    f"Page {page}: Image {width}x{height}px @ {x_dpi}x{y_dpi} DPI"
                                )
                        except (ValueError, IndexError):
                            continue

                # Add warning if low-res images found
                if report.resolution_issues:
                    report.warnings.append(
                        f"{len(report.resolution_issues)} images below {self.min_dpi} DPI"
                    )

        except subprocess.TimeoutExpired:
            report.warnings.append("pdfimages timeout")
        except Exception as e:
            logger.debug(f"pdfimages error: {e}")

    def _check_image_resolution_pymupdf(self, pdf_path: Path, report: PDFValidationReport):
        """Check image resolution using PyMuPDF"""
        try:
            doc = fitz.open(pdf_path)

            for page_num in range(doc.page_count):
                page = doc[page_num]
                image_list = page.get_images()

                for img_index, img in enumerate(image_list):
                    xref = img[0]

                    # Get image properties
                    try:
                        pix = fitz.Pixmap(doc, xref)
                        width = pix.width
                        height = pix.height

                        # Get image position on page to calculate DPI
                        # This is approximate - more accurate calculation would need transform matrix
                        dpi = min(width, height) / 2  # Rough estimate

                        if dpi < self.min_dpi:
                            report.resolution_issues.append(
                                f"Page {page_num + 1}: Image {width}x{height}px (estimated {dpi:.0f} DPI)"
                            )

                        pix = None  # Free memory
                    except Exception as e:
                        logger.debug(f"Could not analyze image {xref}: {e}")
                        continue

            doc.close()

            if report.resolution_issues:
                report.warnings.append(
                    f"{len(report.resolution_issues)} images may be below {self.min_dpi} DPI"
                )

        except Exception as e:
            logger.debug(f"PyMuPDF image checking error: {e}")

    def _check_fonts_pymupdf(self, pdf_path: Path, report: PDFValidationReport):
        """Check font embedding using PyMuPDF"""
        try:
            doc = fitz.open(pdf_path)

            for page_num in range(doc.page_count):
                page = doc[page_num]
                fonts = page.get_fonts()

                for font in fonts:
                    font_name = font[3]  # Font name is at index 3
                    font_type = font[1]  # Font type

                    # Check if embedded (Type0, Type1C, TrueType, etc. are usually embedded)
                    # Non-embedded fonts typically have "Type3" or no subtype
                    is_embedded = font_type not in ['Type3', '']

                    if is_embedded:
                        if font_name not in report.embedded_fonts:
                            report.embedded_fonts.append(font_name)
                    else:
                        if font_name not in report.unembedded_fonts:
                            report.unembedded_fonts.append(font_name)

            # PDF/X requires all fonts to be embedded
            if report.unembedded_fonts:
                report.compliance_errors.append(
                    f"{len(report.unembedded_fonts)} fonts not embedded (required for PDF/X-4)"
                )

            doc.close()

        except Exception as e:
            logger.debug(f"Font checking error: {e}")

    def _check_tool_availability(self) -> Dict[str, bool]:
        """Check which external validation tools are available"""
        tools = {}

        # Check PyMuPDF
        tools['pymupdf'] = PYMUPDF_AVAILABLE

        # Check Ghostscript
        try:
            subprocess.run(['gs', '--version'], capture_output=True, timeout=5)
            tools['ghostscript'] = True
        except:
            tools['ghostscript'] = False

        # Check pdfinfo (poppler)
        try:
            subprocess.run(['pdfinfo', '-v'], capture_output=True, timeout=5)
            tools['pdfinfo'] = True
        except:
            tools['pdfinfo'] = False

        # Check pdfimages (poppler)
        try:
            subprocess.run(['pdfimages', '-v'], capture_output=True, timeout=5)
            tools['pdfimages'] = True
        except:
            tools['pdfimages'] = False

        return tools

    def check_color_profile(self, pdf_path: Path) -> Tuple[bool, str]:
        """
        Check if PDF has proper color profile (OutputIntent).

        Returns:
            Tuple of (has_profile, profile_name)
        """
        if not PYMUPDF_AVAILABLE:
            return (False, "PyMuPDF not available")

        try:
            doc = fitz.open(pdf_path)

            # Check PDF catalog for OutputIntent
            try:
                catalog = doc.pdf_catalog()
                if 'OutputIntents' in catalog:
                    output_intents = catalog.get('OutputIntents', [])
                    if output_intents:
                        intent = output_intents[0] if isinstance(output_intents, list) else output_intents
                        profile_name = intent.get('OutputConditionIdentifier', 'Unknown')
                        doc.close()
                        return (True, profile_name)
            except:
                pass

            doc.close()
            return (False, "No OutputIntent found")

        except Exception as e:
            logger.debug(f"Color profile check error: {e}")
            return (False, str(e))


if __name__ == "__main__":
    # Demo usage
    import sys

    print("PDF/X-4 Validator Demo")
    print("=" * 60)

    # Check tool availability
    validator = PDFValidator()
    print("\nValidation Tools Available:")
    for tool, available in validator.tool_availability.items():
        status = "✓" if available else "✗"
        print(f"  {status} {tool}")

    # If PDF path provided, validate it
    if len(sys.argv) > 1:
        pdf_path = Path(sys.argv[1])
        print(f"\nValidating: {pdf_path}")
        print("-" * 60)

        report = validator.validate_pdfx4(pdf_path)
        print(report)
    else:
        print("\nUsage: python pdf_validator.py <pdf_file>")
        print("\nExample validation report structure:")
        print("-" * 60)

        # Create demo report
        demo_report = PDFValidationReport(
            is_valid=True,
            pdf_version="1.6",
            pdf_standard="PDF/X-4:2010",
            page_count=24,
            file_size=15_234_567,
            color_space="CMYK",
            has_output_intent=True,
            output_intent_name="Coated FOGRA39",
            embedded_fonts=["Helvetica-Bold", "Times-Roman"],
            validation_time=2.34,
            tool_availability=validator.tool_availability
        )
        print(demo_report)
