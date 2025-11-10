# KPS InDesign Automation

Complete JSX script library and Python interface for automating Adobe InDesign workflows in the KPS v2.0 PDF localization pipeline.

## Overview

This module bridges the gap between PDF extraction (Days 1-3) and InDesign layout automation (Day 4+). It provides:

1. **JSX Scripts**: ExtendScript automation for InDesign
2. **Python Interface**: Execute JSX scripts from Python
3. **Coordinate Conversion**: Transform between PDF, InDesign, and normalized coordinate systems
4. **Asset Placement**: Automated placement of images, vectors, and table snapshots

## Directory Structure

```
kps/indesign/
├── __init__.py                           # Python package exports
├── jsx_runner.py                         # Python JSX execution interface (213 lines)
├── placement.py                          # Coordinate conversion utilities (328 lines)
├── jsx/                                  # JSX scripts for InDesign
│   ├── utils.jsx                         # Common utilities (450 lines)
│   ├── label_placed_objects.jsx          # Label existing objects (285 lines)
│   ├── extract_object_labels.jsx         # Extract labels to JSON (317 lines)
│   └── place_assets_from_manifest.jsx    # Automated asset placement (520 lines)
├── README.md                             # This file
└── IMPLEMENTATION_SUMMARY.md             # Implementation details and results
```

## Quick Start

### Python Usage

```python
from pathlib import Path
from kps.indesign import JSXRunner, calculate_placement_position
from kps.core.bbox import NormalizedBBox
from kps.anchoring.columns import Column

# Initialize runner
runner = JSXRunner()

# Label existing objects in InDesign document
result = runner.label_placed_objects(
    document_path=Path("document.indd"),
    manifest_path=Path("output/manifest.json")
)

# Extract labels back from document
labels = runner.extract_labels(
    document_path=Path("document.indd"),
    output_path=Path("output/extracted_labels.json")
)

# Place assets automatically
result = runner.place_assets(
    document_path=Path("document.indd"),
    manifest_path=Path("output/manifest.json"),
    assets_dir=Path("output/assets")
)

# Calculate placement coordinates
normalized = NormalizedBBox(x=0.1, y=0.2, w=0.3, h=0.4)
column = Column(
    column_id=0,
    x_min=50.0,
    x_max=300.0,
    y_min=100.0,
    y_max=700.0,
    blocks=[]
)
bbox = calculate_placement_position(normalized, column, page_height=792.0)
```

### InDesign JSX Usage

Run scripts directly from InDesign:

1. Open InDesign document
2. Go to: **File > Scripts > Other Script...**
3. Select JSX script from `kps/indesign/jsx/`
4. Follow prompts

Or use scripts panel:
1. Copy JSX scripts to InDesign Scripts folder
2. Open **Window > Utilities > Scripts**
3. Double-click script to run

## JSX Scripts API

### utils.jsx

Common utility library providing:

**JSON Operations:**
- `parseJSON(jsonString)` - Parse JSON with error handling
- `stringifyJSON(obj, indent)` - Convert object to JSON string

**File I/O:**
- `readFile(filePath)` - Read text file
- `writeFile(filePath, content)` - Write text file
- `loadManifest(manifestPath)` - Load and parse manifest.json

**BBox Utilities:**
- `createBBox(x0, y0, x1, y1)` - Create BBox object
- `geometricBoundsToBBox(bounds)` - Convert InDesign bounds to BBox
- `bboxToGeometricBounds(bbox)` - Convert BBox to InDesign bounds
- `calculateOverlap(bbox1, bbox2)` - Calculate overlap ratio
- `calculateDistance(bbox1, bbox2)` - Distance between centers

**Coordinate Conversion:**
- `normalizedToAbsolute(normalized, column)` - Convert 0-1 coords to absolute
- `absoluteToNormalized(bbox, column)` - Convert absolute to 0-1 coords

**InDesign Helpers:**
- `getAllPageItems(doc)` - Get all graphics/images in document
- `findItemByLabel(doc, label)` - Find item by label
- `getPageNumber(item)` - Get 0-indexed page number

