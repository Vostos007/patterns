"""InDesign placed object metadata system.

This module defines the complete metadata structure for InDesign placed objects,
enabling full traceability from PDF extraction through InDesign placement.

The metadata is serialized to compact JSON and embedded in InDesign objects using
the extractLabel API, allowing bidirectional verification and validation.

Key Components:
    - PlacedObjectMetadata: Complete metadata dataclass
    - Schema versioning for future compatibility
    - Conversion from Asset objects to placement metadata

Usage:
    >>> from kps.core import Asset, BBox, NormalizedBBox
    >>> from kps.indesign.metadata import PlacedObjectMetadata
    >>>
    >>> # Create metadata from an Asset
    >>> metadata = PlacedObjectMetadata.from_asset(
    ...     asset=my_asset,
    ...     column_id=0,
    ...     normalized_bbox=NormalizedBBox(0.1, 0.2, 0.5, 0.3),
    ...     anchor_to="p.materials.001"
    ... )
    >>>
    >>> # Serialize for InDesign
    >>> json_str = metadata.to_json()
    >>>
    >>> # Deserialize after extraction
    >>> extracted_metadata = PlacedObjectMetadata.from_json(json_str)
    >>>
    >>> # Validate metadata integrity
    >>> errors = extracted_metadata.validate()
    >>> if errors:
    ...     print(f"Validation errors: {errors}")

Schema Version: 1.0
"""

from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict, Any
from pathlib import Path
from datetime import datetime, timezone
import json

from ..core.bbox import BBox, NormalizedBBox
from ..core.assets import Asset, AssetType, ColorSpace, VectorFont


CURRENT_SCHEMA_VERSION = "1.0"


