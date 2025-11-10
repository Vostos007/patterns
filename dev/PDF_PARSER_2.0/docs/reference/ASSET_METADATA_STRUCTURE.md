# Asset Metadata Structure - Complete Reference

## Asset Object Structure

```python
@dataclass
class Asset:
    """Complete visual asset with all 12 enhancements."""

    # ═══════════════════════════════════════════════════════════════
    # IDENTITY & DEDUPLICATION (Enhancements 4, 5)
    # ═══════════════════════════════════════════════════════════════
    asset_id: str                    # "img-abc123def456-p0-occ1"
    asset_type: AssetType            # IMAGE, VECTOR_PDF, VECTOR_PNG, TABLE_SNAP, TABLE_LIVE
    sha256: str                      # 64 hex chars (NOT SHA1!)
    occurrence: int                  # 1, 2, 3... (same hash → multiple assets)

    # ═══════════════════════════════════════════════════════════════
    # LOCATION & GEOMETRY (Enhancements 6, 7)
    # ═══════════════════════════════════════════════════════════════
    page_number: int                 # 0-indexed page
    bbox: BBox                       # (x0, y0, x1, y1) in PDF points (72 dpi)
                                     # Properties: width, height, area, center

    # ═══════════════════════════════════════════════════════════════
    # TRANSFORMATION (Enhancement 1)
    # ═══════════════════════════════════════════════════════════════
    ctm: Tuple[float, float, float, float, float, float]
                                     # [a, b, c, d, e, f]
                                     # a, d = scale (width, height)
                                     # b, c = rotation/skew
                                     # e, f = translation (x, y)

    # ═══════════════════════════════════════════════════════════════
    # FILE EXPORT (Enhancement 10)
    # ═══════════════════════════════════════════════════════════════
    file_path: Path                  # Exported PNG/PDF/JPEG file

    # ═══════════════════════════════════════════════════════════════
    # ANCHORING (Set by Day 4)
    # ═══════════════════════════════════════════════════════════════
    anchor_to: str                   # Block ID (e.g., "p.materials.001")

    # ═══════════════════════════════════════════════════════════════
    # OPTIONAL METADATA
    # ═══════════════════════════════════════════════════════════════
    caption_text: Optional[str] = None          # Auto-detected caption

    # ═══════════════════════════════════════════════════════════════
    # COLOR & ICC (Enhancement 8)
    # ═══════════════════════════════════════════════════════════════
    colorspace: ColorSpace = ColorSpace.RGB     # RGB, CMYK, GRAY, ICC
    icc_profile: Optional[bytes] = None         # ICC profile data

    # ═══════════════════════════════════════════════════════════════
    # TRANSPARENCY & CLIPPING (Enhancement 2)
    # ═══════════════════════════════════════════════════════════════
    has_smask: bool = False                     # Transparency present?
    has_clip: bool = False                      # Clipping path present?
    smask_data: Optional[bytes] = None          # SMask data (future)

    # ═══════════════════════════════════════════════════════════════
    # FONTS (Enhancement 3 - VECTOR_PDF only)
    # ═══════════════════════════════════════════════════════════════
    fonts: List[VectorFont] = field(default_factory=list)
                                     # Each VectorFont:
                                     #   - font_name: str
                                     #   - embedded: bool
                                     #   - subset: bool
                                     #   - font_type: str

    # ═══════════════════════════════════════════════════════════════
    # IMAGE DIMENSIONS (Enhancement 9 - IMAGE only)
    # ═══════════════════════════════════════════════════════════════
    image_width: Optional[int] = None           # Pixels
    image_height: Optional[int] = None          # Pixels

    # ═══════════════════════════════════════════════════════════════
    # TABLE DATA (TABLE_LIVE only)
    # ═══════════════════════════════════════════════════════════════
    table_data: Optional[dict] = None           # Structured table data
    table_confidence: Optional[float] = None    # Confidence score
```

