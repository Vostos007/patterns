"""Unit tests for InDesign Metadata System."""

import pytest
import json
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path


# Mock classes (will be implemented by Agent 2)
@dataclass
class NormalizedBBox:
    """Normalized bounding box (0.0-1.0 coordinate space)."""
    x: float  # Left edge (0.0-1.0)
    y: float  # Top edge (0.0-1.0)
    width: float  # Width (0.0-1.0)
    height: float  # Height (0.0-1.0)

    def validate(self) -> list[str]:
        """Validate normalized coordinates."""
        errors = []
        if not (0.0 <= self.x <= 1.0):
            errors.append(f"x={self.x} out of range [0.0, 1.0]")
        if not (0.0 <= self.y <= 1.0):
            errors.append(f"y={self.y} out of range [0.0, 1.0]")
        if not (0.0 <= self.width <= 1.0):
            errors.append(f"width={self.width} out of range [0.0, 1.0]")
        if not (0.0 <= self.height <= 1.0):
            errors.append(f"height={self.height} out of range [0.0, 1.0]")
        if self.x + self.width > 1.0:
            errors.append(f"x + width = {self.x + self.width} exceeds 1.0")
        if self.y + self.height > 1.0:
            errors.append(f"y + height = {self.y + self.height} exceeds 1.0")
        return errors


@dataclass
class PlacedObjectMetadata:
    """Metadata for a placed object in InDesign."""
    asset_id: str
    column_id: int
    normalized_bbox: NormalizedBBox
    ctm: tuple[float, float, float, float, float, float]  # Transformation matrix
    anchor_to: Optional[str] = None
    asset_type: str = "image"
    page_number: int = 0
    occurrence: int = 1

    def to_json(self) -> str:
        """Serialize to compact JSON string."""
        data = {
            "asset_id": self.asset_id,
            "column_id": self.column_id,
            "normalized_bbox": {
                "x": self.normalized_bbox.x,
                "y": self.normalized_bbox.y,
                "width": self.normalized_bbox.width,
                "height": self.normalized_bbox.height
            },
            "ctm": list(self.ctm),
            "anchor_to": self.anchor_to,
            "asset_type": self.asset_type,
            "page_number": self.page_number,
            "occurrence": self.occurrence
        }
        return json.dumps(data, separators=(',', ':'))

    @classmethod
    def from_json(cls, json_str: str) -> 'PlacedObjectMetadata':
        """Deserialize from JSON string."""
        data = json.loads(json_str)
        bbox_data = data["normalized_bbox"]
        normalized_bbox = NormalizedBBox(
            x=bbox_data["x"],
            y=bbox_data["y"],
            width=bbox_data["width"],
            height=bbox_data["height"]
        )
        return cls(
            asset_id=data["asset_id"],
            column_id=data["column_id"],
            normalized_bbox=normalized_bbox,
            ctm=tuple(data["ctm"]),
            anchor_to=data.get("anchor_to"),
            asset_type=data.get("asset_type", "image"),
            page_number=data.get("page_number", 0),
            occurrence=data.get("occurrence", 1)
        )

    @classmethod
    def from_asset(cls, asset: 'Asset', column_id: int, normalized_bbox: NormalizedBBox,
                   anchor_to: Optional[str] = None) -> 'PlacedObjectMetadata':
        """Create metadata from Asset object."""
        return cls(
            asset_id=asset.asset_id,
            column_id=column_id,
            normalized_bbox=normalized_bbox,
            ctm=asset.ctm,
            anchor_to=anchor_to,
            asset_type=asset.asset_type.value if hasattr(asset.asset_type, 'value') else str(asset.asset_type),
            page_number=asset.page_number,
            occurrence=asset.occurrence
        )

    def validate(self) -> list[str]:
        """Validate all metadata fields."""
        errors = []

        # Validate asset_id format
        import re
        if not re.match(r'^(img|vec|tbl)-[a-f0-9]{8}-p\d+-occ\d+$', self.asset_id):
            errors.append(f"Invalid asset_id format: {self.asset_id}")

        # Validate normalized bbox
        errors.extend(self.normalized_bbox.validate())

        # Validate CTM
        if len(self.ctm) != 6:
            errors.append(f"CTM must have 6 values, got {len(self.ctm)}")

        # Validate column_id
        if self.column_id < 0:
            errors.append(f"column_id must be >= 0, got {self.column_id}")

        return errors