@dataclass
class PlacedObjectMetadata:
    """
    Complete metadata for InDesign placed object.

    This class encapsulates ALL information needed to:
    1. Identify the original PDF asset
    2. Reconstruct placement coordinates
    3. Validate placement accuracy
    4. Handle asset properties (transparency, fonts, color)

    Attributes:
        # Identity
        asset_id: Unique identifier (e.g., "img-abc123def456-p0-occ1")
        asset_type: Asset type ("image", "vector", "table_snap")

        # Original asset data
        original_bbox: BBox in PDF coordinates (x0, y0, x1, y1)
        ctm: Current Transformation Matrix [a, b, c, d, e, f]
        page_number: 0-indexed page number in source PDF
        occurrence: Occurrence number for duplicate content (1-indexed)

        # Anchoring information
        anchor_to: Block ID this asset anchors to (e.g., "p.materials.001")
        column_id: Column index (0-indexed, left-to-right)
        normalized_bbox: Position in column-relative coords (0-1 range)

        # Asset properties
        sha256: Content hash (64 hex characters)
        file_path: Relative path to exported asset file
        has_smask: True if asset has transparency mask
        has_clip: True if asset has clipping path
        fonts: List of font names (for vector assets)
        colorspace: Color space ("RGB", "CMYK", "GRAY", "ICC")
        icc_profile_name: ICC profile name if present
        image_dimensions: (width, height) in pixels for images

        # Placement validation
        expected_bbox_placed: Calculated target bbox in InDesign (optional)
        actual_bbox_placed: Actual bbox extracted from InDesign (optional)

        # Metadata
        schema_version: Schema version for compatibility
        created_at: ISO 8601 timestamp
    """

    # ===== Identity =====
    asset_id: str
    asset_type: str

    # ===== Original asset data =====
    original_bbox: BBox
    ctm: Tuple[float, float, float, float, float, float]
    page_number: int
    occurrence: int

    # ===== Anchoring =====
    anchor_to: str
    column_id: int
    normalized_bbox: NormalizedBBox

    # ===== Asset properties =====
    sha256: str
    file_path: str
    has_smask: bool = False
    has_clip: bool = False
    fonts: List[str] = field(default_factory=list)
    colorspace: str = "RGB"
    icc_profile_name: Optional[str] = None
    image_dimensions: Optional[Tuple[int, int]] = None

    # ===== Placement validation =====
    expected_bbox_placed: Optional[BBox] = None
    actual_bbox_placed: Optional[BBox] = None

    # ===== Metadata =====
    schema_version: str = CURRENT_SCHEMA_VERSION
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        """Validate metadata after initialization."""
        # Validate required string fields
        if not self.asset_id:
            raise ValueError("asset_id cannot be empty")
        if not self.asset_type:
            raise ValueError("asset_type cannot be empty")
        if not self.anchor_to:
            raise ValueError("anchor_to cannot be empty")
        if not self.sha256:
            raise ValueError("sha256 cannot be empty")
        if len(self.sha256) != 64:
            raise ValueError(f"sha256 must be 64 hex characters, got {len(self.sha256)}")

        # Validate integers
        if self.page_number < 0:
            raise ValueError(f"page_number must be >= 0, got {self.page_number}")
        if self.occurrence < 1:
            raise ValueError(f"occurrence must be >= 1, got {self.occurrence}")
        if self.column_id < 0:
            raise ValueError(f"column_id must be >= 0, got {self.column_id}")

        # Validate CTM length
        if len(self.ctm) != 6:
            raise ValueError(f"ctm must have 6 elements, got {len(self.ctm)}")

        # Validate image_dimensions if present
        if self.image_dimensions is not None:
            if len(self.image_dimensions) != 2:
                raise ValueError("image_dimensions must be (width, height) tuple")
            w, h = self.image_dimensions
            if w <= 0 or h <= 0:
                raise ValueError(f"image_dimensions must be positive, got {self.image_dimensions}")

    @classmethod
    def from_asset(
        cls,
        asset: Asset,
        column_id: int,
        normalized_bbox: NormalizedBBox,
        anchor_to: str,
        expected_bbox_placed: Optional[BBox] = None,
    ) -> "PlacedObjectMetadata":
        """
        Create metadata from Asset object.

        This is the primary constructor for creating metadata during the
        anchoring phase. It extracts all relevant information from the Asset
        object and combines it with placement information.

        Args:
            asset: Source Asset object from PDF extraction
            column_id: Column index for placement (0-indexed)
            normalized_bbox: Position in column-relative coordinates
            anchor_to: Block ID to anchor this asset to
            expected_bbox_placed: Optional pre-calculated target bbox in InDesign

        Returns:
            PlacedObjectMetadata instance ready for serialization

        Example:
            >>> asset = Asset(
            ...     asset_id="img-abc123",
            ...     asset_type=AssetType.IMAGE,
            ...     sha256="a1b2c3...",
            ...     page_number=0,
            ...     bbox=BBox(100, 200, 300, 400),
            ...     ctm=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
            ...     file_path=Path("output/assets/img-abc123.png"),
            ...     occurrence=1,
            ...     anchor_to="p.materials.001",
            ...     image_width=1200,
            ...     image_height=800,
            ... )
            >>> metadata = PlacedObjectMetadata.from_asset(
            ...     asset=asset,
            ...     column_id=0,
            ...     normalized_bbox=NormalizedBBox(0.1, 0.2, 0.5, 0.3),
            ...     anchor_to="p.materials.001"
            ... )
        """
        # Convert AssetType enum to string
        asset_type_str = asset.asset_type.value

        # Convert ColorSpace enum to string
        colorspace_str = asset.colorspace.value.upper() if asset.colorspace else "RGB"

        # Extract font names from VectorFont objects
        font_names = [f.font_name for f in asset.fonts] if asset.fonts else []

        # Build image dimensions tuple
        image_dims = None
        if asset.image_width is not None and asset.image_height is not None:
            image_dims = (asset.image_width, asset.image_height)

        # Extract ICC profile name (placeholder - would need to parse from icc_profile bytes)
        icc_name = None
        if asset.icc_profile:
            # In a full implementation, parse ICC profile bytes to extract name
            icc_name = "ICC Profile Present"

        return cls(
            # Identity
            asset_id=asset.asset_id,
            asset_type=asset_type_str,

            # Original asset data
            original_bbox=asset.bbox,
            ctm=asset.ctm,
            page_number=asset.page_number,
            occurrence=asset.occurrence,

            # Anchoring
            anchor_to=anchor_to,
            column_id=column_id,
            normalized_bbox=normalized_bbox,

            # Asset properties
            sha256=asset.sha256,
            file_path=str(asset.file_path),
            has_smask=asset.has_smask,
            has_clip=asset.has_clip,
            fonts=font_names,
            colorspace=colorspace_str,
            icc_profile_name=icc_name,
            image_dimensions=image_dims,

            # Placement validation
            expected_bbox_placed=expected_bbox_placed,
            actual_bbox_placed=None,  # Will be set after InDesign placement
        )

    def to_json(self) -> str:
        """
        Serialize to compact JSON string for InDesign extractLabel.

        The JSON is optimized for size while maintaining readability:
        - No unnecessary whitespace
        - Short key names where practical
        - Optional fields omitted if None

        Returns:
            Compact JSON string (typically < 1KB)

        Example:
            >>> metadata = PlacedObjectMetadata(...)
            >>> json_str = metadata.to_json()
            >>> len(json_str)  # Should be < 1024 bytes
            856
        """
        # Build dict with all required fields
        data: Dict[str, Any] = {
            # Identity
            "asset_id": self.asset_id,
            "asset_type": self.asset_type,

            # Original asset data
            "original_bbox": [
                self.original_bbox.x0,
                self.original_bbox.y0,
                self.original_bbox.x1,
                self.original_bbox.y1,
            ],
            "ctm": list(self.ctm),
            "page_number": self.page_number,
            "occurrence": self.occurrence,

            # Anchoring
            "anchor_to": self.anchor_to,
            "column_id": self.column_id,
            "normalized_bbox": {
                "x": self.normalized_bbox.x,
                "y": self.normalized_bbox.y,
                "w": self.normalized_bbox.w,
                "h": self.normalized_bbox.h,
            },

            # Asset properties
            "sha256": self.sha256,
            "file_path": self.file_path,
            "has_smask": self.has_smask,
            "has_clip": self.has_clip,
            "colorspace": self.colorspace,

            # Metadata
            "schema_version": self.schema_version,
            "created_at": self.created_at,
        }

        # Add optional fields only if present
        if self.fonts:
            data["fonts"] = self.fonts

        if self.icc_profile_name:
            data["icc_profile_name"] = self.icc_profile_name

        if self.image_dimensions:
            data["image_dimensions"] = list(self.image_dimensions)

        if self.expected_bbox_placed:
            data["expected_bbox_placed"] = [
                self.expected_bbox_placed.x0,
                self.expected_bbox_placed.y0,
                self.expected_bbox_placed.x1,
                self.expected_bbox_placed.y1,
            ]

        if self.actual_bbox_placed:
            data["actual_bbox_placed"] = [
                self.actual_bbox_placed.x0,
                self.actual_bbox_placed.y0,
                self.actual_bbox_placed.x1,
                self.actual_bbox_placed.y1,
            ]

        # Serialize to compact JSON (no indent, ensure_ascii=False for UTF-8)
        return json.dumps(data, ensure_ascii=False, separators=(',', ':'))

    @classmethod
    def from_json(cls, json_str: str) -> "PlacedObjectMetadata":
        """
        Deserialize from JSON string.

        Handles schema versioning and validates all required fields.

        Args:
            json_str: JSON string from InDesign extractLabel

        Returns:
            PlacedObjectMetadata instance

        Raises:
            ValueError: If JSON is invalid or missing required fields
            KeyError: If required fields are missing

        Example:
            >>> json_str = '{"asset_id":"img-abc123",...}'
            >>> metadata = PlacedObjectMetadata.from_json(json_str)
        """
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")

        # Check schema version
        schema_version = data.get("schema_version", "1.0")
        if schema_version != CURRENT_SCHEMA_VERSION:
            # In future, call migration function here
            pass

        # Parse BBox objects
        original_bbox_data = data["original_bbox"]
        original_bbox = BBox(
            x0=original_bbox_data[0],
            y0=original_bbox_data[1],
            x1=original_bbox_data[2],
            y1=original_bbox_data[3],
        )

        # Parse NormalizedBBox
        norm_bbox_data = data["normalized_bbox"]
        normalized_bbox = NormalizedBBox(
            x=norm_bbox_data["x"],
            y=norm_bbox_data["y"],
            w=norm_bbox_data["w"],
            h=norm_bbox_data["h"],
        )

        # Parse optional BBox fields
        expected_bbox_placed = None
        if "expected_bbox_placed" in data:
            ebb = data["expected_bbox_placed"]
            expected_bbox_placed = BBox(x0=ebb[0], y0=ebb[1], x1=ebb[2], y1=ebb[3])

        actual_bbox_placed = None
        if "actual_bbox_placed" in data:
            abb = data["actual_bbox_placed"]
            actual_bbox_placed = BBox(x0=abb[0], y0=abb[1], x1=abb[2], y1=abb[3])

        # Parse image_dimensions
        image_dimensions = None
        if "image_dimensions" in data:
            img_dims = data["image_dimensions"]
            image_dimensions = (img_dims[0], img_dims[1])

        # Create instance
        return cls(
            # Identity
            asset_id=data["asset_id"],
            asset_type=data["asset_type"],

            # Original asset data
            original_bbox=original_bbox,
            ctm=tuple(data["ctm"]),
            page_number=data["page_number"],
            occurrence=data["occurrence"],

            # Anchoring
            anchor_to=data["anchor_to"],
            column_id=data["column_id"],
            normalized_bbox=normalized_bbox,

            # Asset properties
            sha256=data["sha256"],
            file_path=data["file_path"],
            has_smask=data.get("has_smask", False),
            has_clip=data.get("has_clip", False),
            fonts=data.get("fonts", []),
            colorspace=data.get("colorspace", "RGB"),
            icc_profile_name=data.get("icc_profile_name"),
            image_dimensions=image_dimensions,

            # Placement validation
            expected_bbox_placed=expected_bbox_placed,
            actual_bbox_placed=actual_bbox_placed,

            # Metadata
            schema_version=schema_version,
            created_at=data.get("created_at", ""),
        )

    def validate(self) -> List[str]:
        """
        Validate metadata integrity.

        Returns:
            List of validation error messages (empty if valid)

        Checks:
            - All required fields present
            - Coordinate ranges (0-1 for normalized)
            - CTM matrix validity
            - BBox consistency
            - Asset type validity

        Example:
            >>> metadata = PlacedObjectMetadata(...)
            >>> errors = metadata.validate()
            >>> if errors:
            ...     for error in errors:
            ...         print(f"ERROR: {error}")
            ... else:
            ...     print("Metadata is valid")
        """
        from .validation import (
            validate_normalized_coords,
            validate_ctm,
            validate_bbox_consistency,
        )

        errors: List[str] = []

        # Validate normalized bbox
        norm_errors = validate_normalized_coords(self.normalized_bbox)
        errors.extend(norm_errors)

        # Validate CTM
        ctm_errors = validate_ctm(self.ctm)
        errors.extend(ctm_errors)

        # Validate asset type
        valid_types = ["image", "vector_pdf", "vector_png", "table_live", "table_snap"]
        if self.asset_type not in valid_types:
            errors.append(f"Invalid asset_type: {self.asset_type} (must be one of {valid_types})")

        # Validate colorspace
        valid_colorspaces = ["RGB", "CMYK", "GRAY", "ICC", "rgb", "cmyk", "gray", "icc"]
        if self.colorspace not in valid_colorspaces:
            errors.append(f"Invalid colorspace: {self.colorspace}")

        # Validate BBox consistency (if we have placement data)
        # This would require column_bbox to reconstruct, so we defer to external validation

        return errors

    def update_actual_bbox(self, bbox: BBox) -> None:
        """
        Update actual placed bbox after InDesign placement.

        This should be called by the verification script after extracting
        the actual placement coordinates from InDesign.

        Args:
            bbox: Actual BBox from InDesign geometric bounds
        """
        object.__setattr__(self, "actual_bbox_placed", bbox)

    def placement_error(self) -> Optional[float]:
        """
        Calculate placement error if both expected and actual bboxes are set.

        Returns:
            Maximum deviation in points, or None if can't calculate

        Example:
            >>> error = metadata.placement_error()
            >>> if error is not None:
            ...     print(f"Placement error: {error:.2f} pt")
        """
        if not self.expected_bbox_placed or not self.actual_bbox_placed:
            return None

        exp = self.expected_bbox_placed
        act = self.actual_bbox_placed

        # Calculate max deviation across all coordinates
        errors = [
            abs(exp.x0 - act.x0),
            abs(exp.y0 - act.y0),
            abs(exp.x1 - act.x1),
            abs(exp.y1 - act.y1),
        ]

        return max(errors)