---

## Validation Rules

```python
def __post_init__(self) -> None:
    # SHA256 required and must be 64 hex chars
    assert self.sha256, "SHA256 hash required"
    assert len(self.sha256) == 64, f"SHA256 must be 64 hex chars, got {len(self.sha256)}"

    # Occurrence must be ≥1
    assert self.occurrence >= 1, f"Occurrence must be ≥1, got {self.occurrence}"

    # Image dimensions required for IMAGE type
    if self.asset_type == AssetType.IMAGE:
        assert (
            self.image_width and self.image_height
        ), "Image dimensions required for IMAGE type"

    # Table data required for TABLE_LIVE
    if self.asset_type == AssetType.TABLE_LIVE:
        assert self.table_data, "TABLE_LIVE requires table_data"
```

---

## AssetLedger Structure

```python
@dataclass
class AssetLedger:
    """Complete registry of all visual assets (SOURCE OF TRUTH)."""

    assets: List[Asset]              # All extracted assets
    source_pdf: Path                 # Original PDF file
    total_pages: int                 # Number of pages

    # Query methods
    def by_page(self, page: int) -> List[Asset]
    def by_type(self, asset_type: AssetType) -> List[Asset]
    def find_by_id(self, asset_id: str) -> Optional[Asset]
    def find_by_sha256(self, sha256: str) -> List[Asset]

    # Statistics
    def completeness_check(self) -> dict:
        """
        Returns:
        {
            "by_page": {0: 5, 1: 3, ...},
            "by_type": {"image": 8, "vector_pdf": 2, ...},
            "total": 10
        }
        """

    # Persistence
    def save_json(self, path: Path) -> None
    @classmethod
    def load_json(cls, path: Path) -> "AssetLedger"
```

---

## BBox Structure

```python
@dataclass(frozen=True)
class BBox:
    """Bounding box in PDF coordinate system (72 dpi)."""

    x0: float                        # Left edge
    y0: float                        # Bottom edge (PDF coords)
    x1: float                        # Right edge
    y1: float                        # Top edge (PDF coords)

    # Computed properties
    @property
    def width(self) -> float:
        """Width in points."""
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        """Height in points."""
        return self.y1 - self.y0

    @property
    def center(self) -> Tuple[float, float]:
        """Center point (x, y)."""
        return ((self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2)

    @property
    def area(self) -> float:
        """Area in square points."""
        return self.width * self.height
```

---

## VectorFont Structure

```python
@dataclass
class VectorFont:
    """Font metadata for VECTOR_PDF assets (Enhancement 3)."""

    font_name: str                   # e.g., "ABCDEF+Arial-Bold"
    embedded: bool                   # True if font data embedded
    subset: bool                     # True if subset (random prefix)
    font_type: str                   # Type1, TrueType, CIDFont, etc.
```

---

## Enums

### AssetType

```python
class AssetType(Enum):
    IMAGE = "image"                  # XObject bitmap (JPEG, PNG, TIFF)
    VECTOR_PDF = "vector_pdf"        # PDF fragment (preserves curves)
    VECTOR_PNG = "vector_png"        # Rasterized vector (fallback)
    TABLE_LIVE = "table_live"        # Extracted table structure
    TABLE_SNAP = "table_snap"        # PDF/PNG snapshot (default)
```

### ColorSpace

```python
class ColorSpace(Enum):
    RGB = "rgb"                      # sRGB / device RGB
    CMYK = "cmyk"                    # Device CMYK
    GRAY = "gray"                    # Grayscale
    ICC = "icc"                      # ICC-based color
```

---

## Complete Example with All Fields

