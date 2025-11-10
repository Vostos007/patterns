# IDML Export Workflow Guide

Complete guide for exporting IDML with anchored objects from KPS asset ledger.

## Overview

The IDML export system takes a source IDML template and embeds KPS assets as anchored objects based on the asset ledger and document structure.

**Workflow:**
```
Source IDML → Parse → Modify (add anchored objects) → Validate → Package → Output IDML
```

## Prerequisites

### Required Data

1. **Source IDML Template**: InDesign document exported as IDML
2. **Asset Ledger** (`assets.json`): Complete asset inventory with anchoring
3. **KPS Document** (`document.json`): Parsed text structure with blocks
4. **Column Detection**: Page columns for anchor positioning

### Python Dependencies

```python
from pathlib import Path
from kps.core.assets import AssetLedger
from kps.core.document import KPSDocument
from kps.anchoring.columns import detect_columns
from kps.indesign import IDMLExporter, IDMLValidator
```

## Quick Start

### Basic Export

```python
from pathlib import Path
from kps.indesign import quick_export

success = quick_export(
    source_idml=Path("template.idml"),
    output_idml=Path("output.idml"),
    assets_json=Path("assets.json"),
    document_json=Path("document.json"),
)

if success:
    print("Export complete!")
else:
    print("Export failed - check logs")
```

### Full Export with Column Control

```python
from pathlib import Path
from kps.core.assets import AssetLedger
from kps.core.document import KPSDocument
from kps.anchoring.columns import detect_columns
from kps.indesign import IDMLExporter

# Load data
ledger = AssetLedger.load_json(Path("assets.json"))
document = KPSDocument.load_json(Path("document.json"))

# Detect columns for each page
columns_by_page = {}
for page in range(ledger.total_pages):
    blocks = document.get_blocks_on_page(page)
    if blocks:
        columns_by_page[page] = detect_columns(blocks)

# Export with anchored objects
exporter = IDMLExporter()
success = exporter.export_with_anchored_objects(
    source_idml=Path("template.idml"),
    output_idml=Path("output.idml"),
    manifest=ledger,
    document=document,
    columns=columns_by_page,
    cleanup=True,  # Cleanup temp directories
)
```

## Step-by-Step Workflow

### Step 1: Parse Source IDML

```python
from kps.indesign import IDMLParser

parser = IDMLParser()
doc = parser.parse_idml(Path("template.idml"))

print(f"Stories: {len(doc.stories)}")
print(f"Spreads: {len(doc.spreads)}")

# Explore structure
for story in doc.stories.values():
    print(f"Story {story.story_id}: {story.get_all_text()[:50]}...")
```

**What Happens:**
1. IDML extracted to temp directory
2. `designmap.xml` parsed (manifest)
3. All Story XML files parsed
4. All Spread XML files parsed
5. Metadata and styles loaded

### Step 2: Prepare Asset Data

```python
from kps.core.assets import AssetLedger

# Load ledger
ledger = AssetLedger.load_json(Path("assets.json"))

# Check anchoring completeness
anchored_count = sum(1 for a in ledger.assets if a.anchor_to)
print(f"Anchored assets: {anchored_count}/{len(ledger.assets)}")

# Filter assets needing anchoring
assets_to_place = [a for a in ledger.assets if a.anchor_to]
```

### Step 3: Detect Columns

```python
from kps.anchoring.columns import detect_columns

columns_by_page = {}
for page in range(ledger.total_pages):
    blocks = document.get_blocks_on_page(page)
    if blocks:
        try:
            cols = detect_columns(blocks, eps=30.0, min_samples=3)
            columns_by_page[page] = cols
            print(f"Page {page}: {len(cols)} columns")
        except ValueError as e:
            print(f"Page {page}: Column detection failed - {e}")
            columns_by_page[page] = []
```

### Step 4: Process Each Asset

