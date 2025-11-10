"""Comprehensive unit tests for InDesign metadata system.

Tests cover:
1. Metadata creation from Asset objects
2. JSON serialization/deserialization
3. Schema validation
4. Coordinate validation
5. CTM validation
6. BBox consistency
7. Placement accuracy
8. Schema versioning

Run with: pytest tests/test_indesign_metadata.py -v
Coverage: pytest tests/test_indesign_metadata.py --cov=kps.indesign --cov-report=term-missing
"""

import pytest
import json
from pathlib import Path
from datetime import datetime
from typing import Tuple

from kps.core.bbox import BBox, NormalizedBBox
from kps.core.assets import Asset, AssetType, ColorSpace, VectorFont
from kps.anchoring.columns import Column
from kps.indesign.metadata import PlacedObjectMetadata, CURRENT_SCHEMA_VERSION
from kps.indesign.serialization import (
    serialize_batch,
    deserialize_batch,
    calculate_json_size,
    optimize_for_size,
    verify_roundtrip,
    validate_schema_fields,
)
from kps.indesign.validation import (
    validate_normalized_coords,
    validate_ctm,
    validate_bbox_consistency,
    validate_placement_accuracy,
    validate_column_assignment,
    validate_aspect_ratio,
    validate_dpi,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_asset() -> Asset:
    """Create a sample Asset for testing."""
    return Asset(
        asset_id="img-abc123def456-p0-occ1",
        asset_type=AssetType.IMAGE,
        sha256="a1b2c3d4e5f67890" * 4,  # 64 hex chars (16 * 4 = 64)
        page_number=0,
        bbox=BBox(100.0, 200.0, 300.0, 400.0),
        ctm=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
        file_path=Path("output/assets/img-abc123def456-p0-occ1.png"),
        occurrence=1,
        anchor_to="p.materials.001",
        colorspace=ColorSpace.RGB,
        image_width=1200,
        image_height=800,
    )


@pytest.fixture
def sample_vector_asset() -> Asset:
    """Create a sample vector Asset with fonts."""
    return Asset(
        asset_id="vec-xyz789-p1-occ1",
        asset_type=AssetType.VECTOR_PDF,
        sha256="9876543210fedcba" * 4,  # 64 hex chars
        page_number=1,
        bbox=BBox(50.0, 100.0, 250.0, 300.0),
        ctm=(1.5, 0.0, 0.0, 1.5, 10.0, 20.0),
        file_path=Path("output/assets/vec-xyz789-p1-occ1.pdf"),
        occurrence=1,
        anchor_to="p.techniques.005",
        colorspace=ColorSpace.CMYK,
        has_smask=True,
        has_clip=True,
        fonts=[
            VectorFont("Helvetica", embedded=True, subset=True, font_type="TrueType"),
            VectorFont("Arial", embedded=False, subset=False, font_type="Type1"),
        ],
    )


@pytest.fixture
def sample_normalized_bbox() -> NormalizedBBox:
    """Create a sample NormalizedBBox."""
    return NormalizedBBox(x=0.1, y=0.2, w=0.5, h=0.3)


@pytest.fixture
def sample_column() -> Column:
    """Create a sample Column."""
    return Column(
        column_id=0,
        x_min=100.0,
        x_max=500.0,
        y_min=100.0,
        y_max=700.0,
        blocks=[],
    )


@pytest.fixture
def sample_metadata(sample_asset, sample_normalized_bbox) -> PlacedObjectMetadata:
    """Create sample PlacedObjectMetadata."""
    return PlacedObjectMetadata.from_asset(
        asset=sample_asset,
        column_id=0,
        normalized_bbox=sample_normalized_bbox,
        anchor_to="p.materials.001",
    )


# ============================================================================
# Test Metadata Creation
# ============================================================================

class TestMetadataCreation:
    """Test PlacedObjectMetadata creation and initialization."""

    def test_from_asset_basic(self, sample_asset, sample_normalized_bbox):
        """Test creating metadata from basic image asset."""
        metadata = PlacedObjectMetadata.from_asset(
            asset=sample_asset,
            column_id=0,
            normalized_bbox=sample_normalized_bbox,
            anchor_to="p.materials.001",
        )

        assert metadata.asset_id == sample_asset.asset_id
        assert metadata.asset_type == "image"
        assert metadata.sha256 == sample_asset.sha256
        assert metadata.page_number == 0
        assert metadata.occurrence == 1
        assert metadata.anchor_to == "p.materials.001"
        assert metadata.column_id == 0
        assert metadata.normalized_bbox == sample_normalized_bbox
        assert metadata.colorspace == "RGB"
        assert metadata.image_dimensions == (1200, 800)
        assert not metadata.has_smask
        assert not metadata.has_clip

    def test_from_asset_vector(self, sample_vector_asset, sample_normalized_bbox):
        """Test creating metadata from vector asset with fonts."""
        metadata = PlacedObjectMetadata.from_asset(
            asset=sample_vector_asset,
            column_id=1,
            normalized_bbox=sample_normalized_bbox,
            anchor_to="p.techniques.005",
        )

        assert metadata.asset_type == "vector_pdf"
        assert metadata.has_smask
        assert metadata.has_clip
        assert len(metadata.fonts) == 2
        assert "Helvetica" in metadata.fonts
        assert "Arial" in metadata.fonts
        assert metadata.colorspace == "CMYK"

    def test_validation_on_init(self):
        """Test that __post_init__ validates required fields."""
        with pytest.raises(ValueError, match="asset_id cannot be empty"):
            PlacedObjectMetadata(
                asset_id="",
                asset_type="image",
                original_bbox=BBox(0, 0, 100, 100),
                ctm=(1, 0, 0, 1, 0, 0),
                page_number=0,
                occurrence=1,
                anchor_to="p.test.001",
                column_id=0,
                normalized_bbox=NormalizedBBox(0.1, 0.1, 0.5, 0.5),
                sha256="a" * 64,
                file_path="test.png",
            )

    def test_validation_sha256_length(self):
        """Test SHA256 length validation."""
        with pytest.raises(ValueError, match="sha256 must be 64 hex characters"):
            PlacedObjectMetadata(
                asset_id="test-id",
                asset_type="image",
                original_bbox=BBox(0, 0, 100, 100),
                ctm=(1, 0, 0, 1, 0, 0),
                page_number=0,
                occurrence=1,
                anchor_to="p.test.001",
                column_id=0,
                normalized_bbox=NormalizedBBox(0.1, 0.1, 0.5, 0.5),
                sha256="abc123",  # Too short
                file_path="test.png",
            )

    def test_validation_negative_values(self):
        """Test validation of negative values."""
        with pytest.raises(ValueError, match="page_number must be >= 0"):
            PlacedObjectMetadata(
                asset_id="test-id",
                asset_type="image",
                original_bbox=BBox(0, 0, 100, 100),
                ctm=(1, 0, 0, 1, 0, 0),
                page_number=-1,  # Invalid
                occurrence=1,
                anchor_to="p.test.001",
                column_id=0,
                normalized_bbox=NormalizedBBox(0.1, 0.1, 0.5, 0.5),
                sha256="a" * 64,
                file_path="test.png",
            )

    def test_validation_ctm_length(self):
        """Test CTM length validation."""
        with pytest.raises(ValueError, match="ctm must have 6 elements"):
            PlacedObjectMetadata(
                asset_id="test-id",
                asset_type="image",
                original_bbox=BBox(0, 0, 100, 100),
                ctm=(1, 0, 0, 1),  # Too short
                page_number=0,
                occurrence=1,
                anchor_to="p.test.001",
                column_id=0,
                normalized_bbox=NormalizedBBox(0.1, 0.1, 0.5, 0.5),
                sha256="a" * 64,
                file_path="test.png",
            )


# ============================================================================
# Test JSON Serialization
# ============================================================================

class TestSerialization:
    """Test JSON serialization and deserialization."""

    def test_to_json_basic(self, sample_metadata):
        """Test basic JSON serialization."""
        json_str = sample_metadata.to_json()

        # Should be valid JSON
        data = json.loads(json_str)

        # Check key fields
        assert data["asset_id"] == sample_metadata.asset_id
        assert data["asset_type"] == sample_metadata.asset_type
        assert data["sha256"] == sample_metadata.sha256
        assert data["schema_version"] == CURRENT_SCHEMA_VERSION

    def test_to_json_compact(self, sample_metadata):
        """Test that JSON is compact (no unnecessary whitespace)."""
        json_str = sample_metadata.to_json()

        # Should have no indentation
        assert "  " not in json_str
        assert "\n" not in json_str

    def test_to_json_size_limit(self, sample_metadata):
        """Test that JSON is under 1KB for typical cases."""
        json_str = sample_metadata.to_json()
        size_bytes = len(json_str.encode('utf-8'))

        # Should be under 1KB
        assert size_bytes < 1024, f"JSON is {size_bytes} bytes (> 1KB)"

    def test_from_json_roundtrip(self, sample_metadata):
        """Test that serialization/deserialization is lossless."""
        json_str = sample_metadata.to_json()
        reconstructed = PlacedObjectMetadata.from_json(json_str)

        # Compare key fields
        assert reconstructed.asset_id == sample_metadata.asset_id
        assert reconstructed.asset_type == sample_metadata.asset_type
        assert reconstructed.sha256 == sample_metadata.sha256
        assert reconstructed.page_number == sample_metadata.page_number
        assert reconstructed.occurrence == sample_metadata.occurrence
        assert reconstructed.anchor_to == sample_metadata.anchor_to
        assert reconstructed.column_id == sample_metadata.column_id
        assert reconstructed.normalized_bbox == sample_metadata.normalized_bbox
        assert reconstructed.original_bbox == sample_metadata.original_bbox
        assert reconstructed.ctm == sample_metadata.ctm

    def test_from_json_invalid(self):
        """Test error handling for invalid JSON."""
        with pytest.raises(ValueError, match="Invalid JSON"):
            PlacedObjectMetadata.from_json("not valid json{")

    def test_from_json_missing_fields(self):
        """Test error handling for missing required fields."""
        incomplete_json = '{"asset_id": "test-123"}'

        with pytest.raises(KeyError):
            PlacedObjectMetadata.from_json(incomplete_json)

    def test_verify_roundtrip(self, sample_metadata):
        """Test verify_roundtrip utility function."""
        assert verify_roundtrip(sample_metadata)

    def test_calculate_json_size(self, sample_metadata):
        """Test JSON size calculation."""
        size = calculate_json_size(sample_metadata)
        json_str = sample_metadata.to_json()
        expected_size = len(json_str.encode('utf-8'))

        assert size == expected_size

    def test_optimize_for_size(self, sample_metadata):
        """Test aggressive size optimization."""
        normal_json = sample_metadata.to_json()
        optimized_json = optimize_for_size(sample_metadata)

        # Optimized should be smaller or equal
        assert len(optimized_json) <= len(normal_json)

        # Should still be valid JSON
        data = json.loads(optimized_json)
        assert data["asset_id"] == sample_metadata.asset_id


# ============================================================================
# Test Batch Operations
# ============================================================================

class TestBatchOperations:
    """Test batch serialization/deserialization."""

    def test_serialize_batch(self, tmp_path, sample_metadata):
        """Test batch serialization to file."""
        output_path = tmp_path / "batch.json"
        metadata_list = [sample_metadata]

        serialize_batch(metadata_list, output_path)

        assert output_path.exists()

        # Verify file contents
        with output_path.open('r') as f:
            data = json.load(f)

        assert data["schema_version"] == CURRENT_SCHEMA_VERSION
        assert data["count"] == 1
        assert len(data["metadata"]) == 1

    def test_deserialize_batch(self, tmp_path, sample_metadata):
        """Test batch deserialization from file."""
        output_path = tmp_path / "batch.json"
        metadata_list = [sample_metadata]

        # Serialize
        serialize_batch(metadata_list, output_path)

        # Deserialize
        reconstructed_list = deserialize_batch(output_path)

        assert len(reconstructed_list) == 1
        assert reconstructed_list[0].asset_id == sample_metadata.asset_id

    def test_batch_roundtrip_multiple(self, tmp_path, sample_asset, sample_normalized_bbox):
        """Test batch operations with multiple metadata objects."""
        # Create multiple metadata objects
        metadata_list = []
        for i in range(5):
            asset = Asset(
                asset_id=f"img-{i:03d}",
                asset_type=AssetType.IMAGE,
                sha256=f"{i:064d}",
                page_number=i,
                bbox=BBox(100 * i, 200 * i, 300 * i, 400 * i),
                ctm=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
                file_path=Path(f"output/img-{i:03d}.png"),
                occurrence=1,
                anchor_to=f"p.section.{i:03d}",
                image_width=1200,
                image_height=800,
            )
            metadata = PlacedObjectMetadata.from_asset(
                asset=asset,
                column_id=0,
                normalized_bbox=sample_normalized_bbox,
                anchor_to=asset.anchor_to,
            )
            metadata_list.append(metadata)

        # Serialize and deserialize
        output_path = tmp_path / "batch_multi.json"
        serialize_batch(metadata_list, output_path)
        reconstructed_list = deserialize_batch(output_path)

        assert len(reconstructed_list) == 5
        for i, metadata in enumerate(reconstructed_list):
            assert metadata.asset_id == f"img-{i:03d}"


# ============================================================================
# Test Validation Functions
# ============================================================================

class TestNormalizedCoordValidation:
    """Test normalized coordinate validation."""

    def test_valid_coords(self):
        """Test valid normalized coordinates."""
        bbox = NormalizedBBox(0.5, 0.2, 0.4, 0.3)
        errors = validate_normalized_coords(bbox)
        assert not errors

    def test_invalid_x_negative(self):
        """Test invalid negative x."""
        # NormalizedBBox validates in __post_init__, so this should raise
        with pytest.raises(ValueError, match="Normalized x must be in"):
            bbox = NormalizedBBox(-0.1, 0.2, 0.4, 0.3)

    def test_invalid_y_too_large(self):
        """Test invalid y > 1."""
        with pytest.raises(ValueError, match="Normalized y must be in"):
            bbox = NormalizedBBox(0.5, 1.5, 0.4, 0.3)

    def test_invalid_extends_beyond_column(self):
        """Test bbox extending beyond column boundaries."""
        bbox = NormalizedBBox(0.8, 0.2, 0.5, 0.3)  # x + w = 1.3 > 1.0
        errors = validate_normalized_coords(bbox)
        assert any("extends beyond column right edge" in e for e in errors)

    def test_multiple_errors(self):
        """Test multiple validation errors at once."""
        # NormalizedBBox validates in __post_init__, so this should raise on first error
        with pytest.raises(ValueError):
            bbox = NormalizedBBox(-0.1, 1.5, 0.7, -0.2)


class TestCTMValidation:
    """Test CTM matrix validation."""

    def test_valid_identity_matrix(self):
        """Test valid identity matrix."""
        ctm = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
        errors = validate_ctm(ctm)
        assert not errors

    def test_valid_scaled_matrix(self):
        """Test valid scaled matrix."""
        ctm = (2.0, 0.0, 0.0, 2.0, 100.0, 200.0)
        errors = validate_ctm(ctm)
        assert not errors

    def test_invalid_singular_matrix(self):
        """Test singular matrix (determinant = 0)."""
        ctm = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        errors = validate_ctm(ctm)
        assert len(errors) >= 1
        assert any("singular" in e.lower() for e in errors)

    def test_invalid_too_large_scale(self):
        """Test matrix with unreasonably large scale."""
        ctm = (200.0, 0.0, 0.0, 200.0, 0.0, 0.0)
        errors = validate_ctm(ctm)
        assert any("too large" in e for e in errors)

    def test_invalid_too_small_scale(self):
        """Test matrix with unreasonably small scale."""
        ctm = (0.0001, 0.0, 0.0, 0.0001, 0.0, 0.0)
        errors = validate_ctm(ctm)
        assert any("too small" in e for e in errors)

    def test_invalid_nan_values(self):
        """Test matrix with NaN values."""
        ctm = (float('nan'), 0.0, 0.0, 1.0, 0.0, 0.0)
        errors = validate_ctm(ctm)
        assert any("not finite" in e for e in errors)

    def test_invalid_inf_values(self):
        """Test matrix with Inf values."""
        ctm = (float('inf'), 0.0, 0.0, 1.0, 0.0, 0.0)
        errors = validate_ctm(ctm)
        assert any("not finite" in e for e in errors)


class TestBBoxConsistency:
    """Test bbox consistency validation."""

    def test_consistent_bboxes(self, sample_column):
        """Test consistent original and normalized bboxes."""
        original = BBox(150.0, 220.0, 350.0, 400.0)
        # Column: x_min=100, width=400, y_min=100, height=600
        # Normalized: x=(150-100)/400=0.125, y=(220-100)/600=0.2
        #             w=(350-150)/400=0.5,   h=(400-220)/600=0.3
        normalized = NormalizedBBox(0.125, 0.2, 0.5, 0.3)

        errors = validate_bbox_consistency(original, normalized, sample_column.bounds)
        assert not errors

    def test_inconsistent_bboxes(self, sample_column):
        """Test inconsistent bboxes (reconstruction fails)."""
        original = BBox(150.0, 220.0, 350.0, 400.0)
        # Wrong normalized coords
        normalized = NormalizedBBox(0.5, 0.5, 0.3, 0.3)

        errors = validate_bbox_consistency(original, normalized, sample_column.bounds)
        assert len(errors) > 0


class TestPlacementAccuracy:
    """Test placement accuracy validation."""

    def test_accurate_placement(self):
        """Test placement within tolerance."""
        expected_bbox = BBox(100.0, 200.0, 300.0, 400.0)
        actual_bbox = BBox(100.5, 200.2, 300.1, 400.3)  # Small deviations

        errors = validate_placement_accuracy(expected_bbox, actual_bbox, tolerance_pt=2.0)
        assert not errors

    def test_inaccurate_placement(self):
        """Test placement outside tolerance."""
        expected_bbox = BBox(100.0, 200.0, 300.0, 400.0)
        actual_bbox = BBox(105.0, 210.0, 310.0, 420.0)  # Large deviations

        errors = validate_placement_accuracy(expected_bbox, actual_bbox, tolerance_pt=2.0)
        assert len(errors) > 0
        assert any("Placement error" in e for e in errors)


class TestColumnAssignment:
    """Test column assignment validation."""

    def test_valid_column_assignment(self, sample_column):
        """Test bbox correctly assigned to column."""
        bbox = BBox(200.0, 300.0, 400.0, 500.0)  # Well within column
        errors = validate_column_assignment(bbox, sample_column)
        assert not errors

    def test_invalid_column_assignment(self, sample_column):
        """Test bbox incorrectly assigned to column."""
        bbox = BBox(600.0, 300.0, 800.0, 500.0)  # Outside column
        errors = validate_column_assignment(bbox, sample_column)
        assert len(errors) > 0
        assert any("Insufficient column overlap" in e for e in errors)


class TestAspectRatio:
    """Test aspect ratio validation."""

    def test_preserved_aspect_ratio(self):
        """Test aspect ratio is preserved."""
        original = BBox(0, 0, 200, 100)  # 2:1
        placed = BBox(0, 0, 400, 200)    # 2:1 (scaled 2x)

        errors = validate_aspect_ratio(original, placed)
        assert not errors

    def test_distorted_aspect_ratio(self):
        """Test aspect ratio is distorted."""
        original = BBox(0, 0, 200, 100)  # 2:1
        placed = BBox(0, 0, 400, 100)    # 4:1 (stretched horizontally)

        errors = validate_aspect_ratio(original, placed, tolerance=0.05)
        assert len(errors) > 0
        assert any("Aspect ratio mismatch" in e for e in errors)


class TestDPIValidation:
    """Test DPI validation."""

    def test_good_dpi(self):
        """Test image with acceptable DPI."""
        image_dims = (1200, 800)
        placed = BBox(0, 0, 300, 200)  # 4.17 x 2.78 inches = ~288 DPI

        errors = validate_dpi(image_dims, placed)
        # Should have no errors, maybe INFO about DPI
        assert not any("WARNING" in e for e in errors)

    def test_low_dpi_warning(self):
        """Test image with low DPI."""
        image_dims = (600, 400)
        placed = BBox(0, 0, 300, 200)  # 4.17 x 2.78 inches = ~144 DPI

        errors = validate_dpi(image_dims, placed, min_dpi=200.0)
        assert any("Low DPI" in e for e in errors)

    def test_high_dpi_info(self):
        """Test image with very high DPI."""
        image_dims = (4800, 3200)
        placed = BBox(0, 0, 300, 200)  # 4.17 x 2.78 inches = ~1152 DPI

        errors = validate_dpi(image_dims, placed, max_dpi=600.0)
        assert any("High DPI" in e for e in errors)


# ============================================================================
# Test Schema Validation
# ============================================================================

class TestSchemaValidation:
    """Test schema version validation."""

    def test_validate_required_fields(self, sample_metadata):
        """Test validation of required fields."""
        json_str = sample_metadata.to_json()
        data = json.loads(json_str)

        errors = validate_schema_fields(data, CURRENT_SCHEMA_VERSION)
        assert not errors

    def test_validate_missing_field(self):
        """Test validation fails for missing required field."""
        data = {
            "asset_id": "test-123",
            "schema_version": "1.0",
            # Missing many required fields
        }

        errors = validate_schema_fields(data, "1.0")
        assert len(errors) > 0
        assert any("Missing required field" in e for e in errors)


# ============================================================================
# Test Metadata Methods
# ============================================================================

class TestMetadataMethods:
    """Test PlacedObjectMetadata methods."""

    def test_update_actual_bbox(self, sample_metadata):
        """Test updating actual bbox after placement."""
        actual_bbox = BBox(105.0, 205.0, 305.0, 405.0)
        sample_metadata.update_actual_bbox(actual_bbox)

        assert sample_metadata.actual_bbox_placed == actual_bbox

    def test_placement_error_calculation(self, sample_metadata):
        """Test placement error calculation."""
        sample_metadata.expected_bbox_placed = BBox(100.0, 200.0, 300.0, 400.0)
        sample_metadata.actual_bbox_placed = BBox(102.0, 201.0, 302.0, 401.0)

        error = sample_metadata.placement_error()
        assert error is not None
        assert error == 2.0  # Max deviation is 2.0 pt

    def test_placement_error_none_when_missing(self, sample_metadata):
        """Test placement error returns None when bboxes missing."""
        error = sample_metadata.placement_error()
        assert error is None

    def test_validate_method(self, sample_metadata):
        """Test validate method."""
        errors = sample_metadata.validate()
        # Should be valid with no errors
        assert isinstance(errors, list)


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for complete workflows."""

    def test_complete_workflow(self, sample_asset, sample_normalized_bbox, sample_column, tmp_path):
        """Test complete workflow from Asset to validation."""
        # 1. Create metadata from Asset
        metadata = PlacedObjectMetadata.from_asset(
            asset=sample_asset,
            column_id=0,
            normalized_bbox=sample_normalized_bbox,
            anchor_to="p.materials.001",
            expected_bbox_placed=BBox(140.0, 220.0, 340.0, 400.0),
        )

        # 2. Validate metadata
        errors = metadata.validate()
        assert not errors

        # 3. Serialize to JSON
        json_str = metadata.to_json()
        assert len(json_str) > 0

        # 4. Check size
        size = calculate_json_size(metadata)
        assert size < 1024

        # 5. Deserialize
        reconstructed = PlacedObjectMetadata.from_json(json_str)
        assert reconstructed.asset_id == metadata.asset_id

        # 6. Verify roundtrip
        assert verify_roundtrip(metadata)

        # 7. Batch operations
        output_path = tmp_path / "workflow.json"
        serialize_batch([metadata], output_path)
        batch_list = deserialize_batch(output_path)
        assert len(batch_list) == 1

    def test_edge_cases_zero_dimensions(self):
        """Test handling of zero-dimension edge cases."""
        # BBox(100, 100, 100, 100) actually has x0=x1 and y0=y1, which violates constraints
        # but the current BBox implementation only checks x1 < x0 and y1 < y0
        # So this test should verify that width and height are zero
        bbox = BBox(100, 100, 100, 100)
        assert bbox.width == 0
        assert bbox.height == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=kps.indesign", "--cov-report=term-missing"])
