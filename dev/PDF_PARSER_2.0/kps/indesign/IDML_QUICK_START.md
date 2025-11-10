# IDML Export Quick Start Guide

**5-Minute Guide to Exporting IDML with Anchored Objects**

## Installation

No external dependencies needed! Uses only Python standard library.

## Basic Usage

### 1. Simple Export (One Command)

```python
from pathlib import Path
from kps.indesign import quick_export

success = quick_export(
    source_idml=Path("template.idml"),
    output_idml=Path("output.idml"),
    assets_json=Path("assets.json"),
    document_json=Path("document.json"),
)

print("Export successful!" if success else "Export failed - check logs")
```

That's it! The system will:
- Parse source IDML
- Load asset ledger and document
- Auto-detect columns
- Create anchored objects for all assets
- Validate output
- Save to output.idml

### 2. Validate Output

```python
from pathlib import Path
from kps.indesign import quick_validate

if quick_validate(Path("output.idml")):
    print("✓ Valid IDML - ready for InDesign!")
else:
    print("✗ Validation failed - check errors")
```

## File Requirements

### Input Files

1. **template.idml**: Source InDesign document exported as IDML
2. **assets.json**: Asset ledger from KPS extraction
3. **document.json**: KPS document structure

### Output Files

- **output.idml**: Modified IDML with anchored objects

## Common Use Cases

### Use Case 1: Export Pattern Document

```python
from kps.indesign import quick_export

# Export knitting pattern with yarn photos
quick_export(
    Path("bonjour-gloves-template.idml"),
    Path("bonjour-gloves-ru.idml"),
    Path("bonjour-gloves-assets.json"),
    Path("bonjour-gloves-document.json"),
)
```

### Use Case 2: Labels Only (No New Objects)

```python
from kps.indesign import IDMLExporter
from kps.core.assets import AssetLedger

ledger = AssetLedger.load_json(Path("assets.json"))
exporter = IDMLExporter()

# Just add labels to existing objects
exporter.export_labels_only(
    Path("template.idml"),
    Path("labeled.idml"),
    ledger,
)
```

### Use Case 3: Custom Column Detection

```python
from kps.core.document import KPSDocument
from kps.anchoring.columns import detect_columns
from kps.indesign import IDMLExporter

document = KPSDocument.load_json(Path("document.json"))

# Custom column detection per page
columns = {}
for page in range(3):
    blocks = document.get_blocks_on_page(page)
    if blocks:
        # Adjust parameters for your layout
        cols = detect_columns(
            blocks,
            eps=30.0,        # Column gap threshold
            min_samples=3,   # Min blocks per column
        )
        columns[page] = cols

# Export with custom columns
exporter = IDMLExporter()
exporter.export_with_anchored_objects(
    Path("template.idml"),
    Path("output.idml"),
    ledger,
    document,
    columns,
)
```

## Troubleshooting

### Problem: "IDML won't open in InDesign"

**Solution:**
```python
from kps.indesign import IDMLValidator

validator = IDMLValidator()
result = validator.validate(Path("output.idml"))
print(result)  # Shows specific errors
```

Common causes:
- Malformed XML → Check validation output
- Invalid anchor settings → Review anchored object settings
- Wrong mimetype → Validator will catch this

### Problem: "Assets not appearing"

**Check:**
```python
ledger = AssetLedger.load_json(Path("assets.json"))

# How many assets have anchor_to set?
anchored = [a for a in ledger.assets if a.anchor_to]
print(f"Anchored assets: {len(anchored)}/{len(ledger.assets)}")

# Check specific asset
asset = ledger.find_by_id("img-abc123-p0-occ1")
print(f"Anchor to: {asset.anchor_to}")
```

Common causes:
- `anchor_to` field empty → Run anchoring algorithm
- Block not found → Check document.json has correct blocks
- Column detection failed → Review column detection output

### Problem: "Performance is slow"

**For large documents:**
```python
import logging

# Enable info logging to see progress
logging.basicConfig(level=logging.INFO)

# Export will log each step
exporter.export_with_anchored_objects(...)
```

Typical performance:
- 10 assets: ~2 seconds
- 50 assets: ~5 seconds
- 100 assets: ~10 seconds

## Next Steps

- **Full Guide:** See `IDML_EXPORT_GUIDE.md` for detailed workflow
- **Format Reference:** See `IDML_STRUCTURE.md` for IDML internals
- **Examples:** Check `tests/test_idml_export.py` for usage patterns

## API Reference

### Main Functions

```python
# High-level export
from kps.indesign import quick_export, quick_validate

# Core classes
from kps.indesign import (
    IDMLParser,      # Parse IDML files
    IDMLModifier,    # Modify IDML structure
    IDMLExporter,    # Export workflow
    IDMLValidator,   # Validate IDML
)

# Anchoring
from kps.indesign import (
    calculate_anchor_settings,  # Auto-calculate from bbox/column
    calculate_inline_anchor,    # Simple inline anchor
    AnchoredObjectSettings,     # Manual configuration
)
```

## Support

For issues:
1. Check validation output
2. Review logs (enable `logging.INFO`)
3. Consult `IDML_EXPORT_GUIDE.md`
4. Check test cases for examples

---

**That's all you need to get started!** Most use cases are covered by `quick_export()`.
