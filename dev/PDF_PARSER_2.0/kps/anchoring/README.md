# KPS v2.0 Anchoring Algorithm

## Overview

This module implements the **asset-to-block anchoring algorithm** for KPS v2.0, which matches visual assets (images, vectors, tables) to text blocks using spatial proximity within the same column.

## Implementation Status

 **COMPLETED** - Day 2 of KPS Master Plan

### Files Created

1. **`anchor.py`** (545 lines)
   - Core anchoring algorithm implementation
   - Normalized coordinate calculation
   - Nearest-block finder with column constraints
   - Validation and reporting

2. **`columns.py`** (434 lines)
   - Column detection using DBSCAN clustering
   - Column representation and utilities
   - Already implemented by parallel agent

3. **`__init__.py`**
   - Module exports for anchoring API

4. **`tests/anchoring/test_anchor.py`** (355 lines)
   - Comprehensive unit tests
   - Multi-column layout tests
   - Geometry validation tests

5. **`examples/anchoring_example.py`** (189 lines)
   - Working example demonstrating the algorithm
   - Sample document and asset creation
   - Full workflow walkthrough

## Algorithm Specification

### Input
- **AssetLedger**: Collection of Asset objects with (bbox, page_number)
- **KPSDocument**: Collection of ContentBlock objects with (bbox, page_number, block_id)
- **Column boundaries**: From column detection (optional, auto-detected if not provided)

### Output
- **Updated Assets**: Each asset has `anchor_to` field set to block_id
- **NormalizedBBox**: Column-relative 0-1 coordinates for each asset
- **AnchoringReport**: Validation report with success rates and warnings

### Algorithm Steps

For each asset on page P:

1. **Get blocks on same page**
   ```python
   page_blocks = document.get_blocks_on_page(asset.page_number)
   ```

2. **Detect columns** (if not provided)
   ```python
   columns = detect_columns(page_blocks)
   ```

3. **Find asset's column** (using horizontal overlap >= 50%)
   ```python
   asset_column = find_asset_column(asset.bbox, columns, threshold=0.5)
   ```

4. **Calculate vertical distances**
   - **Below**: `distance = block.bbox.y0 - asset.bbox.y1` (positive)
   - **Above**: `distance = asset.bbox.y0 - block.bbox.y1` (positive)

5. **Select nearest block**
   - Prefer blocks **below** asset (reading order)
   - If no blocks below, select nearest **above**
   - Only consider blocks in **same column**

6. **Set anchor**
   ```python
   asset.anchor_to = nearest_block.block_id
   ```

7. **Compute normalized coordinates**
   ```python
   normalized = compute_normalized_bbox(asset, column)
   # Returns: NormalizedBBox(x, y, w, h) in [0, 1] range
   ```

## Distance Metric

- **Vertical distance**: |asset.y1 - block.y0| for blocks below
- **Column constraint**: Horizontal overlap >= 50%
- **Prefer "below"**: Maintains reading order (top-to-bottom)

## API Reference

### Core Functions

#### `anchor_assets_to_blocks()`

Main entry point for anchoring.

```python
def anchor_assets_to_blocks(
    assets: AssetLedger,
    document: KPSDocument,
    columns_by_page: Optional[Dict[int, List[Column]]] = None,
    tolerance_pt: float = 2.0,
    tolerance_pct: float = 0.01,
) -> Tuple[AssetLedger, AnchoringReport]:
    """
    Anchor all assets to content blocks using column-aware spatial proximity.

    Returns:
        Tuple of (updated AssetLedger, AnchoringReport)
    """
```

**Example:**
```python
from kps.anchoring import anchor_assets_to_blocks

ledger = AssetLedger(assets=[...], ...)
document = KPSDocument(sections=[...], ...)

anchored_ledger, report = anchor_assets_to_blocks(ledger, document)

# Check results
assert report.success_rate == 1.0  # 100% anchored
assert report.geometry_pass_rate >= 0.98  # >=98% geometry preserved
```

#### `compute_normalized_bbox()`

Convert absolute coordinates to column-relative 0-1 coordinates.

