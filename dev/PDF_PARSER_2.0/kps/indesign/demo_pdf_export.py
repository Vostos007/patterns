#!/usr/bin/env python3
"""
PDF Export System Demo

Demonstrates the complete PDF/X-4 export workflow including:
- Loading presets
- Customizing settings
- Generating JSX scripts
- Validating PDFs

Run: python demo_pdf_export.py
"""

from pathlib import Path
import sys

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from kps.indesign.pdf_export import (
    PDFExportSettings,
    PDFStandard,
    ColorSpace,
    CompressionType,
    ImageQuality,
    PDFExporter,
    get_print_high_quality_preset,
    get_print_medium_quality_preset,
    get_screen_optimized_preset,
    get_proof_preset
)

from kps.indesign.pdf_presets import PDFPresetManager, PresetValidator
from kps.indesign.pdf_validator import PDFValidator, PDFValidationReport


def print_section(title: str):
    """Print section header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def demo_basic_settings():
    """Demo 1: Basic export settings"""
    print_section("Demo 1: Basic Export Settings")

    # Create default settings
    settings = PDFExportSettings()

    print("\nDefault Settings:")
    print(f"  PDF Standard: {settings.pdf_standard.value}")
    print(f"  Color Space: {settings.color_space.value}")
    print(f"  JPEG Quality: {settings.jpeg_quality}/12")
    print(f"  Include Bleed: {settings.include_bleed}")
    print(f"  Crop Marks: {settings.crop_marks}")

    # Validate
    errors = settings.validate()
    if errors:
        print("\n⚠ Validation errors:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("\n✓ Settings are valid")

    # Show JSX generation
    jsx = settings.to_jsx_script()
    print(f"\nGenerated JSX script: {len(jsx)} characters")
    print("\nFirst 300 characters:")
    print(jsx[:300] + "...")


def demo_presets():
    """Demo 2: Using built-in presets"""
    print_section("Demo 2: Built-in Presets")

    presets = {
        'print_high_quality': get_print_high_quality_preset(),
        'print_medium_quality': get_print_medium_quality_preset(),
        'screen_optimized': get_screen_optimized_preset(),
        'proof': get_proof_preset()
    }

    print("\nBuilt-in Presets:")
    for name, preset in presets.items():
        print(f"\n  {name}:")
        print(f"    Standard: {preset.pdf_standard.value}")
        print(f"    Color: {preset.color_space.value}")
        print(f"    JPEG Quality: {preset.jpeg_quality}")
        print(f"    Downsample: {preset.downsample_images}")
        if preset.downsample_images:
            print(f"    Downsample to: {preset.downsample_color_to} DPI")


def demo_preset_manager():
    """Demo 3: Preset manager"""
    print_section("Demo 3: Preset Manager")

    manager = PDFPresetManager()

    print("\nAvailable presets:")
    for name, description in manager.list_presets().items():
        print(f"  - {name}: {description}")

    # Get a preset
    print("\nLoading 'print_high_quality' preset:")
    settings = manager.get_preset("print_high_quality")
    print(f"  ✓ Loaded: {settings.pdf_standard.value}")

    # Create custom preset
    print("\nCreating custom preset:")
    custom = PDFExportSettings(
        pdf_standard=PDFStandard.PDF_X_4_2010,
        color_space=ColorSpace.CMYK,
        jpeg_quality=11,
        include_bleed=True
    )
    manager.add_preset("demo_custom", custom, "Demo custom preset")
    print(f"  ✓ Added 'demo_custom' preset")

    # List again
    print("\nUpdated preset list:")
    for name in manager.list_presets().keys():
        print(f"  - {name}")


def demo_yaml_presets():
    """Demo 4: YAML preset loading"""
    print_section("Demo 4: YAML Preset Configuration")

    # Check if YAML file exists
    yaml_path = Path(__file__).parent.parent.parent / "config" / "pdf_export_presets.yaml"

    if yaml_path.exists():
        print(f"\nLoading presets from: {yaml_path}")

        manager = PDFPresetManager()
        count = manager.load_presets_from_yaml(yaml_path)

        print(f"✓ Loaded {count} presets")

        # Show some presets
        print("\nSample presets from YAML:")
        for name in list(manager.list_presets().keys())[:5]:
            try:
                preset = manager.get_preset(name)
                print(f"  - {name}: {preset.pdf_standard.value}, {preset.color_space.value}")
            except:
                pass
    else:
        print(f"\n⚠ YAML file not found: {yaml_path}")
        print("  (This is normal if running demo standalone)")


def demo_custom_settings():
    """Demo 5: Custom settings"""
    print_section("Demo 5: Custom Export Settings")

    # Create highly customized settings
    settings = PDFExportSettings(
        pdf_standard=PDFStandard.PDF_X_4_2010,
        compatibility=CompatibilityLevel.ACROBAT_7,

        # Color
        color_space=ColorSpace.CMYK,
        output_intent="Coated FOGRA39 (ISO 12647-2:2004)",
        include_icc_profile=True,
        simulate_overprint=True,

        # Quality
        image_quality=ImageQuality.MAXIMUM,
        compression=CompressionType.JPEG,
        jpeg_quality=12,
        downsample_images=False,
        resolution_threshold=450,

        # Bleed
        include_bleed=True,
        bleed_top=5.0,  # 5mm bleed
        bleed_bottom=5.0,
        bleed_left=5.0,
        bleed_right=5.0,

        # Marks
        crop_marks=True,
        registration_marks=True,
        color_bars=True,
        page_information=True,

        # Advanced
        create_acrobat_layers=True,
        include_structure=True,
        include_bookmarks=True,
        transparency_flattener_preset="High Resolution",
        optimize_pdf=True
    )

    print("\nCustom Settings Summary:")
    print(f"  Standard: {settings.pdf_standard.value}")
    print(f"  Color Space: {settings.color_space.value}")
    print(f"  Output Intent: {settings.output_intent}")
    print(f"  JPEG Quality: {settings.jpeg_quality}/12")
    print(f"  Bleed: {settings.bleed_top}mm")
    print(f"  Crop Marks: {settings.crop_marks}")
    print(f"  Registration Marks: {settings.registration_marks}")

    # Validate
    errors = settings.validate()
    print(f"\n✓ Validation: {'PASSED' if not errors else 'FAILED'}")
    if errors:
        for error in errors:
            print(f"  - {error}")

    # Convert to different formats
    print("\nSerialization:")
    json_str = settings.to_json()
    print(f"  JSON: {len(json_str)} characters")

    dict_data = settings.to_dict()
    print(f"  Dict: {len(dict_data)} keys")

    # Roundtrip test
    restored = PDFExportSettings.from_json(json_str)
    print(f"  Roundtrip: {'✓ OK' if restored.jpeg_quality == settings.jpeg_quality else '✗ FAILED'}")


def demo_validation_tools():
    """Demo 6: Validation tools"""
    print_section("Demo 6: PDF Validation Tools")

    validator = PDFValidator(min_dpi=300)

    print("\nValidation Tool Availability:")
    for tool, available in validator.tool_availability.items():
        status = "✓ Available" if available else "✗ Not available"
        print(f"  {tool}: {status}")

    if not any(validator.tool_availability.values()):
        print("\n⚠ No validation tools available")
        print("  Install for full validation:")
        print("    - PyMuPDF: pip install pymupdf")
        print("    - Ghostscript: brew install ghostscript")
        print("    - Poppler: brew install poppler")
    else:
        print("\n✓ Validation tools ready")


def demo_validation_report():
    """Demo 7: Validation report structure"""
    print_section("Demo 7: Validation Report Structure")

    # Create a demo report
    report = PDFValidationReport(
        is_valid=True,
        pdf_version="1.6",
        pdf_standard="PDF/X-4:2010",
        page_count=24,
        file_size=15_234_567,
        color_space="CMYK",
        has_output_intent=True,
        output_intent_name="Coated FOGRA39 (ISO 12647-2:2004)",
        embedded_fonts=["Helvetica-Bold", "Times-Roman", "Arial"],
        unembedded_fonts=[],
        resolution_issues=[],
        compliance_errors=[],
        warnings=["No transparency flattening detected"],
        validation_time=2.34,
        tool_availability={'pymupdf': True, 'ghostscript': True}
    )

    print("\nSample Validation Report:")
    print(report)

    print("\nReport as Dictionary:")
    report_dict = report.to_dict()
    for key, value in list(report_dict.items())[:8]:
        print(f"  {key}: {value}")


def demo_export_workflow():
    """Demo 8: Complete export workflow"""
    print_section("Demo 8: Export Workflow (Simulated)")

    print("\nComplete Export Workflow:")
    print("  1. Load preset manager")
    print("  2. Select or create preset")
    print("  3. Validate settings")
    print("  4. Generate JSX script")
    print("  5. Execute export (via JSX runner)")
    print("  6. Validate output PDF")
    print("  7. Generate report")

    print("\nExample code:")
    code = '''
from pathlib import Path
from kps.indesign.pdf_export import PDFExporter, get_print_high_quality_preset

# Setup
exporter = PDFExporter()
settings = get_print_high_quality_preset()

# Export
report = exporter.export_to_pdfx4(
    indesign_doc=Path("pattern.indd"),
    output_pdf=Path("pattern_print.pdf"),
    preset=settings
)

# Check result
if report.is_valid:
    print(f"✓ Export successful: {report.page_count} pages")
else:
    print("✗ Validation errors:", report.compliance_errors)
'''
    print(code)


def main():
    """Run all demos"""
    print("\n" + "=" * 70)
    print("  PDF/X-4 Export System Demo")
    print("  KPS v2.0 - Agent 4")
    print("=" * 70)

    demos = [
        demo_basic_settings,
        demo_presets,
        demo_preset_manager,
        demo_yaml_presets,
        demo_custom_settings,
        demo_validation_tools,
        demo_validation_report,
        demo_export_workflow
    ]

    for demo in demos:
        try:
            demo()
        except Exception as e:
            print(f"\n⚠ Demo error: {e}")

    print("\n" + "=" * 70)
    print("  Demo Complete")
    print("=" * 70)
    print("\nFor more information, see:")
    print("  - kps/indesign/PDF_EXPORT_GUIDE.md")
    print("  - tests/test_pdf_export.py")
    print("\n")


if __name__ == "__main__":
    main()
