# 12 Enhancements - PyMuPDF Graphics Extraction

## Quick Reference

This document summarizes the 12 metadata enhancements implemented in the PyMuPDF extractor for KPS v2.0.

---

## Enhancement 1: CTM (Coordinate Transform Matrix)

**What**: 6-element transformation matrix from image streams

**Format**: `(a, b, c, d, e, f)`
- `a, d` = scaling (width, height)
- `b, c` = rotation/skew
- `e, f` = translation (x, y)

**Usage**:
```python
ctm = asset.ctm  # (1.0, 0.0, 0.0, 1.0, 72.0, 144.0)
scale_x, skew_x, skew_y, scale_y, trans_x, trans_y = ctm
```

**Purpose**: Precise geometry reconstruction for asset placement

---

## Enhancement 2: SMask & Clipping

**What**: Transparency (soft mask) and clipping path detection

**Fields**:
- `has_smask: bool` - Transparency present
- `has_clip: bool` - Clipping path present
- `smask_data: Optional[bytes]` - Mask data (future)

**Usage**:
```python
if asset.has_smask:
    print("Asset has transparency")
if asset.has_clip:
    print("Asset has clipping path")
```

**Purpose**: Identify assets requiring special rendering

---

## Enhancement 3: Font Audit

**What**: Complete font metadata for vector PDFs

**Type**: `List[VectorFont]`

**Fields per font**:
- `font_name: str` - Font name (e.g., "ABCDEF+Arial-Bold")
- `embedded: bool` - Font data embedded in PDF
- `subset: bool` - Only subset of glyphs included
- `font_type: str` - Type1, TrueType, CIDFont, etc.

**Usage**:
```python
for font in asset.fonts:
    print(f"{font.font_name} ({font.font_type})")
    print(f"  Embedded: {font.embedded}, Subset: {font.subset}")
```

**Purpose**: Validate vector PDF self-containment

---

## Enhancement 4: SHA256 Hashing

**What**: Content-based 256-bit hash (NOT SHA1)

**Format**: 64 hex characters

**Usage**:
```python
sha256 = asset.sha256  # "abc123def456..."
short = sha256[:12]    # "abc123def456"
```

**Purpose**: Reliable content deduplication

---

## Enhancement 5: Multi-Occurrence Tracking

**What**: Same content → multiple asset IDs with occurrence counter

**Logic**:
1. Calculate SHA256 hash
2. Track occurrence count per hash
3. Generate unique asset IDs with occurrence

**Example**:
```
Hash: abc123...
├─ img-abc123-p0-occ1  (first occurrence)
├─ img-abc123-p2-occ2  (second occurrence)
└─ img-abc123-p5-occ3  (third occurrence)
```

**Usage**:
```python
# Find all occurrences of same content
duplicates = ledger.find_by_sha256(asset.sha256)
print(f"Content appears {len(duplicates)} times")
```

**Purpose**: Track content reuse across pages

---

## Enhancement 6: BBox Extraction

**What**: Precise bounding box in PDF coordinate system

**Format**: `BBox(x0, y0, x1, y1)` in points (72 dpi)

**Properties**:
- `width: float` - Width in points
- `height: float` - Height in points
- `area: float` - Area in square points
- `center: Tuple[float, float]` - Center point

**Usage**:
```python
bbox = asset.bbox
print(f"Position: ({bbox.x0:.1f}, {bbox.y0:.1f})")
print(f"Size: {bbox.width:.1f} x {bbox.height:.1f} pts")
print(f"Area: {bbox.area:.1f} sq pts")
```

**Purpose**: Anchoring assets to text blocks

---

## Enhancement 7: Page Number & Reading Order

**What**: 0-indexed page number for asset tracking

**Usage**:
```python
page_num = asset.page_number  # 0 for first page
page_assets = ledger.by_page(page_num)
print(f"Page {page_num} has {len(page_assets)} assets")
```

**Purpose**: Maintain document structure in extraction

---

## Enhancement 8: ICC Color Profiles

**What**: Color space and ICC profile extraction

**Color Spaces**:
- `RGB` - sRGB / device RGB
- `CMYK` - Device CMYK
- `GRAY` - Grayscale
- `ICC` - ICC-based color

**Fields**:
- `colorspace: ColorSpace` - Color space enum
- `icc_profile: Optional[bytes]` - ICC profile data

**Usage**:
```python
colorspace = asset.colorspace
if colorspace == ColorSpace.ICC:
    print(f"ICC profile: {len(asset.icc_profile)} bytes")
```

**Purpose**: Color-accurate reproduction

---

## Enhancement 9: Image Dimensions

**What**: Pixel dimensions for DPI calculation

**Fields**:
- `image_width: int` - Width in pixels
- `image_height: int` - Height in pixels

**Usage**:
```python
# Calculate DPI
dpi_x = (asset.image_width / asset.bbox.width) * 72
dpi_y = (asset.image_height / asset.bbox.height) * 72
print(f"DPI: {dpi_x:.0f} x {dpi_y:.0f}")
```

**Purpose**: Quality assessment and upscaling decisions

---

## Enhancement 10: File Export

**What**: Export to PNG/PDF/JPEG files