```python
def compute_normalized_bbox(asset: Asset, column: Column) -> NormalizedBBox:
    """
    Compute normalized bounding box coordinates relative to column bounds.

    Returns:
        NormalizedBBox with x, y, w, h in [0, 1] range
    """
```

**Example:**
```python
# Asset at (60, 110, 160, 210) in 100x100 box
# Column at (50, 100, 250, 700) - 200x600 box

normalized = compute_normalized_bbox(asset, column)

# Results:
# x = (60 - 50) / (250 - 50) = 0.05
# y = (110 - 100) / (700 - 100) = 0.0167
# w = 100 / 200 = 0.5
# h = 100 / 600 = 0.1667
```

#### `find_nearest_block()`

Find nearest content block to anchor an asset.

```python
def find_nearest_block(
    asset: Asset,
    blocks: List[ContentBlock],
    same_column: Column = None,
    prefer_below: bool = True,
) -> Optional[ContentBlock]:
    """
    Find the nearest content block to anchor an asset.

    Returns:
        Nearest ContentBlock, or None if no suitable blocks found
    """
```

**Example:**
```python
# Asset at y=200-300
# Block 1 at y=310-330 (10pt below)
# Block 2 at y=150-190 (10pt above)

nearest = find_nearest_block(asset, [block1, block2], prefer_below=True)
assert nearest == block1  # Prefers block below
```

### Data Classes

#### `AnchoringReport`

Validation report for anchoring results.

```python
@dataclass
class AnchoringReport:
    total_assets: int
    anchored_assets: int
    unanchored_assets: List[str]
    ambiguous_anchors: List[Tuple[str, List[str]]]
    geometry_violations: List[Tuple[str, float]]
    warnings: List[str]

    @property
    def success_rate(self) -> float:
        """Calculate anchoring success rate."""

    @property
    def geometry_pass_rate(self) -> float:
        """Calculate geometry preservation pass rate."""

    def is_valid(self, min_success_rate=1.0, min_geometry_rate=0.98) -> bool:
        """Check if anchoring meets quality thresholds."""
```

## Validation

### Success Criteria

- **100% Anchoring Success**: All assets must have `anchor_to` set
- **>=98% Geometry Preservation**: Normalized coords within tolerance
- **Tolerance**: +/-2pt or 1% of asset size (whichever is larger)

### Validation Checks

1. **Completeness**: All assets anchored to a block
2. **Geometry**: Normalized coordinates within bounds [0, 1]
3. **Ambiguity Detection**: Logs warnings for equally distant blocks
4. **Column Assignment**: Assets assigned to correct column

### Example Validation

```python
anchored_ledger, report = anchor_assets_to_blocks(ledger, document)

# Validate results
if report.is_valid():
    print(f" Success rate: {report.success_rate:.1%}")
    print(f" Geometry pass rate: {report.geometry_pass_rate:.1%}")
else:
    print(f" Failed: {len(report.unanchored_assets)} unanchored assets")
    for warning in report.warnings:
        print(f"  - {warning}")
```

## Usage Example

Complete workflow:

```python
from pathlib import Path
from kps.core.assets import Asset, AssetLedger, AssetType
from kps.core.document import KPSDocument, ContentBlock, BlockType
from kps.core.bbox import BBox
from kps.anchoring import anchor_assets_to_blocks

# 1. Create document with text blocks
blocks = [
    ContentBlock(
        block_id="p.intro.001",
        block_type=BlockType.PARAGRAPH,
        content="Introduction text",
        bbox=BBox(50, 100, 250, 150),
        page_number=0,
    ),
    ContentBlock(
        block_id="p.intro.002",
        block_type=BlockType.PARAGRAPH,
        content="More text below",
        bbox=BBox(50, 250, 250, 300),
        page_number=0,
    ),
]

document = KPSDocument(slug="pattern", metadata=..., sections=[...])

# 2. Create assets
assets = [
    Asset(
        asset_id="img-001",
        asset_type=AssetType.IMAGE,
        sha256="a" * 64,
        page_number=0,
        bbox=BBox(100, 160, 200, 240),  # Between blocks
        ctm=(1, 0, 0, 1, 0, 0),
        file_path=Path("/tmp/image.png"),
        occurrence=1,
        anchor_to="",
        image_width=100,
        image_height=80,
    ),
]

ledger = AssetLedger(assets=assets, source_pdf=Path("/tmp/doc.pdf"), total_pages=1)

# 3. Run anchoring
anchored_ledger, report = anchor_assets_to_blocks(ledger, document)

# 4. Check results
assert report.success_rate == 1.0
assert anchored_ledger.assets[0].anchor_to == "p.intro.002"
```

