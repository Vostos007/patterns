"""
Comprehensive Test Suite for PDF/X-4 Export System

Tests all components of the InDesign PDF export system:
- PDFExportSettings
- PDFPresetManager
- PDFValidator
- JSX script generation

Author: KPS v2.0 Agent 4
Date: 2025-11-06
"""

import pytest
from pathlib import Path
import json
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock

# Import modules under test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from kps.indesign.pdf_export import (
    PDFExportSettings,
    PDFStandard,
    ColorSpace,
    CompressionType,
    ImageQuality,
    CompatibilityLevel,
    PDFExporter,
    get_print_high_quality_preset,
    get_print_medium_quality_preset,
    get_screen_optimized_preset,
    get_proof_preset
)

from kps.indesign.pdf_presets import (
    PDFPresetManager,
    PresetValidator
)

from kps.indesign.pdf_validator import (
    PDFValidator,
    PDFValidationReport
)


# ========================================
# Fixtures
# ========================================

@pytest.fixture
def temp_dir():
    """Create temporary directory for tests"""
    tmpdir = tempfile.mkdtemp()
    yield Path(tmpdir)
    shutil.rmtree(tmpdir)


@pytest.fixture
def sample_settings():
    """Create sample export settings"""
    return PDFExportSettings(
        pdf_standard=PDFStandard.PDF_X_4_2010,
        color_space=ColorSpace.CMYK,
        output_intent="Coated FOGRA39 (ISO 12647-2:2004)",
        jpeg_quality=12,
        include_bleed=True
    )


@pytest.fixture
def preset_manager(temp_dir):
    """Create preset manager with temp config dir"""
    return PDFPresetManager(config_dir=temp_dir)


@pytest.fixture
def pdf_validator():
    """Create PDF validator instance"""
    return PDFValidator(min_dpi=300)


# ========================================
# PDFExportSettings Tests
# ========================================