```python
from kps.indesign import IDMLModifier, calculate_anchor_settings
from kps.anchoring.columns import find_asset_column

modifier = IDMLModifier()

for asset in assets_to_place:
    # Find target block
    block = document.find_block(asset.anchor_to)
    if not block:
        print(f"Warning: Block {asset.anchor_to} not found")
        continue

    # Find column
    page_columns = columns_by_page.get(asset.page_number, [])
    column = find_asset_column(asset.bbox, page_columns)
    if not column:
        print(f"Warning: Asset {asset.asset_id} not in any column")
        continue

    # Calculate anchor settings
    anchor_settings = calculate_anchor_settings(
        asset.bbox,
        column,
        inline=False  # or True for inline anchoring
    )

    # Create anchored object
    rect_id = modifier.create_anchored_object(
        doc,
        story_id="u123",  # Determine from block
        insertion_point=0,  # Calculate from block position
        graphic_path=str(asset.file_path),
        anchor_settings=anchor_settings,
        asset_id=asset.asset_id,
        dimensions=(asset.bbox.width, asset.bbox.height),
    )

    # Add metadata
    metadata = {
        "sha256": asset.sha256,
        "type": asset.asset_type.value,
        "page": asset.page_number,
    }
    modifier.add_object_label(doc, rect_id, asset.asset_id, metadata)
```

### Step 5: Save and Package

```python
from kps.indesign.idml_utils import zip_idml

# Save modifications
modifier.save_changes(doc)

# Package as IDML
zip_idml(doc.temp_dir, Path("output.idml"))

print("IDML packaged successfully!")
```

### Step 6: Validate Output

```python
from kps.indesign import IDMLValidator

validator = IDMLValidator()
result = validator.validate(Path("output.idml"))

if result.is_valid:
    print("✓ IDML is valid!")
else:
    print("✗ IDML validation failed:")
    for error in result.errors:
        print(f"  - {error}")

# Print warnings
for warning in result.warnings:
    print(f"  ⚠ {warning}")

# Print info
for info in result.info:
    print(f"  ℹ {info}")
```

### Step 7: Cleanup

```python
from kps.indesign.idml_utils import cleanup_temp_dir

# Cleanup temp directory
cleanup_temp_dir(doc.temp_dir)
```

## Advanced Usage

### Custom Anchor Settings

```python
from kps.indesign.anchoring import (
    AnchoredObjectSettings,
    AnchorPoint,
    AnchoredPosition,
    HorizontalAlignment,
    HorizontalReferencePoint,
    VerticalReferencePoint,
)

# Create custom anchor settings
custom_settings = AnchoredObjectSettings(
    anchor_point=AnchorPoint.TOP_LEFT,
    anchored_position=AnchoredPosition.ANCHORED,
    horizontal_alignment=HorizontalAlignment.CENTER_ALIGN,
    horizontal_reference_point=HorizontalReferencePoint.COLUMN_EDGE,
    vertical_reference_point=VerticalReferencePoint.LINE_BASELINE,
    anchor_x_offset=0.0,
    anchor_y_offset=-50.0,  # 50pt above baseline
    pin_position=True,  # Prevent reflow
)

# Use in create_anchored_object
rect_id = modifier.create_anchored_object(
    doc,
    story_id="u123",
    insertion_point=0,
    graphic_path="asset.png",
    anchor_settings=custom_settings,
)
```

### Labels-Only Export

For adding labels to existing objects without creating new anchored objects:

```python
exporter = IDMLExporter()

success = exporter.export_labels_only(
    source_idml=Path("template.idml"),
    output_idml=Path("labeled.idml"),
    manifest=ledger,
    cleanup=True,
)
```

### Inline vs Custom Anchoring

```python
from kps.indesign import calculate_anchor_settings, calculate_inline_anchor

# Inline anchor (flows with text)
inline_settings = calculate_inline_anchor()

# Custom anchor (positioned relative to text frame)
custom_settings = calculate_anchor_settings(
    asset.bbox,
    column,
    inline=False
)

# Choose based on asset type
if asset.asset_type == AssetType.IMAGE and asset.bbox.width < 100:
    # Small images: inline
    settings = inline_settings
else:
    # Larger images: custom positioned
    settings = custom_settings
```

## Troubleshooting

### Issue: Assets Not Appearing in Output

**Diagnostic:**
```python
# Check if assets were processed
print(f"Assets with anchor_to: {sum(1 for a in ledger.assets if a.anchor_to)}")

# Check if stories exist
for asset in ledger.assets:
    if asset.anchor_to:
        block = document.find_block(asset.anchor_to)
        if not block:
            print(f"Missing block: {asset.anchor_to}")
```

**Common Causes:**
1. `anchor_to` field is empty or invalid
2. Target block not found in document
3. Story ID mapping incorrect
4. Column detection failed

**Solutions:**
- Verify anchoring algorithm output
- Check block IDs in document.json
- Manual story ID mapping if needed

### Issue: IDML Won't Open in InDesign

**Diagnostic:**
```python
from kps.indesign import IDMLValidator

result = validator.validate(Path("output.idml"))
print(result)
```