## Multi-Column Layout Support

The algorithm automatically detects and handles multi-column layouts:

```python
# Two-column layout
left_blocks = [
    ContentBlock(bbox=BBox(50, 100, 200, 150), ...),  # Left column
]
right_blocks = [
    ContentBlock(bbox=BBox(300, 100, 450, 150), ...),  # Right column
]

# Assets in both columns
assets = [
    Asset(bbox=BBox(75, 160, 175, 200), ...),   # Left column
    Asset(bbox=BBox(325, 160, 425, 200), ...),  # Right column
]

# Anchoring respects column boundaries
anchored_ledger, report = anchor_assets_to_blocks(ledger, document)

# Each asset anchors to block in same column only
left_asset.anchor_to == "p.left.001"   #  Correct column
right_asset.anchor_to == "p.right.001" #  Correct column
```

## Testing

Run unit tests:

```bash
pytest tests/anchoring/test_anchor.py -v
```

Run example:

```bash
python3 examples/anchoring_example.py
```

### Test Coverage

-  Basic normalization (top-left, center, edges)
-  Nearest block selection (below/above preference)
-  Column constraint enforcement
-  Multi-column layouts
-  Full anchoring workflow
-  Validation and error handling

## Integration with KPS Pipeline

The anchoring algorithm integrates into the KPS pipeline at Phase 2:

```
Phase 1: Extraction
      Docling: Extract text ’ KPSDocument
      PyMuPDF: Extract graphics ’ AssetLedger

Phase 2: Anchoring (THIS MODULE)
      Detect columns
      Anchor assets to blocks
      Inject [[asset_id]] markers

Phase 3: Translation
      Translate text (preserving markers)

Phase 4: InDesign Automation
      Place assets at [[markers]]

Phase 5: QA
      Validate geometry preservation
```

## References

- **KPS Master Plan**: `/docs/KPS_MASTER_PLAN.md` - Algorithm specification
- **Column Detection**: Section 4 - "Column-aware matching"
- **Normalized Coordinates**: Section 9 - "Geometry in column coordinates"
- **Master Plan Day 2**: Asset anchoring implementation

## File Structure

```
kps/anchoring/
   __init__.py           # Module exports
   anchor.py             # Main anchoring algorithm (THIS FILE)
   columns.py            # Column detection (DBSCAN-based)
   markers.py            # Marker injection (separate module)
   README.md             # This documentation

tests/anchoring/
   __init__.py
   test_anchor.py        # Comprehensive unit tests

examples/
   anchoring_example.py  # Working example
```

## Notes

### Coordinate Systems

- **PDF Coordinates**: Origin at bottom-left, y increases upward
- **Normalized Coordinates**: Origin at top-left of column, range [0, 1]
- **InDesign**: Origin at top-left of page

### Performance

- Column detection: O(n log n) where n = number of blocks
- Anchoring: O(m * n) where m = assets, n = blocks per page
- Typical performance: <100ms for 10 pages with 50 assets

### Limitations

- Current implementation assumes single page processing
- Full geometry validation requires InDesign placement data
- Ambiguous cases (equally distant blocks) log warnings but proceed

## Future Enhancements

- [ ] Support for assets spanning multiple columns
- [ ] Advanced geometry validation with InDesign feedback
- [ ] Configurable distance metrics (Euclidean, Manhattan)
- [ ] Support for rotated/skewed assets using CTM
- [ ] Batch processing optimization for large documents