@dataclass
class Asset:
    """Mock Asset class."""
    asset_id: str
    asset_type: str
    ctm: tuple[float, float, float, float, float, float]
    page_number: int = 0
    occurrence: int = 1


# ============================================================================
# TEST: PlacedObjectMetadata Creation
# ============================================================================


class TestPlacedObjectMetadataCreation:
    """Test creating PlacedObjectMetadata objects."""

    @pytest.fixture
    def sample_asset(self):
        """Create sample Asset."""
        return Asset(
            asset_id="img-abc12345-p0-occ1",
            asset_type="image",
            ctm=(1.0, 0.0, 0.0, 1.0, 100.0, 200.0),
            page_number=0,
            occurrence=1
        )

    @pytest.fixture
    def sample_normalized_bbox(self):
        """Create sample normalized bbox."""
        return NormalizedBBox(x=0.1, y=0.2, width=0.5, height=0.3)

    def test_metadata_from_asset(self, sample_asset, sample_normalized_bbox):
        """Test creating metadata from Asset."""
        metadata = PlacedObjectMetadata.from_asset(
            asset=sample_asset,
            column_id=0,
            normalized_bbox=sample_normalized_bbox,
            anchor_to="paragraph.materials.001"
        )

        assert metadata.asset_id == "img-abc12345-p0-occ1"
        assert metadata.column_id == 0
        assert metadata.normalized_bbox.x == 0.1
        assert metadata.normalized_bbox.y == 0.2
        assert metadata.anchor_to == "paragraph.materials.001"
        assert metadata.ctm == (1.0, 0.0, 0.0, 1.0, 100.0, 200.0)

    def test_metadata_without_anchor(self, sample_asset, sample_normalized_bbox):
        """Test creating metadata without anchor."""
        metadata = PlacedObjectMetadata.from_asset(
            asset=sample_asset,
            column_id=1,
            normalized_bbox=sample_normalized_bbox
        )

        assert metadata.asset_id == "img-abc12345-p0-occ1"
        assert metadata.column_id == 1
        assert metadata.anchor_to is None

    def test_metadata_direct_instantiation(self):
        """Test creating metadata directly."""
        normalized_bbox = NormalizedBBox(x=0.2, y=0.3, width=0.4, height=0.5)

        metadata = PlacedObjectMetadata(
            asset_id="vec-def67890-p1-occ2",
            column_id=2,
            normalized_bbox=normalized_bbox,
            ctm=(1.0, 0.0, 0.0, -1.0, 0.0, 0.0),
            anchor_to="paragraph.techniques.005",
            asset_type="vector",
            page_number=1,
            occurrence=2
        )

        assert metadata.asset_id == "vec-def67890-p1-occ2"
        assert metadata.column_id == 2
        assert metadata.asset_type == "vector"
        assert metadata.page_number == 1
        assert metadata.occurrence == 2


# ============================================================================
# TEST: JSON Serialization
# ============================================================================