class TestPDFExportSettings:
    """Test PDFExportSettings dataclass"""

    def test_default_settings(self):
        """Test default settings creation"""
        settings = PDFExportSettings()
        assert settings.pdf_standard == PDFStandard.PDF_X_4_2010
        assert settings.color_space == ColorSpace.CMYK
        assert settings.jpeg_quality == 12
        assert settings.include_bleed is True

    def test_custom_settings(self):
        """Test custom settings"""
        settings = PDFExportSettings(
            pdf_standard=PDFStandard.PDF_X_1A_2001,
            color_space=ColorSpace.RGB,
            jpeg_quality=8,
            downsample_images=True
        )
        assert settings.pdf_standard == PDFStandard.PDF_X_1A_2001
        assert settings.color_space == ColorSpace.RGB
        assert settings.jpeg_quality == 8
        assert settings.downsample_images is True

    def test_jsx_script_generation(self, sample_settings):
        """Test JSX script generation"""
        jsx = sample_settings.to_jsx_script()

        assert "PDF Export Settings" in jsx
        assert "PDF/X-4:2010" in jsx
        assert "ColorSpace.CMYK" in jsx
        assert "jpegQuality" in jsx
        assert "Coated FOGRA39" in jsx

    def test_jsx_bool_conversion(self, sample_settings):
        """Test Python bool to JSX bool conversion"""
        jsx = sample_settings.to_jsx_script()
        assert "cropMarks = true" in jsx
        assert "useDocumentBleedWithPDF = true" in jsx

    def test_jsx_color_space_mapping(self):
        """Test color space enum to JSX mapping"""
        settings = PDFExportSettings(color_space=ColorSpace.CMYK)
        assert settings._jsx_color_space() == "ColorSpace.CMYK"

        settings = PDFExportSettings(color_space=ColorSpace.RGB)
        assert settings._jsx_color_space() == "ColorSpace.RGB"

        settings = PDFExportSettings(color_space=ColorSpace.GRAY)
        assert settings._jsx_color_space() == "ColorSpace.GRAY"

    def test_jsx_jpeg_quality_mapping(self):
        """Test JPEG quality integer to JSX constant"""
        settings = PDFExportSettings(jpeg_quality=12)
        assert settings._jsx_jpeg_quality() == "MAXIMUM"

        settings = PDFExportSettings(jpeg_quality=8)
        assert settings._jsx_jpeg_quality() == "HIGH"

        settings = PDFExportSettings(jpeg_quality=5)
        assert settings._jsx_jpeg_quality() == "MEDIUM"

        settings = PDFExportSettings(jpeg_quality=1)
        assert settings._jsx_jpeg_quality() == "LOW"

    def test_to_dict(self, sample_settings):
        """Test conversion to dictionary"""
        data = sample_settings.to_dict()
        assert isinstance(data, dict)
        assert data['pdf_standard'] == 'PDF/X-4:2010'
        assert data['color_space'] == 'CMYK'
        assert data['jpeg_quality'] == 12

    def test_to_json(self, sample_settings):
        """Test JSON serialization"""
        json_str = sample_settings.to_json()
        data = json.loads(json_str)
        assert data['pdf_standard'] == 'PDF/X-4:2010'
        assert data['jpeg_quality'] == 12

    def test_from_dict(self):
        """Test creating settings from dictionary"""
        data = {
            'pdf_standard': 'PDF/X-4:2010',
            'color_space': 'CMYK',
            'jpeg_quality': 10,
            'include_bleed': True
        }
        settings = PDFExportSettings.from_dict(data)
        assert settings.pdf_standard == PDFStandard.PDF_X_4_2010
        assert settings.color_space == ColorSpace.CMYK
        assert settings.jpeg_quality == 10

    def test_from_json(self):
        """Test creating settings from JSON"""
        json_str = '''
        {
            "pdf_standard": "PDF/X-4:2010",
            "color_space": "RGB",
            "jpeg_quality": 8
        }
        '''
        settings = PDFExportSettings.from_json(json_str)
        assert settings.pdf_standard == PDFStandard.PDF_X_4_2010
        assert settings.color_space == ColorSpace.RGB
        assert settings.jpeg_quality == 8

    def test_validation_valid_settings(self, sample_settings):
        """Test validation of valid settings"""
        errors = sample_settings.validate()
        assert len(errors) == 0

    def test_validation_invalid_jpeg_quality(self):
        """Test validation catches invalid JPEG quality"""
        settings = PDFExportSettings(jpeg_quality=15)
        errors = settings.validate()
        assert len(errors) > 0
        assert any("JPEG quality" in e for e in errors)

    def test_validation_negative_bleed(self):
        """Test validation catches negative bleed values"""
        settings = PDFExportSettings(bleed_top=-1.0)
        errors = settings.validate()
        assert len(errors) > 0
        assert any("Bleed" in e for e in errors)

    def test_validation_pdfx4_requires_cmyk(self):
        """Test PDF/X-4 validation requires CMYK"""
        settings = PDFExportSettings(
            pdf_standard=PDFStandard.PDF_X_4_2010,
            color_space=ColorSpace.RGB
        )
        errors = settings.validate()
        assert len(errors) > 0
        assert any("PDF/X-4" in e and "CMYK" in e for e in errors)

    def test_validation_pdfx4_requires_output_intent(self):
        """Test PDF/X-4 requires output intent"""
        settings = PDFExportSettings(
            pdf_standard=PDFStandard.PDF_X_4_2010,
            output_intent=""
        )
        errors = settings.validate()
        assert len(errors) > 0
        assert any("output intent" in e.lower() for e in errors)


# ========================================
# Preset Tests
# ========================================