**Formats**:
- Images: PNG, JPEG, TIFF (original format)
- Vectors: PDF (original) + PNG (fallback)
- Tables: PDF (original) + PNG (fallback)

**Usage**:
```python
file_path = asset.file_path
if file_path.exists():
    size = file_path.stat().st_size
    print(f"Exported: {file_path.name} ({size:,} bytes)")
```

**Purpose**: Reusable asset files for downstream processing

---

## Enhancement 11: Vector Graphics Extraction

**What**: Extract vector graphics as PDF fragments with rasterization fallback

**Process**:
1. Extract vector region as PDF
2. Preserve curves, paths, fills
3. Audit fonts for self-containment
4. Create PNG fallback at configured DPI

**Output**:
- `vec-{hash}-p{page}-occ{n}.pdf` - Original vector
- `vec-{hash}-p{page}-occ{n}.png` - Rasterized fallback

**Usage**:
```python
vectors = ledger.by_type(AssetType.VECTOR_PDF)
for vec in vectors:
    print(f"Vector: {vec.asset_id}")
    print(f"  Fonts: {len(vec.fonts)}")
    print(f"  PDF: {vec.file_path}")
```

**Purpose**: Preserve scalable graphics, provide fallback for compatibility

---

## Enhancement 12: Table Extraction

**What**: Extract tables as visual snapshots (PDF/PNG)

**Method**: `snapshot` (default) vs `live` (structure)

**Process**:
1. Detect table regions via PyMuPDF `find_tables()`
2. Extract region as PDF snippet
3. Create PNG rasterization
4. Store as `TABLE_SNAP` asset

**Output**:
- `tbl-{hash}-p{page}-occ{n}.pdf` - Original table
- `tbl-{hash}-p{page}-occ{n}.png` - Rasterized fallback

**Usage**:
```python
tables = ledger.by_type(AssetType.TABLE_SNAP)
for tbl in tables:
    print(f"Table: {tbl.asset_id}")
    print(f"  Size: {tbl.bbox.width:.1f} x {tbl.bbox.height:.1f} pts")
```

**Purpose**: Treat tables as visual assets for anchoring

---

## Summary Table

| # | Enhancement | Field(s) | Type | Purpose |
|---|------------|----------|------|---------|
| 1 | CTM | `ctm` | `Tuple[float, ...]` | Transformation matrix |
| 2 | SMask/Clip | `has_smask`, `has_clip` | `bool` | Transparency detection |
| 3 | Font Audit | `fonts` | `List[VectorFont]` | Vector self-containment |
| 4 | SHA256 | `sha256` | `str` | Content hashing |
| 5 | Multi-Occurrence | `occurrence` | `int` | Deduplication tracking |
| 6 | BBox | `bbox` | `BBox` | Anchoring coordinates |
| 7 | Page Number | `page_number` | `int` | Document structure |
| 8 | ICC Profiles | `colorspace`, `icc_profile` | `ColorSpace`, `bytes` | Color accuracy |
| 9 | Dimensions | `image_width`, `image_height` | `int` | DPI calculation |
| 10 | File Export | `file_path` | `Path` | Reusable files |
| 11 | Vector Graphics | `asset_type=VECTOR_PDF` | `AssetType` | Scalable graphics |
| 12 | Table Extraction | `asset_type=TABLE_SNAP` | `AssetType` | Table snapshots |

---

## Validation

All enhancements are validated in `Asset.__post_init__()`:

```python
def __post_init__(self) -> None:
    assert self.sha256, "SHA256 hash required"
    assert len(self.sha256) == 64, "SHA256 must be 64 hex chars"
    assert self.occurrence >= 1, "Occurrence must be ≥1"

    if self.asset_type == AssetType.IMAGE:
        assert self.image_width and self.image_height, \
            "Image dimensions required for IMAGE type"

    if self.asset_type == AssetType.TABLE_LIVE:
        assert self.table_data, "TABLE_LIVE requires table_data"
```

---

## Complete Asset Example

```python
Asset(
    # Identity (Enhancements 4, 5)
    asset_id="img-abc123def456-p0-occ1",
    asset_type=AssetType.IMAGE,
    sha256="abc123def456...",  # 64 chars
    occurrence=1,

    # Location (Enhancements 6, 7)
    page_number=0,
    bbox=BBox(x0=72.0, y0=144.0, x1=288.0, y1=360.0),

    # Transform (Enhancement 1)
    ctm=(1.0, 0.0, 0.0, 1.0, 72.0, 144.0),

    # Transparency (Enhancement 2)
    has_smask=True,
    has_clip=False,

    # Color (Enhancement 8)
    colorspace=ColorSpace.RGB,
    icc_profile=None,

    # Dimensions (Enhancement 9)
    image_width=1800,
    image_height=2400,

    # Export (Enhancement 10)
    file_path=Path("output/images/img-abc123def456-p0-occ1.png"),

    # Anchoring (set later)
    anchor_to="",

    # Optional
    caption_text=None,
    fonts=[],  # Enhancement 3 (for vectors)
)
```

---

## Next Steps

After PyMuPDF extraction (Day 3):

1. **Day 4**: Vision model anchoring to populate `anchor_to` field
2. **Day 5**: Markdown assembly using anchored assets

The AssetLedger is the SOURCE OF TRUTH for all visual assets in the document.