class TestMetadataJSONSerialization:
    """Test JSON serialization of metadata."""

    @pytest.fixture
    def sample_metadata(self):
        """Create sample metadata."""
        normalized_bbox = NormalizedBBox(x=0.1, y=0.2, width=0.5, height=0.3)
        return PlacedObjectMetadata(
            asset_id="img-abc12345-p0-occ1",
            column_id=0,
            normalized_bbox=normalized_bbox,
            ctm=(1.0, 0.0, 0.0, 1.0, 100.0, 200.0),
            anchor_to="paragraph.materials.001",
            asset_type="image",
            page_number=0,
            occurrence=1
        )

    def test_to_json(self, sample_metadata):
        """Test metadata to JSON conversion."""
        json_str = sample_metadata.to_json()

        # Should be valid JSON
        data = json.loads(json_str)
        assert data["asset_id"] == "img-abc12345-p0-occ1"
        assert data["column_id"] == 0
        assert data["normalized_bbox"]["x"] == 0.1
        assert data["normalized_bbox"]["y"] == 0.2
        assert data["ctm"] == [1.0, 0.0, 0.0, 1.0, 100.0, 200.0]
        assert data["anchor_to"] == "paragraph.materials.001"

    def test_json_compact(self, sample_metadata):
        """Test that JSON is compact (< 1KB)."""
        json_str = sample_metadata.to_json()

        # Should be compact
        assert len(json_str) < 1024, f"JSON too large: {len(json_str)} bytes"

        # Should not have unnecessary whitespace
        assert '\n' not in json_str
        assert '  ' not in json_str

    def test_from_json(self, sample_metadata):
        """Test JSON to metadata conversion."""
        json_str = sample_metadata.to_json()
        restored = PlacedObjectMetadata.from_json(json_str)

        assert restored.asset_id == sample_metadata.asset_id
        assert restored.column_id == sample_metadata.column_id
        assert restored.normalized_bbox.x == sample_metadata.normalized_bbox.x
        assert restored.ctm == sample_metadata.ctm
        assert restored.anchor_to == sample_metadata.anchor_to

    def test_roundtrip_serialization(self, sample_metadata):
        """Test complete serialization roundtrip."""
        json_str = sample_metadata.to_json()
        restored = PlacedObjectMetadata.from_json(json_str)
        json_str2 = restored.to_json()

        # Should produce identical JSON
        assert json_str == json_str2

    def test_json_with_null_anchor(self):
        """Test JSON serialization with null anchor."""
        normalized_bbox = NormalizedBBox(x=0.1, y=0.2, width=0.5, height=0.3)
        metadata = PlacedObjectMetadata(
            asset_id="img-test001-p0-occ1",
            column_id=0,
            normalized_bbox=normalized_bbox,
            ctm=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
            anchor_to=None
        )

        json_str = metadata.to_json()
        data = json.loads(json_str)

        assert data["anchor_to"] is None


# ============================================================================
# TEST: NormalizedBBox Validation
# ============================================================================


class TestNormalizedBBoxValidation:
    """Test NormalizedBBox validation."""

    def test_valid_bbox(self):
        """Test valid normalized bbox."""
        bbox = NormalizedBBox(x=0.1, y=0.2, width=0.5, height=0.3)
        errors = bbox.validate()

        assert len(errors) == 0

    def test_bbox_at_boundaries(self):
        """Test bbox at 0.0 and 1.0 boundaries."""
        bbox1 = NormalizedBBox(x=0.0, y=0.0, width=1.0, height=1.0)
        assert len(bbox1.validate()) == 0

        bbox2 = NormalizedBBox(x=0.5, y=0.5, width=0.5, height=0.5)
        assert len(bbox2.validate()) == 0

    def test_invalid_x_negative(self):
        """Test invalid negative x coordinate."""
        bbox = NormalizedBBox(x=-0.1, y=0.2, width=0.5, height=0.3)
        errors = bbox.validate()

        assert len(errors) > 0
        assert any("x=-0.1 out of range" in err for err in errors)

    def test_invalid_x_exceeds_one(self):
        """Test invalid x > 1.0."""
        bbox = NormalizedBBox(x=1.5, y=0.2, width=0.5, height=0.3)
        errors = bbox.validate()

        assert len(errors) > 0
        assert any("x=1.5 out of range" in err for err in errors)

    def test_invalid_width_exceeds_bounds(self):
        """Test width that causes x + width > 1.0."""
        bbox = NormalizedBBox(x=0.7, y=0.2, width=0.5, height=0.3)
        errors = bbox.validate()

        assert len(errors) > 0
        assert any("x + width" in err and "exceeds 1.0" in err for err in errors)

    def test_invalid_height_exceeds_bounds(self):
        """Test height that causes y + height > 1.0."""
        bbox = NormalizedBBox(x=0.1, y=0.8, width=0.5, height=0.3)
        errors = bbox.validate()

        assert len(errors) > 0
        assert any("y + height" in err and "exceeds 1.0" in err for err in errors)

    def test_multiple_validation_errors(self):
        """Test bbox with multiple validation errors."""
        bbox = NormalizedBBox(x=-0.1, y=1.5, width=1.2, height=0.3)
        errors = bbox.validate()

        # Should have multiple errors
        assert len(errors) >= 2


# ============================================================================
# TEST: PlacedObjectMetadata Validation
# ============================================================================