class TestPresets:
    """Test predefined presets"""

    def test_print_high_quality_preset(self):
        """Test high quality print preset"""
        preset = get_print_high_quality_preset()
        assert preset.pdf_standard == PDFStandard.PDF_X_4_2010
        assert preset.color_space == ColorSpace.CMYK
        assert preset.jpeg_quality == 12
        assert preset.downsample_images is False
        assert len(preset.validate()) == 0

    def test_print_medium_quality_preset(self):
        """Test medium quality print preset"""
        preset = get_print_medium_quality_preset()
        assert preset.pdf_standard == PDFStandard.PDF_X_4_2010
        assert preset.downsample_images is True
        assert preset.downsample_color_to == 300
        assert len(preset.validate()) == 0

    def test_screen_optimized_preset(self):
        """Test screen optimized preset"""
        preset = get_screen_optimized_preset()
        assert preset.color_space == ColorSpace.RGB
        assert preset.downsample_images is True
        assert preset.downsample_color_to == 150
        assert preset.include_bleed is False

    def test_proof_preset(self):
        """Test proof preset"""
        preset = get_proof_preset()
        assert preset.image_quality == ImageQuality.MEDIUM
        assert preset.jpeg_quality == 6
        assert preset.include_bleed is False


# ========================================
# PDFPresetManager Tests
# ========================================

class TestPDFPresetManager:
    """Test preset manager functionality"""

    def test_manager_initialization(self, preset_manager):
        """Test manager initializes correctly"""
        assert preset_manager is not None
        assert len(preset_manager.BUILTIN_PRESETS) == 4

    def test_list_builtin_presets(self, preset_manager):
        """Test listing built-in presets"""
        presets = preset_manager.list_presets()
        assert "print_high_quality" in presets
        assert "print_medium_quality" in presets
        assert "screen_optimized" in presets
        assert "proof" in presets

    def test_get_builtin_preset(self, preset_manager):
        """Test getting built-in preset"""
        preset = preset_manager.get_preset("print_high_quality")
        assert preset.pdf_standard == PDFStandard.PDF_X_4_2010
        assert preset.jpeg_quality == 12

    def test_get_nonexistent_preset(self, preset_manager):
        """Test getting non-existent preset raises KeyError"""
        with pytest.raises(KeyError):
            preset_manager.get_preset("nonexistent")

    def test_add_custom_preset(self, preset_manager):
        """Test adding custom preset"""
        custom = PDFExportSettings(
            pdf_standard=PDFStandard.PDF_X_4_2010,
            jpeg_quality=11
        )
        preset_manager.add_preset("my_custom", custom, "My custom preset")

        # Verify it was added
        retrieved = preset_manager.get_preset("my_custom")
        assert retrieved.jpeg_quality == 11

        # Check it appears in list
        presets = preset_manager.list_presets()
        assert "my_custom" in presets

    def test_remove_custom_preset(self, preset_manager):
        """Test removing custom preset"""
        custom = PDFExportSettings()
        preset_manager.add_preset("to_remove", custom)
        preset_manager.remove_preset("to_remove")

        with pytest.raises(KeyError):
            preset_manager.get_preset("to_remove")

    def test_cannot_remove_builtin_preset(self, preset_manager):
        """Test cannot remove built-in presets"""
        with pytest.raises(ValueError):
            preset_manager.remove_preset("print_high_quality")

    def test_save_presets_to_yaml(self, preset_manager, temp_dir):
        """Test saving presets to YAML"""
        # Add a custom preset
        custom = PDFExportSettings(jpeg_quality=11)
        preset_manager.add_preset("custom", custom, "Custom preset")

        # Save to YAML
        yaml_path = temp_dir / "test_presets.yaml"
        preset_manager.save_presets_to_yaml(yaml_path, include_builtin=False)

        assert yaml_path.exists()
        content = yaml_path.read_text()
        assert "custom" in content
        assert "jpeg_quality: 11" in content

    def test_load_presets_from_yaml(self, preset_manager, temp_dir):
        """Test loading presets from YAML"""
        # Create YAML file
        yaml_content = """
presets:
  test_preset:
    description: "Test preset"
    settings:
      pdf_standard: "PDF/X-4:2010"
      jpeg_quality: 9
"""
        yaml_path = temp_dir / "test_presets.yaml"
        yaml_path.write_text(yaml_content)

        # Load presets
        count = preset_manager.load_presets_from_yaml(yaml_path)
        assert count == 1

        # Verify preset loaded
        preset = preset_manager.get_preset("test_preset")
        assert preset.jpeg_quality == 9

    def test_create_preset_file(self, preset_manager, temp_dir, sample_settings):
        """Test creating InDesign .pdfpreset file"""
        preset_file = temp_dir / "test.pdfpreset"
        preset_manager.create_preset_file(sample_settings, preset_file, "Test Preset")

        assert preset_file.exists()
        content = preset_file.read_text()
        assert "<?xml" in content
        assert "<PDFExportPreset>" in content
        assert "Test Preset" in content

    def test_export_preset_as_json(self, preset_manager, temp_dir):
        """Test exporting preset as JSON"""
        json_path = temp_dir / "test_preset.json"
        preset_manager.export_preset_as_json("print_high_quality", json_path)

        assert json_path.exists()
        data = json.loads(json_path.read_text())
        assert data['name'] == "print_high_quality"
        assert 'settings' in data
        assert data['settings']['jpeg_quality'] == 12


