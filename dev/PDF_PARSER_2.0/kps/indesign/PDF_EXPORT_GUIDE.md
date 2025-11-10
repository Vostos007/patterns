# PDF/X-4 Export System Guide

**KPS v2.0 - InDesign Automation Component**
**Agent 4: PDF/X-4 Export Configuration**
**Version:** 1.0
**Date:** 2025-11-06

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Quick Start](#quick-start)
4. [Components](#components)
5. [Export Workflow](#export-workflow)
6. [Presets](#presets)
7. [Validation](#validation)
8. [Configuration](#configuration)
9. [API Reference](#api-reference)
10. [Best Practices](#best-practices)
11. [Troubleshooting](#troubleshooting)
12. [Examples](#examples)

---

## Overview

The PDF/X-4 Export System provides comprehensive PDF export configuration and validation for InDesign automation. It enables programmatic control over all aspects of PDF export, ensuring compliance with print production standards.

### Key Features

- **Complete PDF/X-4:2010 Compliance**: Full support for PDF/X-4:2010 standard with ICC color profiles
- **Flexible Preset System**: Built-in and custom presets for different use cases
- **JSX Script Generation**: Automatic generation of InDesign ExtendScript for PDF export
- **Comprehensive Validation**: Multi-tool PDF validation with detailed reports
- **YAML Configuration**: Easy preset management via YAML files
- **Production Ready**: Robust error handling and validation

### Standards Supported

- PDF/X-4:2010 (recommended for print)
- PDF/X-1a:2001 (legacy print standard)
- PDF/X-3:2002 (print with RGB/Lab support)
- PDF/A-1b:2005 (archival)
- High Quality Print
- Press Quality

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    PDF Export System                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │ PDF Export   │  │   Preset     │  │   PDF           │  │
│  │  Settings    │←─│   Manager    │  │  Validator      │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬────────┘  │
│         │                  │                    │           │
│         ↓                  ↓                    ↓           │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              PDFExporter (Orchestrator)              │  │
│  └────────────────────────┬─────────────────────────────┘  │
│                           │                                │
│                           ↓                                │
│         ┌─────────────────────────────────┐               │
│         │  JSX Runner → InDesign Server   │               │
│         └─────────────────────────────────┘               │
│                           │                                │
│                           ↓                                │
│                   ┌───────────────┐                        │
│                   │  PDF/X-4 File │                        │
│                   └───────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

### Component Overview

1. **PDFExportSettings**: Dataclass defining all export parameters
2. **PDFPresetManager**: Manages built-in and custom presets
3. **PDFValidator**: Validates PDF compliance and quality
4. **PDFExporter**: Orchestrates the complete export workflow
5. **JSX Export Script**: ExtendScript for InDesign PDF export

---

## Quick Start

### Basic Export

```python
from pathlib import Path
from kps.indesign.pdf_export import PDFExporter, get_print_high_quality_preset

# Create exporter
exporter = PDFExporter()

# Get high-quality print preset
settings = get_print_high_quality_preset()

# Export to PDF/X-4
report = exporter.export_to_pdfx4(
    indesign_doc=Path("pattern.indd"),
    output_pdf=Path("pattern_print.pdf"),
    preset=settings
)

# Check validation
if report.is_valid:
    print("✓ Export successful and PDF/X-4 compliant")
else:
    print("✗ Validation errors:")
    for error in report.compliance_errors:
        print(f"  - {error}")
```

### Using Presets

```python
from kps.indesign.pdf_presets import PDFPresetManager

# Load preset manager
manager = PDFPresetManager()

# List available presets
presets = manager.list_presets()
print("Available presets:", list(presets.keys()))

# Get specific preset
settings = manager.get_preset("print_high_quality")

# Load custom presets from YAML
manager.load_presets_from_yaml(Path("config/pdf_export_presets.yaml"))
custom_settings = manager.get_preset("magazine_print")
```

### Custom Settings

```python
from kps.indesign.pdf_export import (
    PDFExportSettings,
    PDFStandard,
    ColorSpace,
    ImageQuality
)

# Create custom settings
settings = PDFExportSettings(
    pdf_standard=PDFStandard.PDF_X_4_2010,
    color_space=ColorSpace.CMYK,
    output_intent="Coated FOGRA39 (ISO 12647-2:2004)",
    image_quality=ImageQuality.MAXIMUM,
    jpeg_quality=12,
    include_bleed=True,
    bleed_top=3.0,
    bleed_bottom=3.0,
    bleed_left=3.0,
    bleed_right=3.0,
    crop_marks=True,
    registration_marks=True
)

# Validate settings
errors = settings.validate()
if errors:
    print("Settings invalid:", errors)
else:
    print("Settings valid")
```

---

## Components

### PDFExportSettings

Comprehensive dataclass for all PDF export parameters.

#### Key Attributes

**Standard & Compatibility**
- `pdf_standard`: PDF standard (PDF/X-4:2010, etc.)
- `compatibility`: Acrobat compatibility level

**Color Management**
- `color_space`: CMYK, RGB, Grayscale
- `output_intent`: ICC profile name
- `include_icc_profile`: Embed ICC profile
- `simulate_overprint`: Simulate overprint for transparency

**Image Quality**
- `image_quality`: Maximum, High, Medium, Low
- `compression`: JPEG, ZIP, JPEG2000
- `jpeg_quality`: 0-12 (12 = maximum)
- `downsample_images`: Enable downsampling
- `resolution_threshold`: Minimum DPI before downsampling

**Marks and Bleeds**
- `include_bleed`: Enable bleed
- `bleed_top/bottom/left/right`: Bleed dimensions (mm)
- `crop_marks`: Show crop marks
- `registration_marks`: Show registration marks
- `color_bars`: Show color bars
- `page_information`: Show page info

**Fonts**
- `embed_fonts`: Embed all fonts
- `subset_fonts_threshold`: Subset threshold %

**Advanced**
- `create_acrobat_layers`: Create Acrobat layers
- `include_structure`: Include PDF structure (tags)
- `include_bookmarks`: Include bookmarks
- `include_hyperlinks`: Include hyperlinks
- `transparency_flattener_preset`: Transparency handling

#### Methods

```python
# Generate JSX script
jsx_script = settings.to_jsx_script()

# Serialize/deserialize
json_str = settings.to_json()
dict_data = settings.to_dict()
settings = PDFExportSettings.from_json(json_str)
settings = PDFExportSettings.from_dict(dict_data)

# Validate
errors = settings.validate()
```

### PDFPresetManager

Manages export presets with YAML configuration support.

#### Built-in Presets

- `print_high_quality`: Maximum quality print (PDF/X-4, no compression)
- `print_medium_quality`: Standard print (PDF/X-4, 300 DPI)
- `screen_optimized`: Screen viewing (RGB, 150 DPI)
- `proof`: Quick proofing (low quality)

#### Methods

```python
manager = PDFPresetManager(config_dir=Path("config"))

# Get preset
settings = manager.get_preset("print_high_quality")

# Add custom preset
manager.add_preset("my_preset", settings, "My custom preset")

# Load from YAML
manager.load_presets_from_yaml(Path("presets.yaml"))

# Save to YAML
manager.save_presets_to_yaml(Path("output.yaml"))

# Create InDesign .pdfpreset file
manager.create_preset_file(settings, Path("preset.pdfpreset"))

# Export as JSON
manager.export_preset_as_json("print_high_quality", Path("preset.json"))
```

### PDFValidator

Validates PDF compliance and quality using multiple tools.

#### Validation Tools

1. **PyMuPDF (fitz)**: Basic PDF analysis, font checking
2. **Ghostscript (gs)**: PDF/X-4 compliance checking
3. **Poppler (pdfinfo, pdfimages)**: Detailed PDF inspection

#### Methods

```python
validator = PDFValidator(min_dpi=300)

# Validate PDF
report = validator.validate_pdfx4(Path("output.pdf"))

# Check report
print(report)  # Human-readable report
if report.is_valid:
    print("Valid PDF/X-4")
else:
    for error in report.compliance_errors:
        print(f"Error: {error}")

# Check specific aspects
has_profile, profile_name = validator.check_color_profile(Path("output.pdf"))
```

#### PDFValidationReport

```python
report = validator.validate_pdfx4(pdf_path)

# Report attributes
report.is_valid              # Overall validity
report.pdf_version           # PDF version (1.6, 1.7, etc.)
report.pdf_standard          # PDF/X-4:2010, etc.
report.page_count            # Number of pages
report.file_size             # File size in bytes
report.color_space           # CMYK, RGB, etc.
report.has_output_intent     # ICC profile present
report.output_intent_name    # ICC profile name
report.embedded_fonts        # List of embedded fonts
report.unembedded_fonts      # Fonts not embedded (error!)
report.resolution_issues     # Low-resolution images
report.compliance_errors     # Critical errors
report.warnings              # Non-critical warnings
report.validation_time       # Time taken
report.tool_availability     # Which tools were available

# Export report
report_dict = report.to_dict()
report_str = str(report)  # Human-readable
```

### PDFExporter

Orchestrates the complete export workflow.

```python
exporter = PDFExporter()

# Export with validation
report = exporter.export_to_pdfx4(
    indesign_doc=Path("input.indd"),
    output_pdf=Path("output.pdf"),
    preset=settings,
    validate=True  # Validate after export
)

# Export without validation
exporter.export_to_pdfx4(
    indesign_doc=Path("input.indd"),
    output_pdf=Path("output.pdf"),
    preset=settings,
    validate=False
)
```

---

## Export Workflow

### Complete Workflow

```python
from pathlib import Path
from kps.indesign.pdf_export import PDFExporter
from kps.indesign.pdf_presets import PDFPresetManager

# 1. Setup
manager = PDFPresetManager(config_dir=Path("config"))
exporter = PDFExporter()

# 2. Load or create preset
if "custom_preset" in manager.list_presets():
    settings = manager.get_preset("custom_preset")
else:
    # Load from YAML
    manager.load_presets_from_yaml(Path("config/pdf_export_presets.yaml"))
    settings = manager.get_preset("magazine_print")

# 3. Validate settings
errors = settings.validate()
if errors:
    raise ValueError(f"Invalid settings: {errors}")

# 4. Export
report = exporter.export_to_pdfx4(
    indesign_doc=Path("documents/pattern.indd"),
    output_pdf=Path("output/pattern_print.pdf"),
    preset=settings
)

# 5. Check results
print(report)

if report.is_valid:
    print(f"✓ Export successful: {report.page_count} pages")
    print(f"  File size: {report.file_size / 1_000_000:.1f} MB")
    print(f"  Color profile: {report.output_intent_name}")
else:
    print("✗ Validation failed:")
    for error in report.compliance_errors:
        print(f"  - {error}")

    if report.warnings:
        print("\nWarnings:")
        for warning in report.warnings:
            print(f"  - {warning}")
```

### Batch Export

```python
from pathlib import Path

exporter = PDFExporter()
settings = get_print_high_quality_preset()

documents = [
    ("pattern_01.indd", "pattern_01_print.pdf"),
    ("pattern_02.indd", "pattern_02_print.pdf"),
    ("pattern_03.indd", "pattern_03_print.pdf"),
]

results = []

for indd_file, pdf_file in documents:
    try:
        report = exporter.export_to_pdfx4(
            indesign_doc=Path(f"documents/{indd_file}"),
            output_pdf=Path(f"output/{pdf_file}"),
            preset=settings
        )
        results.append({
            'input': indd_file,
            'output': pdf_file,
            'success': report.is_valid,
            'errors': report.compliance_errors
        })
    except Exception as e:
        results.append({
            'input': indd_file,
            'success': False,
            'error': str(e)
        })

# Summary
successful = sum(1 for r in results if r['success'])
print(f"\nExported {successful}/{len(documents)} documents successfully")
```

---

## Presets

### Built-in Presets

#### print_high_quality
```python
settings = get_print_high_quality_preset()
# - PDF/X-4:2010
# - CMYK color space
# - Maximum image quality (JPEG quality 12)
# - No downsampling
# - 3mm bleed
# - All printer marks
```

#### print_medium_quality
```python
settings = get_print_medium_quality_preset()
# - PDF/X-4:2010
# - CMYK color space
# - High image quality (JPEG quality 10)
# - Downsample to 300 DPI
# - 3mm bleed
```

#### screen_optimized
```python
settings = get_screen_optimized_preset()
# - High Quality Print standard
# - RGB color space
# - Downsample to 150 DPI
# - Smaller file size
# - No bleed or marks
```

#### proof
```python
settings = get_proof_preset()
# - Quick generation
# - Medium quality
# - JPEG quality 6
# - Downsample to 150 DPI
# - No marks
```

### YAML Preset Configuration

Create custom presets in `config/pdf_export_presets.yaml`:

```yaml
presets:
  magazine_print:
    description: "High-quality magazine printing"
    author: "Your Team"
    version: "1.0"
    settings:
      pdf_standard: "PDF/X-4:2010"
      color_space: "CMYK"
      output_intent: "Coated FOGRA39 (ISO 12647-2:2004)"
      image_quality: "Maximum"
      jpeg_quality: 12
      downsample_images: false
      include_bleed: true
      bleed_top: 3.0
      bleed_bottom: 3.0
      bleed_left: 3.0
      bleed_right: 3.0
      crop_marks: true
      registration_marks: true
      color_bars: true
      transparency_flattener_preset: "High Resolution"
      optimize_pdf: true

  catalog_print:
    description: "Product catalog with lossless images"
    settings:
      pdf_standard: "PDF/X-4:2010"
      color_space: "CMYK"
      compression: "ZIP"  # Lossless
      include_bleed: true
      crop_marks: true
```

Load presets:

```python
manager = PDFPresetManager()
manager.load_presets_from_yaml(Path("config/pdf_export_presets.yaml"))

settings = manager.get_preset("magazine_print")
```

---

## Validation

### Validation Process

The validator checks multiple aspects:

1. **PDF/X-4 Compliance** (via Ghostscript)
   - OutputIntent (ICC profile) present
   - Correct PDF version
   - No transparency issues
   - All fonts embedded

2. **Image Resolution** (via pdfimages or PyMuPDF)
   - All images ≥300 DPI (configurable)
   - Color accuracy

3. **Font Embedding** (via PyMuPDF)
   - All fonts embedded
   - Proper subsetting

4. **Color Management**
   - OutputIntent present
   - Correct color space

### Validation Levels

#### Strict PDF/X-4 Validation

```python
validator = PDFValidator(min_dpi=300)
report = validator.validate_pdfx4(pdf_path)

# Must pass:
# - PDF/X-4 standard declared
# - OutputIntent present
# - All fonts embedded
# - All images ≥300 DPI
# - No transparency issues
```

#### Relaxed Validation

```python
validator = PDFValidator(min_dpi=200)  # Lower DPI threshold
report = validator.validate_pdfx4(pdf_path)

# Check only critical errors
if report.compliance_errors:
    # Critical issues
    pass
elif report.warnings:
    # Non-critical issues
    pass
```

### Installing Validation Tools

For full validation capabilities, install optional tools:

#### macOS (Homebrew)
```bash
# Ghostscript (PDF/X validation)
brew install ghostscript

# Poppler (pdfinfo, pdfimages)
brew install poppler
```

#### Ubuntu/Debian
```bash
# Ghostscript
sudo apt-get install ghostscript

# Poppler
sudo apt-get install poppler-utils
```

#### Windows
```bash
# Use Chocolatey
choco install ghostscript
choco install poppler
```

#### Python Package
```bash
# PyMuPDF (always recommended)
pip install pymupdf
```

The system gracefully degrades if tools are unavailable, using PyMuPDF as fallback.

---

## Configuration

### Environment Setup

```python
# config/settings.py

from pathlib import Path

# Paths
INDESIGN_DOCS_DIR = Path("/path/to/indesign/documents")
PDF_OUTPUT_DIR = Path("/path/to/pdf/output")
PRESET_CONFIG_DIR = Path("config")

# Export defaults
DEFAULT_PRESET = "print_high_quality"
DEFAULT_MIN_DPI = 300
DEFAULT_VALIDATION = True

# InDesign server
INDESIGN_SERVER_HOST = "localhost"
INDESIGN_SERVER_PORT = 8080
```

### Project Integration

```python
# your_project/pdf_export.py

from pathlib import Path
from kps.indesign.pdf_export import PDFExporter
from kps.indesign.pdf_presets import PDFPresetManager
from config.settings import PRESET_CONFIG_DIR, PDF_OUTPUT_DIR

class ProjectPDFExporter:
    """Project-specific PDF exporter"""

    def __init__(self):
        self.preset_manager = PDFPresetManager(config_dir=PRESET_CONFIG_DIR)
        self.exporter = PDFExporter()

        # Load project presets
        self.preset_manager.load_presets_from_yaml(
            PRESET_CONFIG_DIR / "pdf_export_presets.yaml"
        )

    def export_pattern(self, pattern_name: str, preset_name: str = "magazine_print"):
        """Export pattern to PDF"""
        settings = self.preset_manager.get_preset(preset_name)

        return self.exporter.export_to_pdfx4(
            indesign_doc=Path(f"patterns/{pattern_name}.indd"),
            output_pdf=PDF_OUTPUT_DIR / f"{pattern_name}_print.pdf",
            preset=settings
        )
```

---

## API Reference

### Core Classes

#### PDFExportSettings

```python
PDFExportSettings(
    pdf_standard: PDFStandard = PDF_X_4_2010,
    color_space: ColorSpace = CMYK,
    output_intent: str = "Coated FOGRA39",
    # ... many more parameters
)

# Methods
.to_jsx_script() -> str
.to_dict() -> Dict
.to_json() -> str
.validate() -> List[str]

# Class methods
.from_dict(data: Dict) -> PDFExportSettings
.from_json(json_str: str) -> PDFExportSettings
```

#### PDFPresetManager

```python
PDFPresetManager(config_dir: Optional[Path] = None)

# Methods
.get_preset(name: str) -> PDFExportSettings
.list_presets() -> Dict[str, str]
.add_preset(name: str, settings: PDFExportSettings, description: str)
.remove_preset(name: str)
.load_presets_from_yaml(yaml_path: Path) -> int
.save_presets_to_yaml(yaml_path: Path, include_builtin: bool = False)
.create_preset_file(settings: PDFExportSettings, output_path: Path)
.export_preset_as_json(name: str, output_path: Path)
```

#### PDFValidator

```python
PDFValidator(min_dpi: int = 300)

# Methods
.validate_pdfx4(pdf_path: Path) -> PDFValidationReport
.check_color_profile(pdf_path: Path) -> Tuple[bool, str]

# Properties
.tool_availability: Dict[str, bool]
```

#### PDFExporter

```python
PDFExporter(jsx_runner=None, validator=None)

# Methods
.export_to_pdfx4(
    indesign_doc: Path,
    output_pdf: Path,
    preset: PDFExportSettings,
    validate: bool = True
) -> Optional[PDFValidationReport]
```

### Enums

```python
# Standards
PDFStandard.PDF_X_4_2010
PDFStandard.PDF_X_1A_2001
PDFStandard.PDF_X_3_2002
PDFStandard.PDF_A_1B_2005
PDFStandard.HIGH_QUALITY_PRINT
PDFStandard.PRESS_QUALITY

# Color spaces
ColorSpace.CMYK
ColorSpace.RGB
ColorSpace.GRAY
ColorSpace.UNCHANGED

# Compression
CompressionType.JPEG
CompressionType.ZIP
CompressionType.JPEG2000
CompressionType.AUTOMATIC
CompressionType.NONE

# Image quality
ImageQuality.MAXIMUM
ImageQuality.HIGH
ImageQuality.MEDIUM
ImageQuality.LOW
ImageQuality.MINIMUM
```

---

## Best Practices

### 1. Always Validate Settings

```python
settings = PDFExportSettings(...)
errors = settings.validate()
if errors:
    raise ValueError(f"Invalid settings: {errors}")
```

### 2. Use Appropriate Presets

- **Print production**: `print_high_quality` or custom print preset
- **Client proofs**: `email_proof` or `proof`
- **Digital/web**: `screen_optimized`
- **Archival**: Create PDF/A preset

### 3. Validate Exported PDFs

```python
report = exporter.export_to_pdfx4(..., validate=True)
if not report.is_valid:
    # Handle errors before sending to printer
    for error in report.compliance_errors:
        logger.error(f"PDF error: {error}")
```

### 4. Handle Missing Tools Gracefully

```python
validator = PDFValidator()

if not validator.tool_availability.get('ghostscript'):
    logger.warning("Ghostscript not available - validation limited")

# System will use PyMuPDF as fallback
```

### 5. Use Project-Specific Presets

Create a project preset library:

```yaml
# config/project_presets.yaml
presets:
  project_standard:
    settings:
      pdf_standard: "PDF/X-4:2010"
      color_space: "CMYK"
      output_intent: "Your printer's ICC profile"
      # ... project-specific settings
```

### 6. Batch Processing

```python
# Use same settings for consistency
settings = manager.get_preset("magazine_print")

for doc in documents:
    exporter.export_to_pdfx4(doc, output, settings)
```

### 7. Monitor Validation Results

```python
# Track validation metrics
validation_results = []

for doc in documents:
    report = exporter.export_to_pdfx4(...)
    validation_results.append({
        'doc': doc,
        'valid': report.is_valid,
        'errors': len(report.compliance_errors),
        'warnings': len(report.warnings)
    })

# Generate summary report
failed = [r for r in validation_results if not r['valid']]
if failed:
    print(f"⚠ {len(failed)} documents failed validation")
```

---

## Troubleshooting

### Common Issues

#### 1. PDF/X-4 Validation Fails

**Error**: "Missing OutputIntent (ICC profile)"

**Solution**:
```python
settings = PDFExportSettings(
    pdf_standard=PDFStandard.PDF_X_4_2010,
    output_intent="Coated FOGRA39 (ISO 12647-2:2004)"  # Required!
)
```

#### 2. RGB Images in CMYK PDF

**Error**: "PDF/X-4 requires CMYK or Grayscale"

**Solution**:
```python
settings = PDFExportSettings(
    color_space=ColorSpace.CMYK,  # Not RGB
    output_intent="Coated FOGRA39 (ISO 12647-2:2004)"
)
```

#### 3. Fonts Not Embedded

**Error**: "Fonts not embedded (required for PDF/X-4)"

**Solution**:
```python
settings = PDFExportSettings(
    embed_fonts=True,
    subset_fonts_threshold=100  # Always subset/embed
)
```

#### 4. Low Resolution Images

**Warning**: "Images below 300 DPI"

**Solution**:
```python
# Either fix source images or adjust threshold
settings = PDFExportSettings(
    downsample_images=False,  # Don't reduce quality
    resolution_threshold=450   # Don't downsample high-res images
)

# Or accept lower DPI for specific use cases
validator = PDFValidator(min_dpi=200)
```

#### 5. Validation Tools Not Found

**Warning**: "Ghostscript not available"

**Solution**:
```bash
# Install Ghostscript
brew install ghostscript  # macOS
sudo apt-get install ghostscript  # Linux

# Or install PyMuPDF as fallback
pip install pymupdf
```

#### 6. InDesign Document Won't Open

**Error**: "Failed to open document"

**Solution**:
- Verify file path is correct
- Check InDesign version compatibility
- Ensure InDesign Server is running
- Check file permissions

#### 7. Export Takes Too Long

**Issue**: Slow PDF generation

**Solution**:
```python
# Use faster settings for proofs
settings = get_proof_preset()  # Lower quality, faster

# Or disable validation for speed
exporter.export_to_pdfx4(..., validate=False)
```

### Debugging

#### Enable Logging

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('kps.indesign.pdf_export')
logger.setLevel(logging.DEBUG)
```

#### Check Tool Availability

```python
validator = PDFValidator()
print("Available tools:")
for tool, available in validator.tool_availability.items():
    status = "✓" if available else "✗"
    print(f"  {status} {tool}")
```

#### Inspect Generated JSX

```python
settings = get_print_high_quality_preset()
jsx_script = settings.to_jsx_script()

# Save for inspection
Path("debug_export.jsx").write_text(jsx_script)
print(f"JSX script saved: {len(jsx_script)} characters")
```

#### Validate Settings Before Export

```python
errors = settings.validate()
if errors:
    print("Settings errors:")
    for error in errors:
        print(f"  - {error}")
else:
    print("✓ Settings valid")
```

---

## Examples

### Example 1: Simple Export

```python
from pathlib import Path
from kps.indesign.pdf_export import PDFExporter, get_print_high_quality_preset

exporter = PDFExporter()
settings = get_print_high_quality_preset()

report = exporter.export_to_pdfx4(
    indesign_doc=Path("pattern.indd"),
    output_pdf=Path("pattern_print.pdf"),
    preset=settings
)

print(f"Export {'succeeded' if report.is_valid else 'failed'}")
```

### Example 2: Custom Settings with Validation

```python
from kps.indesign.pdf_export import (
    PDFExportSettings,
    PDFStandard,
    ColorSpace,
    PDFExporter
)

# Custom settings
settings = PDFExportSettings(
    pdf_standard=PDFStandard.PDF_X_4_2010,
    color_space=ColorSpace.CMYK,
    output_intent="Coated FOGRA39 (ISO 12647-2:2004)",
    jpeg_quality=11,
    include_bleed=True,
    bleed_top=5.0,  # 5mm bleed
    bleed_bottom=5.0,
    bleed_left=5.0,
    bleed_right=5.0
)

# Validate before export
errors = settings.validate()
if errors:
    print("Configuration errors:", errors)
    exit(1)

# Export
exporter = PDFExporter()
report = exporter.export_to_pdfx4(
    indesign_doc=Path("documents/pattern.indd"),
    output_pdf=Path("output/pattern_print.pdf"),
    preset=settings
)

# Detailed report
print(report)
```

### Example 3: YAML Preset Configuration

```python
from pathlib import Path
from kps.indesign.pdf_presets import PDFPresetManager
from kps.indesign.pdf_export import PDFExporter

# Setup
manager = PDFPresetManager()
exporter = PDFExporter()

# Load presets from YAML
manager.load_presets_from_yaml(Path("config/pdf_export_presets.yaml"))

# List available presets
print("Available presets:")
for name, desc in manager.list_presets().items():
    print(f"  - {name}: {desc}")

# Use specific preset
settings = manager.get_preset("magazine_print")

# Export
report = exporter.export_to_pdfx4(
    indesign_doc=Path("magazine_layout.indd"),
    output_pdf=Path("magazine_final.pdf"),
    preset=settings
)
```

### Example 4: Batch Export with Error Handling

```python
from pathlib import Path
from kps.indesign.pdf_export import PDFExporter, get_print_high_quality_preset

exporter = PDFExporter()
settings = get_print_high_quality_preset()

input_dir = Path("indesign_docs")
output_dir = Path("pdf_output")
output_dir.mkdir(exist_ok=True)

# Find all InDesign documents
indd_files = list(input_dir.glob("*.indd"))

results = {
    'successful': [],
    'failed': [],
    'validation_errors': []
}

for indd_file in indd_files:
    output_pdf = output_dir / f"{indd_file.stem}_print.pdf"

    try:
        report = exporter.export_to_pdfx4(
            indesign_doc=indd_file,
            output_pdf=output_pdf,
            preset=settings
        )

        if report.is_valid:
            results['successful'].append(indd_file.name)
        else:
            results['validation_errors'].append({
                'file': indd_file.name,
                'errors': report.compliance_errors
            })

    except Exception as e:
        results['failed'].append({
            'file': indd_file.name,
            'error': str(e)
        })

# Summary
print(f"\nExport Summary:")
print(f"  ✓ Successful: {len(results['successful'])}")
print(f"  ⚠ Validation errors: {len(results['validation_errors'])}")
print(f"  ✗ Failed: {len(results['failed'])}")

if results['validation_errors']:
    print("\nValidation Errors:")
    for item in results['validation_errors']:
        print(f"  {item['file']}:")
        for error in item['errors']:
            print(f"    - {error}")
```

### Example 5: PDF Validation Only

```python
from pathlib import Path
from kps.indesign.pdf_validator import PDFValidator

validator = PDFValidator(min_dpi=300)

# Validate existing PDF
report = validator.validate_pdfx4(Path("existing_document.pdf"))

print(report)

# Check specific requirements
if not report.has_output_intent:
    print("⚠ Missing ICC color profile")

if report.unembedded_fonts:
    print(f"⚠ {len(report.unembedded_fonts)} fonts not embedded:")
    for font in report.unembedded_fonts:
        print(f"  - {font}")

if report.resolution_issues:
    print(f"⚠ {len(report.resolution_issues)} low-resolution images")
```

### Example 6: Creating Custom Preset Library

```python
from pathlib import Path
from kps.indesign.pdf_presets import PDFPresetManager
from kps.indesign.pdf_export import PDFExportSettings, PDFStandard, ColorSpace

manager = PDFPresetManager()

# Create custom presets
presets = {
    'client_proof': PDFExportSettings(
        pdf_standard=PDFStandard.HIGH_QUALITY_PRINT,
        color_space=ColorSpace.RGB,
        jpeg_quality=8,
        downsample_images=True,
        downsample_color_to=150,
        include_bleed=False
    ),
    'final_print': PDFExportSettings(
        pdf_standard=PDFStandard.PDF_X_4_2010,
        color_space=ColorSpace.CMYK,
        output_intent="Coated FOGRA39 (ISO 12647-2:2004)",
        jpeg_quality=12,
        downsample_images=False,
        include_bleed=True,
        bleed_top=3.0,
        bleed_bottom=3.0,
        bleed_left=3.0,
        bleed_right=3.0,
        crop_marks=True,
        registration_marks=True
    )
}

# Add to manager
for name, settings in presets.items():
    manager.add_preset(name, settings, f"Custom {name} preset")

# Save to YAML
manager.save_presets_to_yaml(
    Path("config/custom_presets.yaml"),
    include_builtin=True
)

print(f"Created {len(presets)} custom presets")
```

---

## Conclusion

The PDF/X-4 Export System provides comprehensive, production-ready PDF export capabilities for InDesign automation. With flexible preset management, robust validation, and complete control over export settings, it ensures high-quality, compliant PDF output for print production workflows.

For questions or issues, refer to the troubleshooting section or examine the test suite in `tests/test_pdf_export.py` for additional examples.

---

**Version:** 1.0
**Last Updated:** 2025-11-06
**Component:** KPS v2.0 Agent 4
**License:** Project Internal Use