class TestPlacedObjectMetadataValidation:
    """Test PlacedObjectMetadata validation."""

    def test_valid_metadata(self):
        """Test valid metadata."""
        normalized_bbox = NormalizedBBox(x=0.1, y=0.2, width=0.5, height=0.3)
        metadata = PlacedObjectMetadata(
            asset_id="img-abc12345-p0-occ1",
            column_id=0,
            normalized_bbox=normalized_bbox,
            ctm=(1.0, 0.0, 0.0, 1.0, 100.0, 200.0)
        )

        errors = metadata.validate()
        assert len(errors) == 0

    def test_invalid_asset_id_format(self):
        """Test invalid asset ID format."""
        normalized_bbox = NormalizedBBox(x=0.1, y=0.2, width=0.5, height=0.3)
        metadata = PlacedObjectMetadata(
            asset_id="invalid-id",
            column_id=0,
            normalized_bbox=normalized_bbox,
            ctm=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
        )

        errors = metadata.validate()
        assert len(errors) > 0
        assert any("Invalid asset_id format" in err for err in errors)

    def test_invalid_ctm_length(self):
        """Test CTM with wrong number of values."""
        normalized_bbox = NormalizedBBox(x=0.1, y=0.2, width=0.5, height=0.3)
        metadata = PlacedObjectMetadata(
            asset_id="img-abc12345-p0-occ1",
            column_id=0,
            normalized_bbox=normalized_bbox,
            ctm=(1.0, 0.0, 0.0, 1.0)  # Only 4 values instead of 6
        )

        errors = metadata.validate()
        assert len(errors) > 0
        assert any("CTM must have 6 values" in err for err in errors)

    def test_negative_column_id(self):
        """Test negative column ID."""
        normalized_bbox = NormalizedBBox(x=0.1, y=0.2, width=0.5, height=0.3)
        metadata = PlacedObjectMetadata(
            asset_id="img-abc12345-p0-occ1",
            column_id=-1,
            normalized_bbox=normalized_bbox,
            ctm=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
        )

        errors = metadata.validate()
        assert len(errors) > 0
        assert any("column_id must be >= 0" in err for err in errors)

    def test_cascading_bbox_errors(self):
        """Test that bbox validation errors cascade up."""
        invalid_bbox = NormalizedBBox(x=1.5, y=0.2, width=0.5, height=0.3)
        metadata = PlacedObjectMetadata(
            asset_id="img-abc12345-p0-occ1",
            column_id=0,
            normalized_bbox=invalid_bbox,
            ctm=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
        )

        errors = metadata.validate()
        assert len(errors) > 0
        assert any("out of range" in err or "exceeds" in err for err in errors)


# ============================================================================
# TEST: Metadata Integrity
# ============================================================================


class TestMetadataIntegrity:
    """Test metadata integrity through operations."""

    def test_metadata_immutability_after_json(self):
        """Test that deserialized metadata matches original."""
        normalized_bbox = NormalizedBBox(x=0.123456, y=0.234567, width=0.345678, height=0.456789)
        original = PlacedObjectMetadata(
            asset_id="img-test001-p0-occ1",
            column_id=0,
            normalized_bbox=normalized_bbox,
            ctm=(1.0, 0.0, 0.0, -1.0, 100.5, 200.3)
        )

        json_str = original.to_json()
        restored = PlacedObjectMetadata.from_json(json_str)

        # All fields should match
        assert restored.asset_id == original.asset_id
        assert restored.column_id == original.column_id
        assert restored.normalized_bbox.x == original.normalized_bbox.x
        assert restored.normalized_bbox.y == original.normalized_bbox.y
        assert restored.normalized_bbox.width == original.normalized_bbox.width
        assert restored.normalized_bbox.height == original.normalized_bbox.height
        assert restored.ctm == original.ctm

    def test_metadata_survives_multiple_roundtrips(self):
        """Test metadata through multiple serialize/deserialize cycles."""
        normalized_bbox = NormalizedBBox(x=0.1, y=0.2, width=0.5, height=0.3)
        original = PlacedObjectMetadata(
            asset_id="img-abc12345-p0-occ1",
            column_id=0,
            normalized_bbox=normalized_bbox,
            ctm=(1.0, 0.0, 0.0, 1.0, 100.0, 200.0)
        )

        current = original
        for _ in range(5):
            json_str = current.to_json()
            current = PlacedObjectMetadata.from_json(json_str)

        # Should still match original after 5 roundtrips
        assert current.asset_id == original.asset_id
        assert current.ctm == original.ctm

    def test_floating_point_precision(self):
        """Test floating point precision in coordinates."""
        # Use precise floating point values
        normalized_bbox = NormalizedBBox(
            x=0.123456789012345,
            y=0.234567890123456,
            width=0.345678901234567,
            height=0.456789012345678
        )

        metadata = PlacedObjectMetadata(
            asset_id="img-test001-p0-occ1",
            column_id=0,
            normalized_bbox=normalized_bbox,
            ctm=(1.0, 0.0, 0.0, 1.0, 100.123456789, 200.987654321)
        )

        json_str = metadata.to_json()
        restored = PlacedObjectMetadata.from_json(json_str)

        # Should preserve reasonable precision (within 1e-6)
        assert abs(restored.normalized_bbox.x - normalized_bbox.x) < 1e-6
        assert abs(restored.ctm[4] - metadata.ctm[4]) < 1e-6


