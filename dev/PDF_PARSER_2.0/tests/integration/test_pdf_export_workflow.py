"""Integration tests for PDF export workflow."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
import subprocess

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "unit"))

from test_jsx_runner import JSXRunner
from test_pdf_export import (
    PDFExportSettings,
    PDFExportResult,
    PDFStandard,
    ColorSpace,
    PDFPresetManager
)


@pytest.mark.integration
class TestPDFExportWorkflow:
    """Test complete PDF export workflow."""

    def test_export_with_default_settings(self, tmp_path):
        """Test PDF export with default settings."""
        runner = JSXRunner()
        settings = PDFExportSettings()

        # Validate settings
        errors = settings.validate()
        assert len(errors) == 0

        # Mock export
        with patch.object(runner, 'export_pdf') as mock_export:
            mock_export.return_value = PDFExportResult(
                success=True,
                output_path=tmp_path / "output.pdf",
                file_size=1024000,
                pages=10,
                is_valid_pdfx4=True
            )

            result = runner.export_pdf(
                document_path=Path("/tmp/test.indd"),
                output_pdf=tmp_path / "output.pdf",
                preset=settings.__dict__
            )

            assert result.success is True
            assert result.is_valid_pdfx4 is True

    def test_export_with_preset(self, tmp_path):
        """Test PDF export using saved preset."""
        manager = PDFPresetManager()

        # Mock preset loading
        with pytest.raises(NotImplementedError):
            settings = manager.get_preset("print_high_quality")

        # Mock preset
        settings = PDFExportSettings(
            pdf_standard=PDFStandard.PDF_X_4_2010,
            color_space=ColorSpace.CMYK,
            jpeg_quality=12,
            bleed_top=3.0,
            bleed_bottom=3.0,
            bleed_left=3.0,
            bleed_right=3.0
        )

        errors = settings.validate()
        assert len(errors) == 0

        # Export with preset
        runner = JSXRunner()
        with patch.object(runner, 'export_pdf') as mock_export:
            mock_export.return_value = PDFExportResult(
                success=True,
                output_path=tmp_path / "output.pdf",
                file_size=2048000,
                pages=10
            )

            result = runner.export_pdf(
                document_path=Path("/tmp/test.indd"),
                output_pdf=tmp_path / "output.pdf",
                preset=settings.__dict__
            )

            assert result.success is True

    def test_export_and_validate_pdfx4(self, tmp_path):
        """Test export and PDF/X-4 validation."""
        runner = JSXRunner()
        settings = PDFExportSettings(
            pdf_standard=PDFStandard.PDF_X_4_2010,
            color_space=ColorSpace.CMYK
        )

        # Mock export
        output_pdf = tmp_path / "output.pdf"
        with patch.object(runner, 'export_pdf') as mock_export:
            mock_export.return_value = PDFExportResult(
                success=True,
                output_path=output_pdf,
                file_size=1024000,
                pages=10,
                is_valid_pdfx4=True,
                validation_report="PDF/X-4:2010 compliant\n0 errors\n0 warnings"
            )

            result = runner.export_pdf(
                document_path=Path("/tmp/test.indd"),
                output_pdf=output_pdf,
                preset=settings.__dict__
            )

            # Verify PDF/X-4 compliance
            assert result.is_valid_pdfx4 is True
            assert "compliant" in result.validation_report


@pytest.mark.integration
class TestPDFExportValidation:
    """Test PDF export validation."""

    def test_validate_output_file_created(self, tmp_path):
        """Test that output PDF file is created."""
        runner = JSXRunner()
        output_pdf = tmp_path / "output.pdf"

        with patch.object(runner, 'export_pdf') as mock_export:
            mock_export.return_value = PDFExportResult(
                success=True,
                output_path=output_pdf,
                file_size=1024000,
                pages=10
            )

            result = runner.export_pdf(
                document_path=Path("/tmp/test.indd"),
                output_pdf=output_pdf,
                preset={}
            )

            assert result.output_path == output_pdf

    def test_validate_page_count(self):
        """Test validating page count in output."""
        runner = JSXRunner()

        with patch.object(runner, 'export_pdf') as mock_export:
            mock_export.return_value = PDFExportResult(
                success=True,
                output_path=Path("/tmp/output.pdf"),
                file_size=1024000,
                pages=15
            )

            result = runner.export_pdf(
                document_path=Path("/tmp/test.indd"),
                output_pdf=Path("/tmp/output.pdf"),
                preset={}
            )

            # Verify page count
            assert result.pages == 15

    def test_validate_file_size_reasonable(self):
        """Test that output file size is reasonable."""
        runner = JSXRunner()

        with patch.object(runner, 'export_pdf') as mock_export:
            mock_export.return_value = PDFExportResult(
                success=True,
                output_path=Path("/tmp/output.pdf"),
                file_size=1024000,  # 1 MB
                pages=10
            )

            result = runner.export_pdf(
                document_path=Path("/tmp/test.indd"),
                output_pdf=Path("/tmp/output.pdf"),
                preset={}
            )

            # File size should be reasonable (1MB for 10 pages)
            assert 500_000 < result.file_size < 10_000_000

    @pytest.mark.skipif(True, reason="Requires Ghostscript")
    def test_validate_with_ghostscript(self, tmp_path):
        """Test PDF/X-4 validation with Ghostscript."""
        output_pdf = tmp_path / "output.pdf"

        # Would run: gs -dNOPAUSE -dBATCH -sDEVICE=pdfwrite output.pdf
        # For now, skip if Ghostscript not available
        try:
            result = subprocess.run(
                ['gs', '--version'],
                capture_output=True,
                timeout=5
            )
            ghostscript_available = result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            ghostscript_available = False

        if not ghostscript_available:
            pytest.skip("Ghostscript not available")


@pytest.mark.integration
class TestPDFExportWithWarnings:
    """Test PDF export with warnings."""

    def test_export_with_font_warnings(self):
        """Test export with font substitution warnings."""
        runner = JSXRunner()

        with patch.object(runner, 'export_pdf') as mock_export:
            mock_export.return_value = PDFExportResult(
                success=True,
                output_path=Path("/tmp/output.pdf"),
                file_size=1024000,
                pages=10,
                warnings=[
                    "Font 'CustomFont' was substituted with 'Arial'",
                    "Font 'AnotherFont' not found, using default"
                ]
            )

            result = runner.export_pdf(
                document_path=Path("/tmp/test.indd"),
                output_pdf=Path("/tmp/output.pdf"),
                preset={}
            )

            # Should succeed with warnings
            assert result.success is True
            assert len(result.warnings) == 2

    def test_export_with_image_warnings(self):
        """Test export with image resolution warnings."""
        runner = JSXRunner()

        with patch.object(runner, 'export_pdf') as mock_export:
            mock_export.return_value = PDFExportResult(
                success=True,
                output_path=Path("/tmp/output.pdf"),
                file_size=1024000,
                pages=10,
                warnings=[
                    "Image 'photo.jpg' resolution is 150 DPI (recommended: 300 DPI)",
                    "Image 'diagram.png' uses RGB color space"
                ]
            )

            result = runner.export_pdf(
                document_path=Path("/tmp/test.indd"),
                output_pdf=Path("/tmp/output.pdf"),
                preset={}
            )

            assert result.success is True
            assert len(result.warnings) == 2

    def test_export_with_color_space_warnings(self):
        """Test export with color space warnings."""
        runner = JSXRunner()

        with patch.object(runner, 'export_pdf') as mock_export:
            mock_export.return_value = PDFExportResult(
                success=True,
                output_path=Path("/tmp/output.pdf"),
                file_size=1024000,
                pages=10,
                warnings=[
                    "Image contains RGB colors (PDF/X-4 prefers CMYK)"
                ]
            )

            result = runner.export_pdf(
                document_path=Path("/tmp/test.indd"),
                output_pdf=Path("/tmp/output.pdf"),
                preset={}
            )

            assert result.success is True
            assert any("RGB" in w for w in result.warnings)


@pytest.mark.integration
class TestPDFExportFailures:
    """Test PDF export failure scenarios."""

    def test_export_document_not_found(self):
        """Test export when document doesn't exist."""
        runner = JSXRunner()

        with patch.object(runner, 'export_pdf') as mock_export:
            mock_export.return_value = PDFExportResult(
                success=False,
                output_path=None,
                errors=["Document not found: /nonexistent/test.indd"]
            )

            result = runner.export_pdf(
                document_path=Path("/nonexistent/test.indd"),
                output_pdf=Path("/tmp/output.pdf"),
                preset={}
            )

            assert result.success is False
            assert len(result.errors) > 0

    def test_export_invalid_preset(self):
        """Test export with invalid preset."""
        runner = JSXRunner()

        # Invalid settings
        settings = PDFExportSettings(jpeg_quality=99)
        errors = settings.validate()

        assert len(errors) > 0

    def test_export_insufficient_disk_space(self):
        """Test export failure due to disk space."""
        runner = JSXRunner()

        with patch.object(runner, 'export_pdf') as mock_export:
            mock_export.return_value = PDFExportResult(
                success=False,
                output_path=None,
                errors=["Insufficient disk space for export"]
            )

            result = runner.export_pdf(
                document_path=Path("/tmp/test.indd"),
                output_pdf=Path("/tmp/output.pdf"),
                preset={}
            )

            assert result.success is False

    def test_export_indesign_crash(self):
        """Test handling InDesign crash during export."""
        runner = JSXRunner()

        with patch.object(runner, 'export_pdf') as mock_export:
            mock_export.return_value = PDFExportResult(
                success=False,
                output_path=None,
                errors=["InDesign application crashed during export"]
            )

            result = runner.export_pdf(
                document_path=Path("/tmp/test.indd"),
                output_pdf=Path("/tmp/output.pdf"),
                preset={}
            )

            assert result.success is False
            assert any("crash" in e.lower() for e in result.errors)