```python
asset = Asset(
    # Identity (Enhancements 4, 5)
    asset_id="img-abc123def456-p0-occ1",
    asset_type=AssetType.IMAGE,
    sha256="abc123def456789abcdef0123456789abcdef0123456789abcdef0123456789a",
    occurrence=1,

    # Location (Enhancements 6, 7)
    page_number=0,
    bbox=BBox(x0=72.0, y0=144.0, x1=288.0, y1=360.0),
    # bbox.width = 216.0 pts
    # bbox.height = 216.0 pts
    # bbox.area = 46656.0 sq pts
    # bbox.center = (180.0, 252.0)

    # Transform (Enhancement 1)
    ctm=(1.0, 0.0, 0.0, 1.0, 72.0, 144.0),
    # a=1.0, b=0.0, c=0.0, d=1.0, e=72.0, f=144.0
    # No rotation, no skew, positioned at (72, 144)

    # File export (Enhancement 10)
    file_path=Path("output/images/img-abc123def456-p0-occ1.png"),

    # Anchoring (set by Day 4)
    anchor_to="p.materials.001",

    # Optional caption
    caption_text="Figure 1: Material sample A",

    # Color (Enhancement 8)
    colorspace=ColorSpace.RGB,
    icc_profile=None,

    # Transparency (Enhancement 2)
    has_smask=True,
    has_clip=False,
    smask_data=None,

    # Dimensions (Enhancement 9)
    image_width=1800,                # pixels
    image_height=1800,               # pixels
    # DPI_X = (1800 / 216.0) * 72 = 600 dpi
    # DPI_Y = (1800 / 216.0) * 72 = 600 dpi

    # Fonts (Enhancement 3, empty for images)
    fonts=[],

    # Table data (not applicable for images)
    table_data=None,
    table_confidence=None,
)
```

---

## Vector PDF Example

```python
vector_asset = Asset(
    asset_id="vec-789xyz012abc-p1-occ1",
    asset_type=AssetType.VECTOR_PDF,
    sha256="789xyz012abc456def...",
    occurrence=1,

    page_number=1,
    bbox=BBox(x0=100.0, y0=200.0, x1=400.0, y1=500.0),
    ctm=(1.0, 0.0, 0.0, 1.0, 100.0, 200.0),

    file_path=Path("output/vectors/vec-789xyz012abc-p1-occ1.pdf"),
    anchor_to="p.diagram.002",

    colorspace=ColorSpace.RGB,
    has_smask=False,
    has_clip=True,

    # Enhancement 3: Font audit for vectors
    fonts=[
        VectorFont(
            font_name="ABCDEF+Helvetica-Bold",
            embedded=True,
            subset=True,
            font_type="Type1"
        ),
        VectorFont(
            font_name="Times-Roman",
            embedded=False,
            subset=False,
            font_type="Type1"
        ),
    ],
)
```

---

## Table Snapshot Example

```python
table_asset = Asset(
    asset_id="tbl-456def789ghi-p3-occ1",
    asset_type=AssetType.TABLE_SNAP,
    sha256="456def789ghi012jkl...",
    occurrence=1,

    page_number=3,
    bbox=BBox(x0=50.0, y0=100.0, x1=550.0, y1=400.0),
    ctm=(1.0, 0.0, 0.0, 1.0, 50.0, 100.0),

    file_path=Path("output/tables/tbl-456def789ghi-p3-occ1.pdf"),
    anchor_to="p.table.001",

    colorspace=ColorSpace.RGB,
)
```

---

## Deduplication Example

```python
# Same image on multiple pages
hash_val = "abc123def456..."

# First occurrence
asset1 = Asset(
    asset_id="img-abc123-p0-occ1",   # occurrence = 1
    sha256=hash_val,
    page_number=0,
    occurrence=1,
    file_path=Path("output/images/img-abc123-p0-occ1.png"),
    # ... other fields
)

# Second occurrence (same content, different page)
asset2 = Asset(
    asset_id="img-abc123-p2-occ2",   # occurrence = 2
    sha256=hash_val,                 # SAME hash
    page_number=2,
    occurrence=2,
    file_path=Path("output/images/img-abc123-p0-occ1.png"),  # SAME file
    # ... other fields
)

# Third occurrence
asset3 = Asset(
    asset_id="img-abc123-p5-occ3",   # occurrence = 3
    sha256=hash_val,                 # SAME hash
    page_number=5,
    occurrence=3,
    file_path=Path("output/images/img-abc123-p0-occ1.png"),  # SAME file
    # ... other fields
)

# All three assets reference the same exported file
# Different asset_ids allow independent anchoring
```