# ============================================================================
# TEST: Edge Cases
# ============================================================================


class TestMetadataEdgeCases:
    """Test edge cases and special scenarios."""

    def test_metadata_with_identity_ctm(self):
        """Test metadata with identity transformation."""
        normalized_bbox = NormalizedBBox(x=0.0, y=0.0, width=1.0, height=1.0)
        metadata = PlacedObjectMetadata(
            asset_id="img-abcdef12-p0-occ1",
            column_id=0,
            normalized_bbox=normalized_bbox,
            ctm=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
        )

        errors = metadata.validate()
        assert len(errors) == 0

    def test_metadata_with_rotation_ctm(self):
        """Test metadata with rotated transformation."""
        import math
        angle = math.radians(45)
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)

        normalized_bbox = NormalizedBBox(x=0.1, y=0.1, width=0.8, height=0.8)
        metadata = PlacedObjectMetadata(
            asset_id="img-abcdef34-p0-occ1",
            column_id=0,
            normalized_bbox=normalized_bbox,
            ctm=(cos_a, sin_a, -sin_a, cos_a, 0.0, 0.0)
        )

        errors = metadata.validate()
        assert len(errors) == 0

    def test_metadata_with_scale_ctm(self):
        """Test metadata with scaled transformation."""
        normalized_bbox = NormalizedBBox(x=0.2, y=0.2, width=0.6, height=0.6)
        metadata = PlacedObjectMetadata(
            asset_id="img-abcdef56-p0-occ1",
            column_id=0,
            normalized_bbox=normalized_bbox,
            ctm=(2.0, 0.0, 0.0, 2.0, 0.0, 0.0)  # 2x scale
        )

        errors = metadata.validate()
        assert len(errors) == 0

    def test_very_long_anchor_block_id(self):
        """Test metadata with very long anchor block ID."""
        normalized_bbox = NormalizedBBox(x=0.1, y=0.1, width=0.5, height=0.3)
        long_anchor = "paragraph.very_long_section_name.subsection.item.detail.specific_element.001"

        metadata = PlacedObjectMetadata(
            asset_id="img-test001-p0-occ1",
            column_id=0,
            normalized_bbox=normalized_bbox,
            ctm=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
            anchor_to=long_anchor
        )

        json_str = metadata.to_json()
        restored = PlacedObjectMetadata.from_json(json_str)

        assert restored.anchor_to == long_anchor

    def test_multiple_occurrences(self):
        """Test metadata for multiple occurrences of same asset."""
        normalized_bbox = NormalizedBBox(x=0.1, y=0.1, width=0.5, height=0.3)

        metadata_occ1 = PlacedObjectMetadata(
            asset_id="img-abc12345-p0-occ1",
            column_id=0,
            normalized_bbox=normalized_bbox,
            ctm=(1.0, 0.0, 0.0, 1.0, 100.0, 200.0),
            occurrence=1
        )

        metadata_occ2 = PlacedObjectMetadata(
            asset_id="img-abc12345-p1-occ2",
            column_id=1,
            normalized_bbox=normalized_bbox,
            ctm=(1.0, 0.0, 0.0, 1.0, 150.0, 300.0),
            occurrence=2
        )

        assert metadata_occ1.occurrence == 1
        assert metadata_occ2.occurrence == 2
        assert metadata_occ1.asset_id != metadata_occ2.asset_id  # Different page/occurrence