**Logging:**
- `logInfo(message)` - Log info message
- `logWarning(message)` - Log warning message
- `logError(message)` - Log error message
- `logSuccess(message)` - Log success message

### label_placed_objects.jsx

Labels existing placed objects with asset IDs from manifest.

**Function:** `labelPlacedObjects(manifestPath)`

**Input:**
- `manifestPath`: Path to manifest.json with AssetLedger

**Process:**
1. Load manifest.json
2. Iterate through all placed objects in active document
3. Match each object to asset by position, size, and page
4. Set `item.label = asset_id`
5. Set `item.extractLabel = JSON metadata`

**Matching Algorithm:**
- Filters assets by page number
- Calculates confidence score (0-1) based on:
  - Position similarity (30% weight)
  - Size similarity (30% weight)
  - Overlap ratio (40% weight)
- Matches if confidence ≥ 0.8

**Output:**
```javascript
{
    success: true,
    total_items: 50,
    labeled: 45,
    skipped: 5,
    errors: 0,
    labeled_items: [
        {
            asset_id: "img-abc123-p0-occ1",
            page: 0,
            bbox: {...}
        }
    ]
}
```

**Configuration:**
```javascript
var CONFIG = {
    POSITION_TOLERANCE: 5.0,  // Points tolerance
    SIZE_TOLERANCE: 2.0,
    MIN_CONFIDENCE: 0.8
};
```

### extract_object_labels.jsx

Extracts labels and metadata from labeled objects.

**Function:** `extractObjectLabels(outputPath)`

**Input:**
- `outputPath`: Path to save extracted JSON (optional)

**Process:**
1. Iterate through all page items
2. Extract `item.label` (asset_id)
3. Parse `item.extractLabel` (JSON metadata)
4. Detect position changes
5. Export to JSON

**Output Format:**
```json
{
    "document": "document.indd",
    "document_path": "/path/to/document.indd",
    "extracted_at": "2025-11-06T12:00:00",
    "total_items": 50,
    "labeled_items": 45,
    "unlabeled_items": 5,
    "objects": [
        {
            "label": "img-abc123-p0-occ1",
            "page": 0,
            "item_type": "image",
            "current_bbox": {
                "x0": 100.0,
                "y0": 200.0,
                "x1": 300.0,
                "y1": 400.0,
                "width": 200.0,
                "height": 200.0
            },
            "visible": true,
            "locked": false,
            "metadata": {
                "asset_id": "img-abc123-p0-occ1",
                "asset_type": "image",
                "sha256": "abc123...",
                "original_bbox": {...},
                "placed_bbox": {...},
                "ctm": [1, 0, 0, 1, 0, 0],
                "anchor_to": "p.materials.001"
            },
            "position_changed": false,
            "position_delta": 0.5
        }
    ]
}
```

**Analysis Functions:**
- `analyzeLabels(objects)` - Check for duplicates, missing metadata, position changes

### place_assets_from_manifest.jsx

Automates asset placement from manifest.

**Function:** `placeAssetsFromManifest(manifestPath, assetsDir, columnLayout)`

**Input:**
- `manifestPath`: Path to manifest.json
- `assetsDir`: Directory containing asset files
- `columnLayout`: Optional column layout info for normalized coordinates

**Process:**
1. Load manifest.json with AssetLedger
2. For each asset:
   - Locate asset file
   - Calculate placement bounds (PDF → InDesign coordinates)
   - Create rectangle frame
   - Place asset file
   - Apply transformation matrix (CTM)
   - Set label and metadata

**Coordinate Conversion:**
```javascript
// PDF coordinates (origin bottom-left, y-up)
// → InDesign coordinates (origin top-left, y-down)
function calculatePlacementBounds(asset, page, columnLayout) {
    var assetBBox = createBBox(
        asset.bbox.x0,
        asset.bbox.y0,
        asset.bbox.x1,
        asset.bbox.y1
    );

    // Flip y-coordinates
    var pageHeight = page.bounds[2] - page.bounds[0];
    var indesignBBox = createBBox(
        assetBBox.x0,
        pageHeight - assetBBox.y1,  // Flip y
        assetBBox.x1,
        pageHeight - assetBBox.y0
    );

    return indesignBBox;
}
```

