"""Asset data structures used by the extraction pipeline."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple

from .bbox import BBox


class AssetType(str, Enum):
    IMAGE = "image"
    VECTOR_PDF = "vector_pdf"
    VECTOR_PNG = "vector_png"
    TABLE_LIVE = "table_live"
    TABLE_SNAP = "table_snap"


class ColorSpace(str, Enum):
    RGB = "rgb"
    CMYK = "cmyk"
    GRAY = "gray"
    ICC = "icc"


@dataclass(slots=True)
class VectorFont:
    font_name: str
    embedded: bool
    subset: bool
    font_type: str


@dataclass(slots=True)
class Asset:
    asset_id: str
    asset_type: AssetType
    sha256: str
    page_number: int
    bbox: BBox
    ctm: Tuple[float, float, float, float, float, float]
    file_path: Path
    occurrence: int
    anchor_to: str
    caption_text: Optional[str] = None
    colorspace: ColorSpace = ColorSpace.RGB
    icc_profile: Optional[bytes] = None
    has_smask: bool = False
    has_clip: bool = False
    smask_data: Optional[bytes] = None
    fonts: List[VectorFont] = field(default_factory=list)
    image_width: Optional[int] = None
    image_height: Optional[int] = None
    table_data: Optional[dict] = None
    table_confidence: Optional[float] = None

    def __post_init__(self) -> None:
        if not self.sha256 or len(self.sha256) != 64:
            raise ValueError("Assets require a 64 character SHA256 hash")
        if self.occurrence < 1:
            raise ValueError("Occurrence counter must be >= 1")
        if self.asset_type == AssetType.IMAGE and (
            self.image_width is None or self.image_height is None
        ):
            raise ValueError("Bitmap assets must include image dimensions")
        if self.asset_type == AssetType.TABLE_LIVE and self.table_data is None:
            raise ValueError("Live table extraction results require table_data")


@dataclass(slots=True)
class AssetLedger:
    assets: List[Asset]
    source_pdf: Path
    total_pages: int

    def by_page(self, page: int) -> List[Asset]:
        return [asset for asset in self.assets if asset.page_number == page]

    def by_type(self, asset_type: AssetType) -> List[Asset]:
        return [asset for asset in self.assets if asset.asset_type == asset_type]

    def find_by_id(self, asset_id: str) -> Optional[Asset]:
        return next((asset for asset in self.assets if asset.asset_id == asset_id), None)

    def find_by_sha256(self, sha256: str) -> List[Asset]:
        return [asset for asset in self.assets if asset.sha256 == sha256]

    def completeness_check(self) -> dict:
        return {
            "by_page": {page: len(self.by_page(page)) for page in range(self.total_pages)},
            "by_type": {asset_type.value: len(self.by_type(asset_type)) for asset_type in AssetType},
            "total": len(self.assets),
        }

    def save_json(self, path: Path) -> None:
        payload = {
            "source_pdf": str(self.source_pdf),
            "total_pages": self.total_pages,
            "assets": [
                {
                    "asset_id": asset.asset_id,
                    "asset_type": asset.asset_type.value,
                    "sha256": asset.sha256,
                    "page_number": asset.page_number,
                    "bbox": {
                        "x0": asset.bbox.x0,
                        "y0": asset.bbox.y0,
                        "x1": asset.bbox.x1,
                        "y1": asset.bbox.y1,
                    },
                    "ctm": list(asset.ctm),
                    "file_path": str(asset.file_path),
                    "occurrence": asset.occurrence,
                    "anchor_to": asset.anchor_to,
                    "caption_text": asset.caption_text,
                    "colorspace": asset.colorspace.value if asset.colorspace else None,
                    "has_smask": asset.has_smask,
                    "has_clip": asset.has_clip,
                    "fonts": [
                        {
                            "font_name": font.font_name,
                            "embedded": font.embedded,
                            "subset": font.subset,
                            "font_type": font.font_type,
                        }
                        for font in asset.fonts
                    ],
                    "image_width": asset.image_width,
                    "image_height": asset.image_height,
                    "table_data": asset.table_data,
                    "table_confidence": asset.table_confidence,
                }
                for asset in self.assets
            ],
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load_json(cls, path: Path) -> "AssetLedger":
        data = json.loads(path.read_text(encoding="utf-8"))
        assets = [
            Asset(
                asset_id=item["asset_id"],
                asset_type=AssetType(item["asset_type"]),
                sha256=item["sha256"],
                page_number=item["page_number"],
                bbox=BBox(**item["bbox"]),
                ctm=tuple(item["ctm"]),
                file_path=Path(item["file_path"]),
                occurrence=item["occurrence"],
                anchor_to=item["anchor_to"],
                caption_text=item.get("caption_text"),
                colorspace=ColorSpace(item["colorspace"]) if item.get("colorspace") else ColorSpace.RGB,
                has_smask=item.get("has_smask", False),
                has_clip=item.get("has_clip", False),
                fonts=[VectorFont(**font) for font in item.get("fonts", [])],
                image_width=item.get("image_width"),
                image_height=item.get("image_height"),
                table_data=item.get("table_data"),
                table_confidence=item.get("table_confidence"),
            )
            for item in data.get("assets", [])
        ]

        return cls(assets=assets, source_pdf=Path(data["source_pdf"]), total_pages=data["total_pages"])


__all__ = [
    "AssetType",
    "ColorSpace",
    "VectorFont",
    "Asset",
    "AssetLedger",
]

