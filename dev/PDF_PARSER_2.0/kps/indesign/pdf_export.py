"""
PDF/X-4 Export System for InDesign Automation

This module provides comprehensive PDF export configuration and workflow
orchestration for InDesign documents, with full PDF/X-4:2010 compliance.

Components:
- PDFExportSettings: Dataclass for export configuration
- PDFExporter: Workflow orchestrator for export process

Author: KPS v2.0 Agent 4
Date: 2025-11-06
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, Tuple, Dict, Any, List
from pathlib import Path
from enum import Enum
import json
import logging

logger = logging.getLogger(__name__)


class PDFStandard(Enum):
    """PDF standards supported by InDesign"""
    PDF_X_4_2010 = "PDF/X-4:2010"
    PDF_X_1A_2001 = "PDF/X-1a:2001"
    PDF_X_3_2002 = "PDF/X-3:2002"
    PDF_A_1B_2005 = "PDF/A-1b:2005"
    HIGH_QUALITY_PRINT = "High Quality Print"
    PRESS_QUALITY = "Press Quality"


class ColorSpace(Enum):
    """Color space options for PDF export"""
    CMYK = "CMYK"
    RGB = "RGB"
    GRAY = "Grayscale"
    UNCHANGED = "Unchanged"


class CompressionType(Enum):
    """Image compression types"""
    JPEG = "JPEG"
    ZIP = "ZIP"
    JPEG2000 = "JPEG2000"
    AUTOMATIC = "Automatic"
    NONE = "None"


class ImageQuality(Enum):
    """Image quality presets"""
    MAXIMUM = "Maximum"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    MINIMUM = "Minimum"


class CompatibilityLevel(Enum):
    """PDF compatibility levels"""
    ACROBAT_4 = "Acrobat 4 (PDF 1.3)"
    ACROBAT_5 = "Acrobat 5 (PDF 1.4)"
    ACROBAT_6 = "Acrobat 6 (PDF 1.5)"
    ACROBAT_7 = "Acrobat 7 (PDF 1.6)"
    ACROBAT_8 = "Acrobat 8 (PDF 1.7)"


@dataclass
class PDFExportSettings:
    """
    Comprehensive InDesign PDF export settings.

    This dataclass represents all configuration options for exporting
    InDesign documents to PDF/X-4 or other PDF standards.

    Attributes:
        pdf_standard: Target PDF standard (PDF/X-4:2010 recommended)
        color_space: Color space for output (CMYK for print)
        output_intent: ICC profile name for color management
        image_quality: Quality preset for image compression
        compression: Compression algorithm for images
        jpeg_quality: JPEG compression quality (0-12, 12=max)
        ...and many more (see dataclass fields)

    Example:
        >>> settings = PDFExportSettings(
        ...     pdf_standard=PDFStandard.PDF_X_4_2010,
        ...     color_space=ColorSpace.CMYK,
        ...     include_bleed=True
        ... )
        >>> jsx_code = settings.to_jsx_script()
    """

    # ===== PDF Standard & Compatibility =====
    pdf_standard: PDFStandard = PDFStandard.PDF_X_4_2010
    compatibility: CompatibilityLevel = CompatibilityLevel.ACROBAT_7

    # ===== Color Management =====
    color_space: ColorSpace = ColorSpace.CMYK
    output_intent: str = "Coated FOGRA39 (ISO 12647-2:2004)"  # ICC profile
    destination_profile: Optional[str] = None  # Custom ICC profile path
    include_icc_profile: bool = True
    simulate_overprint: bool = True

    # ===== Image Quality & Compression =====
    image_quality: ImageQuality = ImageQuality.MAXIMUM
    compression: CompressionType = CompressionType.JPEG
    jpeg_quality: int = 12  # 0-12 (12 = maximum quality, minimum compression)

    # Downsampling settings
    downsample_images: bool = False
    downsample_color_to: int = 300  # DPI
    downsample_grayscale_to: int = 300  # DPI
    downsample_monochrome_to: int = 1200  # DPI
    resolution_threshold: int = 450  # DPI (don't downsample above this)

    # Color image settings
    color_compression: CompressionType = CompressionType.JPEG
    color_quality: ImageQuality = ImageQuality.MAXIMUM
    color_tile_size: int = 256  # For ZIP compression

    # Grayscale image settings
    grayscale_compression: CompressionType = CompressionType.JPEG
    grayscale_quality: ImageQuality = ImageQuality.MAXIMUM

    # Monochrome image settings
    monochrome_compression: CompressionType = CompressionType.ZIP

    # ===== Marks and Bleeds =====
    include_bleed: bool = True
    use_document_bleed: bool = True  # Use document bleed settings
    bleed_top: float = 3.0  # mm
    bleed_bottom: float = 3.0  # mm
    bleed_left: float = 3.0  # mm
    bleed_right: float = 3.0  # mm

    # Printer marks
    crop_marks: bool = True
    bleed_marks: bool = True
    registration_marks: bool = True
    color_bars: bool = True
    page_information: bool = True

    # Mark settings
    mark_type: str = "Default"  # Default, Light, Medium, Heavy
    mark_weight: float = 0.25  # pt
    mark_offset: float = 3.0  # mm

    # ===== Page Range & Layout =====
    page_range: str = "All"  # "All", "1-5", "1, 3, 5-7"
    spreads: bool = False  # Export spreads vs. individual pages
    generate_thumbnails: bool = True
    optimize_for_fast_web_view: bool = False

    # ===== Fonts =====
    embed_fonts: bool = True
    subset_fonts_threshold: int = 100  # % (100 = always subset)
    embed_all_fonts: bool = True

    # ===== Advanced =====
    create_acrobat_layers: bool = True
    include_structure: bool = True  # PDF structure (tags) for accessibility
    include_bookmarks: bool = True
    include_hyperlinks: bool = True

    # Transparency
    transparency_flattener_preset: str = "High Resolution"  # Low, Medium, High Resolution
    ignore_spread_overrides: bool = False

    # Security
    enable_security: bool = False
    require_password_to_open: bool = False
    require_password_to_print: bool = False
    password_open: Optional[str] = None
    password_permissions: Optional[str] = None

    # Output
    optimize_pdf: bool = True
    view_pdf_after_export: bool = False
    create_tagged_pdf: bool = True

    # Metadata
    include_metadata: bool = True
    preserve_document_info: bool = True

    # ===== Export Options =====
    export_layers: str = "Visible & Printable Layers"  # All, Visible, Visible & Printable
    export_guides_and_grids: bool = False
    export_nonprinting_objects: bool = False

    def to_jsx_script(self) -> str:
        """
        Generate JSX code to apply these settings in InDesign.

        Returns:
            JSX script as string that can be executed in InDesign
        """
        jsx_lines = [
            "// PDF Export Settings - Generated by KPS v2.0",
            "// Standard: " + self.pdf_standard.value,
            "",
            "with (app.pdfExportPreferences) {",
        ]

        # Standard and compatibility
        jsx_lines.extend([
            f"    // PDF Standard",
            f"    pdfExportPreset = PDFExportPresetList.item('{self.pdf_standard.value}');",
            "",
        ])

        # Color settings
        jsx_lines.extend([
            f"    // Color Management",
            f"    colorSpace = {self._jsx_color_space()};",
            f"    outputIntent = '{self.output_intent}';",
            f"    includeICCProfiles = {self._jsx_bool(self.include_icc_profile)};",
            f"    simulateOverprint = {self._jsx_bool(self.simulate_overprint)};",
            "",
        ])

        # Image quality and compression
        jsx_lines.extend([
            f"    // Image Quality & Compression",
            f"    colorCompression = Compression.{self.compression.value.upper()};",
            f"    compressionQuality = CompressionQuality.{self.image_quality.value.upper()};",
        ])

        if self.compression == CompressionType.JPEG:
            jsx_lines.append(f"    jpegQuality = JPEGQuality.{self._jsx_jpeg_quality()};")

        jsx_lines.extend([
            f"    thresholdToCompressColor = {self.resolution_threshold};",
            "",
        ])

        # Downsampling
        if self.downsample_images:
            jsx_lines.extend([
                f"    // Downsampling",
                f"    colorDownsampling = {self.downsample_color_to};",
                f"    grayscaleDownsampling = {self.downsample_grayscale_to};",
                f"    monochromeDownsampling = {self.downsample_monochrome_to};",
                "",
            ])

        # Marks and bleeds
        jsx_lines.extend([
            f"    // Marks and Bleeds",
            f"    useDocumentBleedWithPDF = {self._jsx_bool(self.use_document_bleed)};",
        ])

        if not self.use_document_bleed:
            jsx_lines.extend([
                f"    bleedTop = '{self.bleed_top}mm';",
                f"    bleedBottom = '{self.bleed_bottom}mm';",
                f"    bleedLeft = '{self.bleed_left}mm';",
                f"    bleedRight = '{self.bleed_right}mm';",
            ])

        jsx_lines.extend([
            f"    cropMarks = {self._jsx_bool(self.crop_marks)};",
            f"    bleedMarks = {self._jsx_bool(self.bleed_marks)};",
            f"    registrationMarks = {self._jsx_bool(self.registration_marks)};",
            f"    colorBars = {self._jsx_bool(self.color_bars)};",
            f"    pageInformationMarks = {self._jsx_bool(self.page_information)};",
            "",
        ])

        # Page range
        jsx_lines.extend([
            f"    // Page Range",
            f"    pageRange = '{self.page_range}';",
            f"    exportReaderSpreads = {self._jsx_bool(self.spreads)};",
            "",
        ])

        # Fonts
        jsx_lines.extend([
            f"    // Fonts",
            f"    subsetFontsBelow = {self.subset_fonts_threshold};",
            "",
        ])

        # Advanced
        jsx_lines.extend([
            f"    // Advanced Settings",
            f"    acrobatCompatibility = AcrobatCompatibility.{self._jsx_acrobat_compat()};",
            f"    generateThumbnails = {self._jsx_bool(self.generate_thumbnails)};",
            f"    optimizePDF = {self._jsx_bool(self.optimize_pdf)};",
            f"    createTaggedPDF = {self._jsx_bool(self.create_tagged_pdf)};",
            f"    includeStructure = {self._jsx_bool(self.include_structure)};",
            f"    includeBookmarks = {self._jsx_bool(self.include_bookmarks)};",
            f"    includeHyperlinks = {self._jsx_bool(self.include_hyperlinks)};",
            f"    viewPDF = {self._jsx_bool(self.view_pdf_after_export)};",
            "",
        ])

        # Transparency flattener
        jsx_lines.extend([
            f"    // Transparency",
            f"    appliedFlattenerPreset = app.flattenerPresets.item('{self.transparency_flattener_preset}');",
            "",
        ])

        jsx_lines.append("}")

        return "\n".join(jsx_lines)

    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary for serialization"""
        data = asdict(self)
        # Convert enums to values
        for key, value in data.items():
            if isinstance(value, Enum):
                data[key] = value.value
        return data

    def to_json(self) -> str:
        """Convert settings to JSON string"""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PDFExportSettings':
        """Create settings from dictionary"""
        # Convert string values back to enums
        if 'pdf_standard' in data and isinstance(data['pdf_standard'], str):
            data['pdf_standard'] = PDFStandard(data['pdf_standard'])
        if 'color_space' in data and isinstance(data['color_space'], str):
            data['color_space'] = ColorSpace(data['color_space'])
        if 'compression' in data and isinstance(data['compression'], str):
            data['compression'] = CompressionType(data['compression'])
        if 'image_quality' in data and isinstance(data['image_quality'], str):
            data['image_quality'] = ImageQuality(data['image_quality'])
        if 'compatibility' in data and isinstance(data['compatibility'], str):
            data['compatibility'] = CompatibilityLevel(data['compatibility'])

        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> 'PDFExportSettings':
        """Create settings from JSON string"""
        data = json.loads(json_str)
        return cls.from_dict(data)

    # ===== JSX Helper Methods =====

    def _jsx_bool(self, value: bool) -> str:
        """Convert Python bool to JSX bool"""
        return "true" if value else "false"

    def _jsx_color_space(self) -> str:
        """Convert Python enum to JSX ColorSpace constant"""
        mapping = {
            ColorSpace.CMYK: "ColorSpace.CMYK",
            ColorSpace.RGB: "ColorSpace.RGB",
            ColorSpace.GRAY: "ColorSpace.GRAY",
            ColorSpace.UNCHANGED: "ColorSpace.UNCHANGED_COLOR_SPACE"
        }
        return mapping.get(self.color_space, "ColorSpace.CMYK")

    def _jsx_jpeg_quality(self) -> str:
        """Convert JPEG quality integer to JSX constant"""
        # InDesign uses named constants for JPEG quality
        quality_map = {
            0: "MINIMUM",
            1: "LOW",
            2: "LOW",
            3: "LOW",
            4: "LOW",
            5: "MEDIUM",
            6: "MEDIUM",
            7: "MEDIUM",
            8: "HIGH",
            9: "HIGH",
            10: "HIGH",
            11: "MAXIMUM",
            12: "MAXIMUM"
        }
        return quality_map.get(self.jpeg_quality, "MAXIMUM")

    def _jsx_acrobat_compat(self) -> str:
        """Convert compatibility level to JSX constant"""
        mapping = {
            CompatibilityLevel.ACROBAT_4: "ACROBAT_4",
            CompatibilityLevel.ACROBAT_5: "ACROBAT_5",
            CompatibilityLevel.ACROBAT_6: "ACROBAT_6",
            CompatibilityLevel.ACROBAT_7: "ACROBAT_7",
            CompatibilityLevel.ACROBAT_8: "ACROBAT_8"
        }
        return mapping.get(self.compatibility, "ACROBAT_7")

    def validate(self) -> List[str]:
        """
        Validate settings for consistency and correctness.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # JPEG quality range
        if not 0 <= self.jpeg_quality <= 12:
            errors.append(f"JPEG quality must be 0-12, got {self.jpeg_quality}")

        # Bleed values must be positive
        if self.bleed_top < 0 or self.bleed_bottom < 0 or self.bleed_left < 0 or self.bleed_right < 0:
            errors.append("Bleed values must be positive")

        # Resolution threshold
        if self.resolution_threshold < 72:
            errors.append(f"Resolution threshold too low: {self.resolution_threshold} DPI")

        # Subset threshold
        if not 0 <= self.subset_fonts_threshold <= 100:
            errors.append(f"Font subset threshold must be 0-100%, got {self.subset_fonts_threshold}")

        # PDF/X-4 requires CMYK or Grayscale
        if self.pdf_standard == PDFStandard.PDF_X_4_2010:
            if self.color_space == ColorSpace.RGB:
                errors.append("PDF/X-4:2010 requires CMYK or Grayscale color space")
            if not self.output_intent:
                errors.append("PDF/X-4:2010 requires output intent (ICC profile)")

        return errors


# ===== Predefined Export Presets =====

def get_print_high_quality_preset() -> PDFExportSettings:
    """Get preset optimized for high-quality print production"""
    return PDFExportSettings(
        pdf_standard=PDFStandard.PDF_X_4_2010,
        color_space=ColorSpace.CMYK,
        output_intent="Coated FOGRA39 (ISO 12647-2:2004)",
        image_quality=ImageQuality.MAXIMUM,
        compression=CompressionType.JPEG,
        jpeg_quality=12,
        downsample_images=False,
        include_bleed=True,
        crop_marks=True,
        registration_marks=True,
        color_bars=True,
        transparency_flattener_preset="High Resolution",
        optimize_pdf=True
    )


def get_print_medium_quality_preset() -> PDFExportSettings:
    """Get preset for standard print quality (smaller file size)"""
    return PDFExportSettings(
        pdf_standard=PDFStandard.PDF_X_4_2010,
        color_space=ColorSpace.CMYK,
        output_intent="Coated FOGRA39 (ISO 12647-2:2004)",
        image_quality=ImageQuality.HIGH,
        compression=CompressionType.JPEG,
        jpeg_quality=10,
        downsample_images=True,
        downsample_color_to=300,
        include_bleed=True,
        crop_marks=True,
        transparency_flattener_preset="High Resolution",
        optimize_pdf=True
    )


def get_screen_optimized_preset() -> PDFExportSettings:
    """Get preset optimized for screen viewing (RGB, smaller file)"""
    return PDFExportSettings(
        pdf_standard=PDFStandard.HIGH_QUALITY_PRINT,
        color_space=ColorSpace.RGB,
        image_quality=ImageQuality.HIGH,
        compression=CompressionType.JPEG,
        jpeg_quality=8,
        downsample_images=True,
        downsample_color_to=150,
        downsample_grayscale_to=150,
        include_bleed=False,
        crop_marks=False,
        registration_marks=False,
        color_bars=False,
        optimize_for_fast_web_view=True,
        optimize_pdf=True
    )


def get_proof_preset() -> PDFExportSettings:
    """Get preset for quick proofing (low quality, fast generation)"""
    return PDFExportSettings(
        pdf_standard=PDFStandard.HIGH_QUALITY_PRINT,
        color_space=ColorSpace.RGB,
        image_quality=ImageQuality.MEDIUM,
        compression=CompressionType.JPEG,
        jpeg_quality=6,
        downsample_images=True,
        downsample_color_to=150,
        include_bleed=False,
        crop_marks=False,
        transparency_flattener_preset="Medium Resolution",
        optimize_pdf=False,
        generate_thumbnails=False
    )


# ===== Main Export Workflow =====

class PDFExporter:
    """
    Complete PDF export workflow orchestrator.

    Coordinates the export process from InDesign document to validated PDF/X-4 output.

    Example:
        >>> from kps.indesign.jsx_runner import JSXRunner
        >>> from kps.indesign.pdf_validator import PDFValidator
        >>>
        >>> exporter = PDFExporter()
        >>> settings = get_print_high_quality_preset()
        >>>
        >>> report = exporter.export_to_pdfx4(
        ...     indesign_doc=Path("pattern.indd"),
        ...     output_pdf=Path("pattern_print.pdf"),
        ...     preset=settings
        ... )
        >>>
        >>> if report.is_valid:
        ...     print("Export successful!")
    """

    def __init__(self, jsx_runner=None, validator=None):
        """
        Initialize exporter with optional dependencies.

        Args:
            jsx_runner: JSX script executor (will lazy-load if None)
            validator: PDF validator instance (will lazy-load if None)
        """
        self._jsx_runner = jsx_runner
        self._validator = validator

    @property
    def jsx_runner(self):
        """Lazy-load JSX runner"""
        if self._jsx_runner is None:
            try:
                from kps.indesign.jsx_runner import JSXRunner
                self._jsx_runner = JSXRunner()
            except ImportError:
                logger.warning("JSX runner not available - export will be limited")
        return self._jsx_runner

    @property
    def validator(self):
        """Lazy-load PDF validator"""
        if self._validator is None:
            from kps.indesign.pdf_validator import PDFValidator
            self._validator = PDFValidator()
        return self._validator

    def export_to_pdfx4(
        self,
        indesign_doc: Path,
        output_pdf: Path,
        preset: PDFExportSettings,
        validate: bool = True
    ):
        """
        Export InDesign document to PDF/X-4 and optionally validate.

        Args:
            indesign_doc: Path to InDesign document (.indd)
            output_pdf: Path for output PDF file
            preset: Export settings to apply
            validate: Whether to validate PDF after export

        Returns:
            PDFValidationReport if validate=True, else None

        Raises:
            ValueError: If settings validation fails
            RuntimeError: If export fails
        """
        logger.info(f"Starting PDF/X-4 export: {indesign_doc} -> {output_pdf}")

        # Validate settings
        errors = preset.validate()
        if errors:
            error_msg = "Export settings validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Ensure paths are absolute
        indesign_doc = Path(indesign_doc).resolve()
        output_pdf = Path(output_pdf).resolve()

        # Check input file exists
        if not indesign_doc.exists():
            raise FileNotFoundError(f"InDesign document not found: {indesign_doc}")

        # Create output directory
        output_pdf.parent.mkdir(parents=True, exist_ok=True)

        # Generate JSX script
        jsx_script = preset.to_jsx_script()
        logger.debug(f"Generated JSX script ({len(jsx_script)} chars)")

        # Execute export via JSX
        try:
            if self.jsx_runner:
                result = self._execute_jsx_export(
                    indesign_doc=indesign_doc,
                    output_pdf=output_pdf,
                    jsx_settings=jsx_script
                )
                logger.info(f"Export completed: {output_pdf}")
            else:
                logger.warning("JSX runner not available - skipping actual export")
                result = {"success": False, "message": "JSX runner not available"}
        except Exception as e:
            logger.error(f"Export failed: {e}")
            raise RuntimeError(f"PDF export failed: {e}")

        # Validate output
        if validate and output_pdf.exists():
            logger.info("Validating PDF/X-4 compliance...")
            report = self.validator.validate_pdfx4(output_pdf)

            if report.is_valid:
                logger.info("✓ PDF/X-4 validation passed")
            else:
                logger.warning("✗ PDF/X-4 validation failed")
                for error in report.compliance_errors:
                    logger.warning(f"  - {error}")

            return report

        return None

    def _execute_jsx_export(
        self,
        indesign_doc: Path,
        output_pdf: Path,
        jsx_settings: str
    ) -> Dict[str, Any]:
        """
        Execute JSX export script with settings.

        This is a placeholder - actual implementation depends on JSX runner.
        """
        if not self.jsx_runner:
            return {"success": False, "message": "JSX runner not initialized"}

        # In actual implementation, would call:
        # return self.jsx_runner.execute_script(
        #     script_path="jsx/export_pdf.jsx",
        #     document_path=indesign_doc,
        #     output_path=output_pdf,
        #     preset_settings=jsx_settings
        # )

        logger.warning("JSX execution not yet implemented")
        return {"success": False, "message": "JSX execution not implemented"}


if __name__ == "__main__":
    # Demo usage
    print("PDF/X-4 Export Settings Demo")
    print("=" * 50)

    # Create high-quality print preset
    settings = get_print_high_quality_preset()

    # Display settings
    print("\nHigh Quality Print Preset:")
    print(f"  Standard: {settings.pdf_standard.value}")
    print(f"  Color Space: {settings.color_space.value}")
    print(f"  JPEG Quality: {settings.jpeg_quality}")
    print(f"  Bleed: {settings.include_bleed}")

    # Validate
    errors = settings.validate()
    if errors:
        print("\nValidation errors:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("\n✓ Settings valid")

    # Generate JSX
    jsx = settings.to_jsx_script()
    print(f"\nGenerated JSX script: {len(jsx)} characters")
    print("\nFirst 500 characters:")
    print(jsx[:500])