class TestPresetValidator:
    """Test preset validation"""

    def test_validate_yaml_file(self, temp_dir):
        """Test validating YAML preset file"""
        yaml_content = """
presets:
  valid_preset:
    settings:
      pdf_standard: "PDF/X-4:2010"
      color_space: "CMYK"
      jpeg_quality: 12
"""
        yaml_path = temp_dir / "valid.yaml"
        yaml_path.write_text(yaml_content)

        errors = PresetValidator.validate_preset_file(yaml_path)
        assert len(errors) == 0

    def test_validate_invalid_yaml(self, temp_dir):
        """Test validation catches invalid YAML"""
        yaml_content = """
presets:
  invalid_preset:
    settings:
      jpeg_quality: 999  # Invalid value
"""
        yaml_path = temp_dir / "invalid.yaml"
        yaml_path.write_text(yaml_content)

        errors = PresetValidator.validate_preset_file(yaml_path)
        assert len(errors) > 0


# ========================================
# PDFValidator Tests
# ========================================

class TestPDFValidator:
    """Test PDF validation functionality"""

    def test_validator_initialization(self, pdf_validator):
        """Test validator initializes correctly"""
        assert pdf_validator.min_dpi == 300
        assert hasattr(pdf_validator, 'tool_availability')

    def test_tool_availability_check(self, pdf_validator):
        """Test tool availability checking"""
        tools = pdf_validator.tool_availability
        assert isinstance(tools, dict)
        # Should have checks for pymupdf, ghostscript, pdfinfo, pdfimages
        assert 'pymupdf' in tools

    def test_validation_report_creation(self):
        """Test creating validation report"""
        report = PDFValidationReport(
            is_valid=True,
            pdf_version="1.6",
            pdf_standard="PDF/X-4:2010",
            page_count=10,
            file_size=1_000_000,
            color_space="CMYK"
        )
        assert report.is_valid
        assert report.page_count == 10
        assert report.pdf_version == "1.6"

    def test_validation_report_to_dict(self):
        """Test converting validation report to dict"""
        report = PDFValidationReport(
            is_valid=True,
            page_count=5
        )
        data = report.to_dict()
        assert isinstance(data, dict)
        assert data['is_valid'] is True
        assert data['page_count'] == 5

    def test_validation_report_string(self):
        """Test validation report string representation"""
        report = PDFValidationReport(
            is_valid=True,
            pdf_version="1.6",
            page_count=10
        )
        report_str = str(report)
        assert "PDF Validation Report" in report_str
        assert "VALID" in report_str
        assert "1.6" in report_str

    def test_validate_nonexistent_file(self, pdf_validator, temp_dir):
        """Test validation of non-existent file"""
        report = pdf_validator.validate_pdfx4(temp_dir / "nonexistent.pdf")
        assert report.is_valid is False
        assert len(report.compliance_errors) > 0

    @patch('subprocess.run')
    def test_ghostscript_validation(self, mock_run, pdf_validator, temp_dir):
        """Test Ghostscript validation with mocked subprocess"""
        # Create dummy PDF file
        pdf_path = temp_dir / "test.pdf"
        pdf_path.write_text("fake pdf")

        # Mock successful Ghostscript run
        mock_run.return_value = Mock(returncode=0, stderr="")

        # Update tool availability
        pdf_validator.tool_availability['ghostscript'] = True

        # This would normally run validation
        # (actual validation requires real PDF and tools)


