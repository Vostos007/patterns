"""Asset models for KPS with complete metadata tracking."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple
import json

from .bbox import BBox


class AssetType(Enum):
    """Types of visual assets."""

    IMAGE = "image"  # XObject bitmap (JPEG, PNG, etc.)
    VECTOR_PDF = "vector_pdf"  # PDF fragment (preserves curves)
    VECTOR_PNG = "vector_png"  # Rasterized vector (fallback)
    TABLE_LIVE = "table_live"  # Extracted table structure
    TABLE_SNAP = "table_snap"  # PDF/PNG snapshot (default for tables)


class ColorSpace(Enum):
    """Color space types."""

    RGB = "rgb"
    CMYK = "cmyk"
    GRAY = "gray"
    ICC = "icc"


@dataclass
class VectorFont:
    """Font metadata for VECTOR_PDF assets."""

    font_name: str
    embedded: bool
    subset: bool
    font_type: str  # Type1, TrueType, CIDFont, etc.


@dataclass
class Asset:
    """
    Complete visual asset with all metadata.

    CRITICAL FIELDS (must never be None):
    - asset_id: Unique identifier
    - sha256: Content hash for deduplication
    - anchor_to: Block ID for placement (set by anchoring algorithm)
    """

    # Identity
    asset_id: str  # e.g., "img-abc123def456-p3-occ1"
    asset_type: AssetType
    sha256: str  # 256-bit hash (not 160-bit sha1!)

    # Location in source PDF
    page_number: int  # 0-indexed
    bbox: BBox  # Bounding box in PDF points
    ctm: Tuple[float, float, float, float, float, float]  # Transform matrix [a,b,c,d,e,f]

    # File export
    file_path: Path  # Exported PNG/PDF/SVG

    # Multi-occurrence tracking
    occurrence: int  # If same sha256 appears multiple times

    # Anchoring (REQUIRED after anchoring phase)
    anchor_to: str  # Block ID (e.g., "p.materials.001")

    # Caption (optional, auto-detected)
    caption_text: Optional[str] = None

    # Color/ICC metadata
    colorspace: ColorSpace = ColorSpace.RGB
    icc_profile: Optional[bytes] = None

    # Transparency/Clipping (NEW - Enhancement 2)
    has_smask: bool = False
    has_clip: bool = False
    smask_data: Optional[bytes] = None

    # Fonts (for VECTOR_PDF only - Enhancement 3)
    fonts: List[VectorFont] = field(default_factory=list)

    # Image dimensions (for DPI calculation)
    image_width: Optional[int] = None  # pixels
    image_height: Optional[int] = None  # pixels

    # Table-specific (for TABLE_LIVE only)
    table_data: Optional[dict] = None
    table_confidence: Optional[float] = None

    def __post_init__(self) -> None:
        """Validation after initialization."""
        assert self.sha256, "SHA256 hash required"
        assert len(self.sha256) == 64, f"SHA256 must be 64 hex chars, got {len(self.sha256)}"
        assert self.occurrence >= 1, f"Occurrence must be ≥1, got {self.occurrence}"

        if self.asset_type == AssetType.IMAGE:
            assert (
                self.image_width and self.image_height
            ), "Image dimensions required for IMAGE type"

        if self.asset_type == AssetType.TABLE_LIVE:
            assert self.table_data, "TABLE_LIVE requires table_data"


@dataclass
class AssetLedger:
    """
    Complete registry of all visual assets.

    This is the SOURCE OF TRUTH for all graphics in the document.
    EVERY asset must be tracked here.
    """

    assets: List[Asset]
    source_pdf: Path
    total_pages: int

    def by_page(self, page: int) -> List[Asset]:
        """Get all assets on a specific page."""
        return [a for a in self.assets if a.page_number == page]

    def by_type(self, asset_type: AssetType) -> List[Asset]:
        """Get all assets of specific type."""
        return [a for a in self.assets if a.asset_type == asset_type]

    def find_by_id(self, asset_id: str) -> Optional[Asset]:
        """Find asset by ID."""
        for asset in self.assets:
            if asset.asset_id == asset_id:
                return asset
        return None

    def find_by_sha256(self, sha256: str) -> List[Asset]:
        """Find all occurrences of same content (by hash)."""
        return [a for a in self.assets if a.sha256 == sha256]

    def completeness_check(self) -> dict:
        """Return counts by page and type."""
        return {
            "by_page": {p: len(self.by_page(p)) for p in range(self.total_pages)},
            "by_type": {t.value: len(self.by_type(t)) for t in AssetType},
            "total": len(self.assets),
        }

    def save_json(self, path: Path) -> None:
        """Serialize to JSON."""
        data = {
            "source_pdf": str(self.source_pdf),
            "total_pages": self.total_pages,
            "assets": [
                {
                    "asset_id": a.asset_id,
                    "asset_type": a.asset_type.value,
                    "sha256": a.sha256,
                    "page_number": a.page_number,
                    "bbox": {
                        "x0": a.bbox.x0,
                        "y0": a.bbox.y0,
                        "x1": a.bbox.x1,
                        "y1": a.bbox.y1,
                    },
                    "ctm": list(a.ctm),
                    "file_path": str(a.file_path),
                    "occurrence": a.occurrence,
                    "anchor_to": a.anchor_to,
                    "caption_text": a.caption_text,
                    "colorspace": a.colorspace.value if a.colorspace else None,
                    "has_smask": a.has_smask,
                    "has_clip": a.has_clip,
                    "fonts": [
                        {
                            "font_name": f.font_name,
                            "embedded": f.embedded,
                            "subset": f.subset,
                            "font_type": f.font_type,
                        }
                        for f in a.fonts
                    ]
                    if a.fonts
                    else [],
                    "image_width": a.image_width,
                    "image_height": a.image_height,
                    "table_data": a.table_data,
                    "table_confidence": a.table_confidence,
                }
                for a in self.assets
            ],
        }
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    @classmethod
    def load_json(cls, path: Path) -> "AssetLedger":
        """Deserialize from JSON."""
        data = json.loads(path.read_text())

        assets = [
            Asset(
                asset_id=a["asset_id"],
                asset_type=AssetType(a["asset_type"]),
                sha256=a["sha256"],
                page_number=a["page_number"],
                bbox=BBox(**a["bbox"]),
                ctm=tuple(a["ctm"]),
                file_path=Path(a["file_path"]),
                occurrence=a["occurrence"],
                anchor_to=a["anchor_to"],
                caption_text=a.get("caption_text"),
                colorspace=ColorSpace(a["colorspace"]) if a.get("colorspace") else ColorSpace.RGB,
                has_smask=a.get("has_smask", False),
                has_clip=a.get("has_clip", False),
                fonts=[VectorFont(**f) for f in a.get("fonts", [])],
                image_width=a.get("image_width"),
                image_height=a.get("image_height"),
                table_data=a.get("table_data"),
                table_confidence=a.get("table_confidence"),
            )
            for a in data["assets"]
        ]

        return cls(
            assets=assets,
            source_pdf=Path(data["source_pdf"]),
            total_pages=data["total_pages"],
        )