---

## DPI Calculation

```python
# Given an image asset
asset = Asset(
    bbox=BBox(x0=72.0, y0=144.0, x1=288.0, y1=360.0),  # 216x216 pts
    image_width=1800,    # pixels
    image_height=1800,   # pixels
    # ... other fields
)

# Calculate DPI
width_pts = asset.bbox.width     # 216.0 points
height_pts = asset.bbox.height   # 216.0 points

dpi_x = (asset.image_width / width_pts) * 72
dpi_y = (asset.image_height / height_pts) * 72

print(f"DPI: {dpi_x:.0f} x {dpi_y:.0f}")  # "DPI: 600 x 600"
```

---

## JSON Serialization Format

```json
{
  "source_pdf": "pattern.pdf",
  "total_pages": 10,
  "assets": [
    {
      "asset_id": "img-abc123def456-p0-occ1",
      "asset_type": "image",
      "sha256": "abc123def456...",
      "page_number": 0,
      "bbox": {
        "x0": 72.0,
        "y0": 144.0,
        "x1": 288.0,
        "y1": 360.0
      },
      "ctm": [1.0, 0.0, 0.0, 1.0, 72.0, 144.0],
      "file_path": "output/images/img-abc123def456-p0-occ1.png",
      "occurrence": 1,
      "anchor_to": "p.materials.001",
      "caption_text": "Figure 1: Material sample",
      "colorspace": "rgb",
      "has_smask": true,
      "has_clip": false,
      "fonts": [],
      "image_width": 1800,
      "image_height": 1800,
      "table_data": null,
      "table_confidence": null
    }
  ]
}
```

---

## Summary: Field Usage by Asset Type

| Field | IMAGE | VECTOR_PDF | TABLE_SNAP | TABLE_LIVE |
|-------|-------|------------|------------|------------|
| `asset_id` | ✓ | ✓ | ✓ | ✓ |
| `asset_type` | ✓ | ✓ | ✓ | ✓ |
| `sha256` | ✓ | ✓ | ✓ | ✓ |
| `page_number` | ✓ | ✓ | ✓ | ✓ |
| `bbox` | ✓ | ✓ | ✓ | ✓ |
| `ctm` | ✓ | ✓ | ✓ | ✓ |
| `file_path` | ✓ | ✓ | ✓ | ✓ |
| `occurrence` | ✓ | ✓ | ✓ | ✓ |
| `anchor_to` | ✓ | ✓ | ✓ | ✓ |
| `caption_text` | optional | optional | optional | optional |
| `colorspace` | ✓ | ✓ | ✓ | ✓ |
| `icc_profile` | ✓ | optional | optional | - |
| `has_smask` | ✓ | optional | - | - |
| `has_clip` | ✓ | ✓ | optional | - |
| `smask_data` | ✓ | optional | - | - |
| `fonts` | - | ✓ | optional | - |
| `image_width` | ✓ (required) | - | - | - |
| `image_height` | ✓ (required) | - | - | - |
| `table_data` | - | - | - | ✓ (required) |
| `table_confidence` | - | - | - | optional |

---

## References

- **Implementation**: `/kps/extraction/pymupdf_extractor.py`
- **Asset Models**: `/kps/core/assets.py`
- **BBox Types**: `/kps/core/bbox.py`
- **Usage Guide**: `/docs/PYMUPDF_EXTRACTION.md`
- **Enhancement Details**: `/docs/12_ENHANCEMENTS.md`