**Common Causes:**
1. Malformed XML
2. Invalid anchored object settings
3. Missing required files
4. Incorrect mimetype compression

**Solutions:**
- Run validator to identify specific errors
- Check XML well-formedness
- Verify mimetype is first and uncompressed

### Issue: Anchored Objects Positioned Incorrectly

**Diagnostic:**
```python
# Check anchor settings
settings = calculate_anchor_settings(asset.bbox, column)
print(f"Horizontal alignment: {settings.horizontal_alignment}")
print(f"X offset: {settings.anchor_x_offset}")
print(f"Y offset: {settings.anchor_y_offset}")

# Check column boundaries
print(f"Column: {column.x_min} - {column.x_max}")
print(f"Asset: {asset.bbox.x0} - {asset.bbox.x1}")
```

**Common Causes:**
1. Column detection incorrect
2. Coordinate system mismatch (PDF vs InDesign)
3. Wrong anchor reference point

**Solutions:**
- Verify column detection with visualization
- Check coordinate conversions
- Adjust anchor offsets manually if needed

### Issue: Missing Images

**Causes:**
1. Image paths incorrect
2. Relative paths wrong from IDML location
3. Image files not accessible

**Solutions:**
```python
# Use absolute paths
import os
absolute_path = os.path.abspath(asset.file_path)

# Or ensure relative paths are correct
relative_path = asset.file_path.relative_to(idml_path.parent)
```

## Production Considerations

### Performance

**Large Documents:**
- Process assets in batches
- Use multiprocessing for independent pages
- Stream large XML files

```python
# Batch processing example
batch_size = 50
for i in range(0, len(assets_to_place), batch_size):
    batch = assets_to_place[i:i+batch_size]
    # Process batch
```

### Error Recovery

```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    success = exporter.export_with_anchored_objects(...)
except Exception as e:
    logger.error(f"Export failed: {e}", exc_info=True)
    # Cleanup temp files
    # Notify user
    # Retry or fail gracefully
```

### Version Compatibility

Target IDML 7.5 (CS6) for maximum compatibility:

```python
# Check IDML version
from kps.indesign.idml_parser import get_idml_version

version = get_idml_version(doc)
if version != "7.5":
    print(f"Warning: IDML version {version} may have compatibility issues")
```

### Quality Assurance

```python
# Post-export validation checklist
def validate_export(output_path: Path) -> bool:
    """Complete validation of exported IDML."""
    checks = []

    # 1. File exists and is valid ZIP
    checks.append(output_path.exists())

    # 2. IDML structure valid
    validator = IDMLValidator()
    result = validator.validate(output_path)
    checks.append(result.is_valid)

    # 3. Expected object count
    parser = IDMLParser()
    doc = parser.parse_idml(output_path)
    inline_objects = doc.get_all_inline_objects()
    checks.append(len(inline_objects) > 0)

    # 4. All labels present
    # (custom check based on requirements)

    return all(checks)
```

## Best Practices

1. **Always validate** output IDML before delivery
2. **Cleanup temp directories** to avoid disk space issues
3. **Log processing details** for debugging
4. **Use absolute paths** for image links when possible
5. **Test with small documents** before batch processing
6. **Keep backups** of source IDML templates
7. **Document custom settings** for reproducibility

## API Reference

See module docstrings for complete API:

```python
# Core modules
from kps.indesign import (
    IDMLParser,      # Parse IDML structure
    IDMLModifier,    # Modify IDML
    IDMLExporter,    # High-level export
    IDMLValidator,   # Validate IDML
)

# Anchoring
from kps.indesign.anchoring import (
    calculate_anchor_settings,  # Calculate from bbox/column
    calculate_inline_anchor,    # Simple inline anchor
    AnchoredObjectSettings,     # Manual settings
)

# Utilities
from kps.indesign.idml_utils import (
    unzip_idml,      # Extract IDML
    zip_idml,        # Package IDML
    validate_idml_structure,  # Check structure
)
```

## Examples

See `tests/test_idml_export.py` for comprehensive examples and usage patterns.

## Support

For issues or questions:
1. Check validation output for specific errors
2. Review IDML_STRUCTURE.md for format details
3. Examine test cases for working examples
4. Enable debug logging for detailed traces

## Version History

- **v2.0.0** (2025-01-06): Initial IDML export implementation
  - Anchored object support
  - Column-aware positioning
  - Validation system
  - Comprehensive documentation