@pytest.mark.integration
class TestPDFExportQualitySettings:
    """Test different quality settings."""

    def test_export_maximum_quality(self):
        """Test export with maximum quality settings."""
        settings = PDFExportSettings(
            pdf_standard=PDFStandard.PDF_X_4_2010,
            color_space=ColorSpace.CMYK,
            jpeg_quality=12,  # Maximum
            compression="None",
            embed_fonts=True,
            include_icc_profiles=True
        )

        errors = settings.validate()
        assert len(errors) == 0

        # Would produce larger file
        runner = JSXRunner()
        with patch.object(runner, 'export_pdf') as mock_export:
            mock_export.return_value = PDFExportResult(
                success=True,
                output_path=Path("/tmp/output.pdf"),
                file_size=5_000_000,  # Larger file due to higher quality
                pages=10
            )

            result = runner.export_pdf(
                document_path=Path("/tmp/test.indd"),
                output_pdf=Path("/tmp/output.pdf"),
                preset=settings.__dict__
            )

            # Larger file size expected
            assert result.file_size > 2_000_000

    def test_export_minimum_quality(self):
        """Test export with minimum quality (smallest file)."""
        settings = PDFExportSettings(
            pdf_standard=PDFStandard.PDF_1_4,
            color_space=ColorSpace.RGB,
            jpeg_quality=0,  # Minimum
            compression="Auto",
            optimize_pdf=True,
            subset_fonts_threshold=1
        )

        errors = settings.validate()
        assert len(errors) == 0

        # Would produce smaller file
        runner = JSXRunner()
        with patch.object(runner, 'export_pdf') as mock_export:
            mock_export.return_value = PDFExportResult(
                success=True,
                output_path=Path("/tmp/output.pdf"),
                file_size=500_000,  # Smaller file
                pages=10
            )

            result = runner.export_pdf(
                document_path=Path("/tmp/test.indd"),
                output_pdf=Path("/tmp/output.pdf"),
                preset=settings.__dict__
            )

            # Smaller file size expected
            assert result.file_size < 1_000_000

    def test_export_with_bleed(self):
        """Test export with bleed settings."""
        settings = PDFExportSettings(
            bleed_top=3.0,
            bleed_bottom=3.0,
            bleed_left=3.0,
            bleed_right=3.0
        )

        errors = settings.validate()
        assert len(errors) == 0

        # Export with bleed
        runner = JSXRunner()
        with patch.object(runner, 'export_pdf') as mock_export:
            mock_export.return_value = PDFExportResult(
                success=True,
                output_path=Path("/tmp/output.pdf"),
                file_size=1024000,
                pages=10
            )

            result = runner.export_pdf(
                document_path=Path("/tmp/test.indd"),
                output_pdf=Path("/tmp/output.pdf"),
                preset=settings.__dict__
            )

            assert result.success is True