**Transformation Matrix (CTM):**
- `ctm = [a, b, c, d, e, f]`
  - `a`: Horizontal scaling
  - `b`: Vertical skewing
  - `c`: Horizontal skewing
  - `d`: Vertical scaling
  - `e`: Horizontal translation
  - `f`: Vertical translation

**Configuration:**
```javascript
var CONFIG = {
    DPI: 72,
    DEFAULT_FRAME_FITTING: FitOptions.PROPORTIONALLY,
    PRESERVE_ASPECT_RATIO: true,
    AUTO_LABEL: true,
    APPLY_CTM: true
};
```

**Batch Operations:**
- `placeAssetsByPageRange(manifestPath, assetsDir, startPage, endPage, columnLayout)`

## Python API

### JSXRunner Class

Execute JSX scripts from Python.

```python
from kps.indesign import JSXRunner

runner = JSXRunner(jsx_dir=Path("kps/indesign/jsx"))

# Execute any JSX script
result = runner.execute_script(
    script_name="label_placed_objects",
    arguments={"manifestPath": "/path/to/manifest.json"}
)

# Convenience methods
result = runner.label_placed_objects(doc_path, manifest_path)
result = runner.extract_labels(doc_path, output_path)
result = runner.place_assets(doc_path, manifest_path, assets_dir)
result = runner.place_assets_by_page_range(
    doc_path, manifest_path, assets_dir,
    start_page=0, end_page=5
)
```

**JSXResult:**
```python
@dataclass
class JSXResult:
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
```

**Platform Support:**
- **macOS**: Uses `osascript` to communicate with InDesign via AppleScript
- **Windows**: Uses COM (requires `pywin32` package)

### Coordinate Conversion

```python
from kps.indesign import CoordinateConverter, calculate_placement_position
from kps.core.bbox import BBox, NormalizedBBox

# Initialize converter
converter = CoordinateConverter(page_width=612.0, page_height=792.0)

# PDF → InDesign
pdf_bbox = BBox(x0=100, y0=200, x1=300, y1=400)
indesign_bounds = converter.pdf_to_indesign(pdf_bbox)
# Returns: [top, left, bottom, right] = [392, 100, 592, 300]

# InDesign → PDF
pdf_bbox = converter.indesign_to_pdf([392, 100, 592, 300])

# Normalized → PDF
normalized = NormalizedBBox(x=0.1, y=0.2, w=0.3, h=0.4)
pdf_bbox = converter.normalized_to_pdf(normalized, column)

# PDF → Normalized
normalized = converter.pdf_to_normalized(pdf_bbox, column)
```

### Placement Utilities

```python
from kps.indesign import (
    calculate_placement_position,
    calculate_placement_spec,
    find_asset_column,
    validate_placement_bounds,
    calculate_dpi,
    suggest_scaling
)

# Calculate placement position
bbox = calculate_placement_position(normalized_bbox, column, page_height)

# Calculate complete placement spec
spec = calculate_placement_spec(
    asset_id="img-abc123-p0-occ1",
    page_number=0,
    normalized_bbox=normalized_bbox,
    column=column,
    page_height=792.0,
    file_path="assets/img-abc123.png",
    ctm=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
)

# Find asset's column
column = find_asset_column(asset_bbox, columns, threshold=0.5)

# Validate placement bounds
is_valid, error_msg = validate_placement_bounds(
    bounds=[100, 50, 300, 250],
    page_width=612.0,
    page_height=792.0
)

# Calculate DPI
dpi_x, dpi_y = calculate_dpi(
    bbox=BBox(100, 200, 300, 400),
    image_width=1200,
    image_height=1200
)

# Suggest scaling for target DPI
scale_x, scale_y = suggest_scaling(
    bbox=bbox,
    image_width=1200,
    image_height=1200,
    target_dpi=300.0
)
```