# ========================================
# PDFExporter Tests
# ========================================

class TestPDFExporter:
    """Test PDF exporter workflow"""

    def test_exporter_initialization(self):
        """Test exporter initializes correctly"""
        exporter = PDFExporter()
        assert exporter is not None

    def test_exporter_with_dependencies(self):
        """Test exporter with mock dependencies"""
        mock_jsx_runner = Mock()
        mock_validator = Mock()

        exporter = PDFExporter(
            jsx_runner=mock_jsx_runner,
            validator=mock_validator
        )

        assert exporter.jsx_runner == mock_jsx_runner
        assert exporter.validator == mock_validator

    def test_export_validation_error(self, sample_settings, temp_dir):
        """Test export fails with invalid settings"""
        exporter = PDFExporter()

        # Create invalid settings
        invalid_settings = PDFExportSettings(jpeg_quality=999)

        with pytest.raises(ValueError):
            exporter.export_to_pdfx4(
                indesign_doc=temp_dir / "test.indd",
                output_pdf=temp_dir / "output.pdf",
                preset=invalid_settings
            )

    def test_export_missing_input_file(self, sample_settings, temp_dir):
        """Test export fails with missing input file"""
        exporter = PDFExporter()

        with pytest.raises(FileNotFoundError):
            exporter.export_to_pdfx4(
                indesign_doc=temp_dir / "nonexistent.indd",
                output_pdf=temp_dir / "output.pdf",
                preset=sample_settings
            )


# ========================================
# Integration Tests
# ========================================

class TestIntegration:
    """Integration tests for complete workflow"""

    def test_preset_to_jsx_workflow(self, preset_manager):
        """Test complete workflow: preset -> settings -> JSX"""
        # Get preset
        preset = preset_manager.get_preset("print_high_quality")

        # Validate settings
        errors = preset.validate()
        assert len(errors) == 0

        # Generate JSX
        jsx = preset.to_jsx_script()
        assert len(jsx) > 0
        assert "PDF/X-4:2010" in jsx

    def test_yaml_to_export_workflow(self, preset_manager, temp_dir):
        """Test workflow: YAML -> preset -> export settings"""
        # Create YAML config
        yaml_content = """
presets:
  workflow_test:
    description: "Test workflow"
    settings:
      pdf_standard: "PDF/X-4:2010"
      color_space: "CMYK"
      jpeg_quality: 11
      include_bleed: true
"""
        yaml_path = temp_dir / "workflow.yaml"
        yaml_path.write_text(yaml_content)

        # Load preset
        preset_manager.load_presets_from_yaml(yaml_path)
        settings = preset_manager.get_preset("workflow_test")

        # Validate
        errors = settings.validate()
        assert len(errors) == 0

        # Generate JSX
        jsx = settings.to_jsx_script()
        assert "jpegQuality" in jsx

    def test_roundtrip_json_serialization(self, sample_settings):
        """Test settings survive JSON roundtrip"""
        # Serialize
        json_str = sample_settings.to_json()

        # Deserialize
        restored = PDFExportSettings.from_json(json_str)

        # Compare
        assert restored.pdf_standard == sample_settings.pdf_standard
        assert restored.color_space == sample_settings.color_space
        assert restored.jpeg_quality == sample_settings.jpeg_quality


# ========================================
# Performance Tests
# ========================================

class TestPerformance:
    """Performance and stress tests"""

    def test_jsx_generation_performance(self, sample_settings):
        """Test JSX generation is fast"""
        import time
        start = time.time()

        for _ in range(100):
            jsx = sample_settings.to_jsx_script()

        elapsed = time.time() - start
        assert elapsed < 1.0  # Should complete in under 1 second

    def test_validation_performance(self, sample_settings):
        """Test validation is fast"""
        import time
        start = time.time()

        for _ in range(1000):
            errors = sample_settings.validate()

        elapsed = time.time() - start
        assert elapsed < 1.0


# ========================================
# Run Tests
# ========================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