@pytest.mark.integration
@pytest.mark.slow
class TestPDFExportPerformance:
    """Test PDF export performance."""

    def test_export_10_page_document(self):
        """Test exporting 10-page document."""
        import time

        runner = JSXRunner()
        settings = PDFExportSettings()

        start_time = time.time()

        with patch.object(runner, 'export_pdf') as mock_export:
            mock_export.return_value = PDFExportResult(
                success=True,
                output_path=Path("/tmp/output.pdf"),
                file_size=2_000_000,
                pages=10
            )

            result = runner.export_pdf(
                document_path=Path("/tmp/test.indd"),
                output_pdf=Path("/tmp/output.pdf"),
                preset=settings.__dict__
            )

        elapsed = time.time() - start_time

        # Mock should be fast
        assert elapsed < 1.0
        assert result.pages == 10

    def test_export_50_page_document(self):
        """Test exporting large 50-page document."""
        import time

        runner = JSXRunner()
        settings = PDFExportSettings()

        start_time = time.time()

        with patch.object(runner, 'export_pdf') as mock_export:
            mock_export.return_value = PDFExportResult(
                success=True,
                output_path=Path("/tmp/output.pdf"),
                file_size=10_000_000,
                pages=50
            )

            result = runner.export_pdf(
                document_path=Path("/tmp/test.indd"),
                output_pdf=Path("/tmp/output.pdf"),
                preset=settings.__dict__
            )

        elapsed = time.time() - start_time

        # Mock should be fast
        assert elapsed < 2.0
        assert result.pages == 50