## Coordinate Systems

### PDF Coordinates
- **Origin**: Bottom-left corner
- **X-axis**: Right (increases →)
- **Y-axis**: Up (increases ↑)
- **Units**: Points (72 DPI)
- **Format**: `BBox(x0, y0, x1, y1)`

### InDesign Coordinates
- **Origin**: Top-left corner
- **X-axis**: Right (increases →)
- **Y-axis**: Down (increases ↓)
- **Units**: Points (72 DPI)
- **Format**: `[top, left, bottom, right]` = `[y1, x0, y0, x1]`

### Normalized Coordinates
- **Origin**: Column top-left
- **Range**: 0-1 (relative to column dimensions)
- **Purpose**: Layout-independent positioning
- **Format**: `NormalizedBBox(x, y, w, h)`

### Conversion Example

```python
# PDF bbox at (100, 200) to (300, 400) on 792pt tall page
pdf_bbox = BBox(x0=100, y0=200, x1=300, y1=400)

# Convert to InDesign (flip y-axis)
# y_indesign = page_height - y_pdf
indesign_bounds = [
    792 - 400,  # top = 392
    100,        # left = 100
    792 - 200,  # bottom = 592
    300         # right = 300
]

# Convert to normalized (relative to column)
column = Column(x_min=50, x_max=350, y_min=100, y_max=700, ...)
normalized = NormalizedBBox(
    x=(100 - 50) / (350 - 50) = 0.167,
    y=(200 - 100) / (700 - 100) = 0.167,
    w=(200) / (300) = 0.667,
    h=(200) / (600) = 0.333
)
```

## Workflow Integration

### Day 1-3: PDF Extraction
```python
# 1. Extract text and structure
from kps.extraction import extract_document
doc = extract_document(pdf_path)

# 2. Extract visual assets
from kps.extraction import extract_assets
ledger = extract_assets(pdf_path, output_dir)
ledger.save_json(output_dir / "manifest.json")

# 3. Anchor assets to text blocks
from kps.anchoring import anchor_assets
anchor_assets(doc, ledger)
ledger.save_json(output_dir / "manifest.json")  # Updated with anchors
```

### Day 4: InDesign Automation

**Option A: Label Existing Document**
```python
from kps.indesign import JSXRunner

runner = JSXRunner()

# Open document in InDesign first
# Then label all placed objects
result = runner.label_placed_objects(
    document_path=Path("document.indd"),
    manifest_path=Path("output/manifest.json")
)

print(f"Labeled {result.data['labeled']} objects")
```

**Option B: Automated Placement**
```python
# Create new InDesign document
# Then place all assets automatically
result = runner.place_assets(
    document_path=Path("new_document.indd"),
    manifest_path=Path("output/manifest.json"),
    assets_dir=Path("output/assets")
)

print(f"Placed {result.data['placed']} assets")
```

**Verification:**
```python
# Extract labels to verify
labels = runner.extract_labels(
    document_path=Path("document.indd"),
    output_path=Path("output/verification.json")
)

# Check for issues
data = labels.data
print(f"Total labeled: {data['labeled_items']}")
print(f"Position changed: {len([o for o in data['objects'] if o.get('position_changed')])}")
```

## Error Handling

### JSX Scripts

All JSX scripts include comprehensive error handling:

```javascript
try {
    var result = placeSingleAsset(asset, doc, assetsDir);
    if (result.success) {
        logSuccess("Placed: " + asset.asset_id);
    } else {
        logWarning("Skipped: " + result.reason);
    }
} catch (e) {
    logError("Error: " + e.message);
    // Continue with next asset
}
```

### Python Interface

```python
from kps.indesign import JSXRunner

runner = JSXRunner()

try:
    result = runner.label_placed_objects(doc_path, manifest_path)
    if not result.success:
        print(f"Error: {result.error}")
        print(f"stderr: {result.stderr}")
except FileNotFoundError as e:
    print(f"Script not found: {e}")
except RuntimeError as e:
    print(f"Execution failed: {e}")
```

## Testing

### Manual Testing

1. **Test label_placed_objects.jsx:**
   ```bash
   # Open InDesign document with placed images
   # Run script via File > Scripts > Run Script
   # Check console output for labeled count
   ```

2. **Test extract_object_labels.jsx:**
   ```bash
   # After labeling, run extraction
   # Verify JSON output has correct structure
   # Check for position_changed flags
   ```

3. **Test place_assets_from_manifest.jsx:**
   ```bash
   # Create new InDesign document
   # Run placement script
   # Verify assets appear at correct positions
   ```

### Python Testing

```python
from pathlib import Path
from kps.indesign import JSXRunner

runner = JSXRunner()

# Test script existence
assert (runner.jsx_dir / "utils.jsx").exists()
assert (runner.jsx_dir / "label_placed_objects.jsx").exists()

# Test coordinate conversion
from kps.indesign import calculate_placement_position
from kps.core.bbox import NormalizedBBox
from kps.anchoring.columns import Column

normalized = NormalizedBBox(x=0.0, y=0.0, w=1.0, h=1.0)
column = Column(
    column_id=0, x_min=50, x_max=350, y_min=100, y_max=700, blocks=[]
)
bbox = calculate_placement_position(normalized, column, 792.0)

assert bbox.x0 == 50.0
assert bbox.y0 == 100.0
assert bbox.x1 == 350.0
assert bbox.y1 == 700.0
```

## Performance Considerations

### JSX Script Performance

- **Labeling**: ~0.1-0.2 seconds per object (50 objects ≈ 10 seconds)
- **Extraction**: ~0.05 seconds per object (100 objects ≈ 5 seconds)
- **Placement**: ~0.5-1.0 seconds per asset (file I/O overhead)

### Optimization Tips

1. **Batch Operations**: Use page range filtering for large documents
2. **Asset Preloading**: Ensure all asset files are local (not network drives)
3. **Column Layout**: Provide column layout info to avoid recalculation
4. **Minimal UI Updates**: InDesign scripts run faster with no screen updates

```javascript
// Disable screen redraw for better performance
app.scriptPreferences.enableRedraw = false;
try {
    // Your script operations
} finally {
    app.scriptPreferences.enableRedraw = true;
}
```

## Troubleshooting

### Common Issues

**1. Script execution timeout**
- **Cause**: Too many assets or slow file I/O
- **Solution**: Use page range filtering or increase timeout
```python
runner.execute_script(script_name, arguments, timeout=600)  # 10 minutes
```

**2. Assets not found**
- **Cause**: Incorrect asset directory path
- **Solution**: Use absolute paths
```python
assets_dir = Path("/absolute/path/to/assets").resolve()
```

**3. Position mismatch**
- **Cause**: Incorrect coordinate conversion
- **Solution**: Verify page height and column bounds
```python
# Check page dimensions
print(f"Page: {page_width}x{page_height}")
print(f"Column: {column.x_min}-{column.x_max}, {column.y_min}-{column.y_max}")
```

**4. InDesign not responding**
- **Cause**: InDesign not running or busy
- **Solution**: Ensure InDesign is open and idle
```python
# On macOS, check if InDesign is running
import subprocess
result = subprocess.run(
    ["osascript", "-e", 'tell application "System Events" to get name of every process'],
    capture_output=True, text=True
)
assert "InDesign" in result.stdout
```

## License

Part of KPS v2.0 PDF Localization Pipeline.

## Support

For issues or questions:
1. Check `IMPLEMENTATION_SUMMARY.md` for known limitations
2. Review console output (InDesign: Window > Utilities > ExtendScript Toolkit)
3. Validate manifest.json structure
4. Test with single asset first

## Changelog

### Version 1.0.0 (2025-11-06)
- Initial implementation
- Complete JSX script suite (4 scripts, 1572 total lines)
- Python interface with JSXRunner
- Coordinate conversion utilities
- Comprehensive documentation