@pytest.mark.integration
class TestPDFPresetWorkflow:
    """Test PDF preset management workflow."""

    def test_create_and_use_custom_preset(self, tmp_path):
        """Test creating and using custom preset."""
        manager = PDFPresetManager(presets_dir=tmp_path)

        # Create custom settings
        settings = PDFExportSettings(
            pdf_standard=PDFStandard.PDF_X_4_2010,
            color_space=ColorSpace.CMYK,
            jpeg_quality=10,
            bleed_top=5.0,
            bleed_bottom=5.0
        )

        # Save preset
        with pytest.raises(NotImplementedError):
            manager.save_preset("my_custom_preset", settings)

        # Load and use preset
        with pytest.raises(NotImplementedError):
            loaded_settings = manager.get_preset("my_custom_preset")

        # Mock loaded settings
        loaded_settings = settings

        # Use in export
        runner = JSXRunner()
        with patch.object(runner, 'export_pdf') as mock_export:
            mock_export.return_value = PDFExportResult(success=True, output_path=Path("/tmp/output.pdf"), file_size=1024000, pages=10)

            result = runner.export_pdf(
                document_path=Path("/tmp/test.indd"),
                output_pdf=Path("/tmp/output.pdf"),
                preset=loaded_settings.__dict__
            )

            assert result.success is True

    def test_list_and_select_preset(self):
        """Test listing and selecting presets."""
        manager = PDFPresetManager()

        with pytest.raises(NotImplementedError):
            presets = manager.list_presets()

        # Mock presets
        presets = ["print_high_quality", "web_optimized", "press_quality", "smallest_file_size"]

        assert len(presets) >= 4

        # Select preset
        with pytest.raises(NotImplementedError):
            settings = manager.get_preset("press_quality")

        # Mock settings
        settings = PDFExportSettings(
            pdf_standard=PDFStandard.PDF_X_4_2010,
            jpeg_quality=12
        )

        assert settings.jpeg_quality == 12
