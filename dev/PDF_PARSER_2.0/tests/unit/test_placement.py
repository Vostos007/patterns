"""Unit tests for coordinate conversion and placement calculations."""

import pytest
import math
from dataclasses import dataclass
from typing import Tuple


# Mock classes (coordinate conversion utilities)
@dataclass
class NormalizedBBox:
    """Normalized bounding box (0.0-1.0 coordinate space)."""
    x: float
    y: float
    width: float
    height: float


@dataclass
class Column:
    """Column definition in PDF coordinate space."""
    column_id: int
    x_min: float  # pt
    x_max: float  # pt
    y_min: float  # pt
    y_max: float  # pt

    @property
    def width(self) -> float:
        return self.x_max - self.x_min

    @property
    def height(self) -> float:
        return self.y_max - self.y_min


@dataclass
class PlacedBBox:
    """Absolute bounding box in PDF points."""
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    def to_indesign_coords(self, page_height: float) -> 'PlacedBBox':
        """Convert PDF coords (bottom-origin) to InDesign (top-origin)."""
        return PlacedBBox(
            x0=self.x0,
            y0=page_height - self.y1,  # Flip Y
            x1=self.x1,
            y1=page_height - self.y0
        )


def calculate_placement_position(
    normalized_bbox: NormalizedBBox,
    column: Column,
    page_height: float
) -> PlacedBBox:
    """
    Convert normalized bbox to absolute PDF points.

    Args:
        normalized_bbox: Normalized coordinates (0.0-1.0)
        column: Column definition
        page_height: Page height in points

    Returns:
        Absolute bounding box in PDF points
    """
    # Calculate absolute coordinates
    x0 = column.x_min + (normalized_bbox.x * column.width)
    x1 = x0 + (normalized_bbox.width * column.width)
    y0 = column.y_min + (normalized_bbox.y * column.height)
    y1 = y0 + (normalized_bbox.height * column.height)

    return PlacedBBox(x0=x0, y0=y0, x1=x1, y1=y1)


def normalize_bbox(
    absolute_bbox: PlacedBBox,
    column: Column
) -> NormalizedBBox:
    """
    Convert absolute bbox to normalized coordinates.

    Args:
        absolute_bbox: Absolute bounding box in PDF points
        column: Column definition

    Returns:
        Normalized coordinates (0.0-1.0)
    """
    x = (absolute_bbox.x0 - column.x_min) / column.width
    y = (absolute_bbox.y0 - column.y_min) / column.height
    width = absolute_bbox.width / column.width
    height = absolute_bbox.height / column.height

    return NormalizedBBox(x=x, y=y, width=width, height=height)


def calculate_ctm(
    source_width: float,
    source_height: float,
    target_bbox: PlacedBBox,
    rotation: float = 0.0,
    flip_h: bool = False,
    flip_v: bool = False
) -> Tuple[float, float, float, float, float, float]:
    """
    Calculate transformation matrix (CTM) for placing an asset.

    Args:
        source_width: Source image width (px or pt)
        source_height: Source image height (px or pt)
        target_bbox: Target bounding box
        rotation: Rotation angle in degrees
        flip_h: Horizontal flip
        flip_v: Vertical flip

    Returns:
        CTM tuple (a, b, c, d, e, f)
    """
    # Calculate scale
    scale_x = target_bbox.width / source_width
    scale_y = target_bbox.height / source_height

    # Apply flips
    if flip_h:
        scale_x = -scale_x
    if flip_v:
        scale_y = -scale_y

    # Calculate rotation
    angle_rad = math.radians(rotation)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)

    # CTM components
    a = scale_x * cos_a
    b = scale_x * sin_a
    c = -scale_y * sin_a
    d = scale_y * cos_a
    e = target_bbox.x0
    f = target_bbox.y0

    return (a, b, c, d, e, f)


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def a4_page_size():
    """A4 page dimensions in points."""
    return {
        "width": 595.28,  # 210mm
        "height": 841.89,  # 297mm
    }


@pytest.fixture
def sample_column():
    """Standard column definition."""
    return Column(
        column_id=0,
        x_min=50.0,
        x_max=300.0,
        y_min=100.0,
        y_max=700.0
    )


@pytest.fixture
def two_column_layout():
    """Two-column layout."""
    return [
        Column(column_id=0, x_min=50.0, x_max=250.0, y_min=100.0, y_max=700.0),
        Column(column_id=1, x_min=280.0, x_max=480.0, y_min=100.0, y_max=700.0)
    ]


# ============================================================================
# TEST: Coordinate Conversion (Normalized → Absolute)
# ============================================================================


class TestCoordinateConversion:
    """Test converting normalized coordinates to absolute."""

    def test_top_left_corner(self, sample_column, a4_page_size):
        """Test placing at top-left corner."""
        normalized = NormalizedBBox(x=0.0, y=0.0, width=0.2, height=0.1)

        placed = calculate_placement_position(
            normalized,
            sample_column,
            a4_page_size["height"]
        )

        # Should be at column's top-left
        assert placed.x0 == 50.0
        assert placed.y0 == 100.0
        assert placed.width == pytest.approx(50.0, abs=0.1)  # 0.2 * 250
        assert placed.height == pytest.approx(60.0, abs=0.1)  # 0.1 * 600

    def test_center_placement(self, sample_column, a4_page_size):
        """Test placing at column center."""
        normalized = NormalizedBBox(x=0.4, y=0.4, width=0.2, height=0.2)

        placed = calculate_placement_position(
            normalized,
            sample_column,
            a4_page_size["height"]
        )

        # Should be centered in column
        expected_x0 = 50.0 + (0.4 * 250.0)  # 150.0
        expected_y0 = 100.0 + (0.4 * 600.0)  # 340.0

        assert placed.x0 == pytest.approx(expected_x0, abs=0.1)
        assert placed.y0 == pytest.approx(expected_y0, abs=0.1)

    def test_bottom_right_corner(self, sample_column, a4_page_size):
        """Test placing at bottom-right corner."""
        normalized = NormalizedBBox(x=0.8, y=0.9, width=0.2, height=0.1)

        placed = calculate_placement_position(
            normalized,
            sample_column,
            a4_page_size["height"]
        )

        # Should be at column's bottom-right
        expected_x0 = 50.0 + (0.8 * 250.0)  # 250.0
        expected_y0 = 100.0 + (0.9 * 600.0)  # 640.0

        assert placed.x0 == pytest.approx(expected_x0, abs=0.1)
        assert placed.y0 == pytest.approx(expected_y0, abs=0.1)

    def test_full_column_width(self, sample_column, a4_page_size):
        """Test placing across full column width."""
        normalized = NormalizedBBox(x=0.0, y=0.5, width=1.0, height=0.2)

        placed = calculate_placement_position(
            normalized,
            sample_column,
            a4_page_size["height"]
        )

        assert placed.x0 == 50.0
        assert placed.x1 == 300.0
        assert placed.width == 250.0


# ============================================================================
# TEST: Reverse Conversion (Absolute → Normalized)
# ============================================================================


class TestReverseConversion:
    """Test converting absolute coordinates to normalized."""

    def test_normalize_full_column(self, sample_column):
        """Test normalizing bbox that spans full column."""
        absolute = PlacedBBox(x0=50.0, y0=100.0, x1=300.0, y1=700.0)

        normalized = normalize_bbox(absolute, sample_column)

        assert normalized.x == pytest.approx(0.0, abs=0.001)
        assert normalized.y == pytest.approx(0.0, abs=0.001)
        assert normalized.width == pytest.approx(1.0, abs=0.001)
        assert normalized.height == pytest.approx(1.0, abs=0.001)

    def test_normalize_quarter_size(self, sample_column):
        """Test normalizing quarter-size bbox."""
        # 50% width, 50% height
        absolute = PlacedBBox(
            x0=50.0 + 125.0,   # Center X
            y0=100.0 + 300.0,  # Center Y
            x1=50.0 + 187.5,   # 50% width from center
            y1=100.0 + 450.0   # 50% height from center
        )

        normalized = normalize_bbox(absolute, sample_column)

        assert normalized.width == pytest.approx(0.25, abs=0.01)
        assert normalized.height == pytest.approx(0.25, abs=0.01)

    def test_normalize_offset_bbox(self, sample_column):
        """Test normalizing bbox with offset."""
        absolute = PlacedBBox(
            x0=100.0,  # 20% from left (50 + 50)
            y0=200.0,  # 16.7% from top (100 + 100)
            x1=200.0,
            y1=400.0
        )

        normalized = normalize_bbox(absolute, sample_column)

        assert normalized.x == pytest.approx(0.2, abs=0.01)
        assert normalized.y == pytest.approx(0.167, abs=0.01)


# ============================================================================
# TEST: Roundtrip Conversion
# ============================================================================


class TestRoundtripConversion:
    """Test that coordinates survive normalize → place → normalize."""

    def test_roundtrip_top_left(self, sample_column, a4_page_size):
        """Test roundtrip for top-left position."""
        original = NormalizedBBox(x=0.0, y=0.0, width=0.3, height=0.2)

        # Convert to absolute
        placed = calculate_placement_position(original, sample_column, a4_page_size["height"])

        # Convert back to normalized
        restored = normalize_bbox(placed, sample_column)

        assert restored.x == pytest.approx(original.x, abs=0.001)
        assert restored.y == pytest.approx(original.y, abs=0.001)
        assert restored.width == pytest.approx(original.width, abs=0.001)
        assert restored.height == pytest.approx(original.height, abs=0.001)

    def test_roundtrip_center(self, sample_column, a4_page_size):
        """Test roundtrip for center position."""
        original = NormalizedBBox(x=0.4, y=0.4, width=0.2, height=0.2)

        placed = calculate_placement_position(original, sample_column, a4_page_size["height"])
        restored = normalize_bbox(placed, sample_column)

        assert restored.x == pytest.approx(original.x, abs=0.001)
        assert restored.y == pytest.approx(original.y, abs=0.001)
        assert restored.width == pytest.approx(original.width, abs=0.001)
        assert restored.height == pytest.approx(original.height, abs=0.001)

    def test_roundtrip_arbitrary_position(self, sample_column, a4_page_size):
        """Test roundtrip for arbitrary position."""
        original = NormalizedBBox(x=0.123, y=0.456, width=0.234, height=0.345)

        placed = calculate_placement_position(original, sample_column, a4_page_size["height"])
        restored = normalize_bbox(placed, sample_column)

        assert restored.x == pytest.approx(original.x, abs=0.001)
        assert restored.y == pytest.approx(original.y, abs=0.001)
        assert restored.width == pytest.approx(original.width, abs=0.001)
        assert restored.height == pytest.approx(original.height, abs=0.001)


# ============================================================================
# TEST: Coordinate Accuracy (±2pt tolerance)
# ============================================================================


class TestCoordinateAccuracy:
    """Test coordinate conversion accuracy (critical requirement: ±2pt)."""

    def test_accuracy_within_2pt(self, sample_column, a4_page_size):
        """Test that roundtrip is within ±2pt tolerance."""
        original_normalized = NormalizedBBox(x=0.1, y=0.2, width=0.5, height=0.3)

        # Convert to absolute
        placed = calculate_placement_position(
            original_normalized,
            sample_column,
            a4_page_size["height"]
        )

        # Convert back
        restored_normalized = normalize_bbox(placed, sample_column)

        # Convert restored back to absolute
        placed_again = calculate_placement_position(
            restored_normalized,
            sample_column,
            a4_page_size["height"]
        )

        # Check that coordinates are within ±2pt
        assert abs(placed_again.x0 - placed.x0) < 2.0
        assert abs(placed_again.y0 - placed.y0) < 2.0
        assert abs(placed_again.x1 - placed.x1) < 2.0
        assert abs(placed_again.y1 - placed.y1) < 2.0

    def test_accuracy_multiple_roundtrips(self, sample_column, a4_page_size):
        """Test accuracy after multiple roundtrips."""
        original = NormalizedBBox(x=0.25, y=0.35, width=0.4, height=0.3)

        current_normalized = original
        for _ in range(5):
            placed = calculate_placement_position(
                current_normalized,
                sample_column,
                a4_page_size["height"]
            )
            current_normalized = normalize_bbox(placed, sample_column)

        # After 5 roundtrips, should still be close
        assert current_normalized.x == pytest.approx(original.x, abs=0.01)
        assert current_normalized.y == pytest.approx(original.y, abs=0.01)


# ============================================================================
# TEST: PDF → InDesign Coordinate Conversion
# ============================================================================


class TestPDFToInDesignConversion:
    """Test converting PDF coordinates (bottom-origin) to InDesign (top-origin)."""

    def test_pdf_to_indesign_top_left(self, a4_page_size):
        """Test converting top-left corner."""
        # In PDF: top-left is (0, page_height)
        pdf_bbox = PlacedBBox(x0=0.0, y0=700.0, x1=100.0, y1=800.0)

        indesign_bbox = pdf_bbox.to_indesign_coords(a4_page_size["height"])

        # In InDesign: top-left is (0, 0)
        assert indesign_bbox.x0 == 0.0
        assert indesign_bbox.y0 == pytest.approx(41.89, abs=0.1)  # 841.89 - 800

    def test_pdf_to_indesign_bottom_left(self, a4_page_size):
        """Test converting bottom-left corner."""
        # In PDF: bottom-left is (0, 0)
        pdf_bbox = PlacedBBox(x0=0.0, y0=0.0, x1=100.0, y1=100.0)

        indesign_bbox = pdf_bbox.to_indesign_coords(a4_page_size["height"])

        # In InDesign: bottom-left is (0, page_height - 100)
        assert indesign_bbox.x0 == 0.0
        assert indesign_bbox.y0 == pytest.approx(741.89, abs=0.1)  # 841.89 - 100

    def test_pdf_to_indesign_preserves_dimensions(self, a4_page_size):
        """Test that width/height are preserved."""
        pdf_bbox = PlacedBBox(x0=100.0, y0=200.0, x1=300.0, y1=400.0)

        indesign_bbox = pdf_bbox.to_indesign_coords(a4_page_size["height"])

        assert indesign_bbox.width == pytest.approx(200.0, abs=0.1)
        assert indesign_bbox.height == pytest.approx(200.0, abs=0.1)


# ============================================================================
# TEST: CTM Calculation
# ============================================================================


class TestCTMCalculation:
    """Test transformation matrix calculation."""

    def test_ctm_identity_no_transform(self):
        """Test CTM with no transformation (identity)."""
        ctm = calculate_ctm(
            source_width=100.0,
            source_height=100.0,
            target_bbox=PlacedBBox(x0=0.0, y0=0.0, x1=100.0, y1=100.0)
        )

        # Should be identity matrix
        assert ctm == pytest.approx((1.0, 0.0, 0.0, 1.0, 0.0, 0.0), abs=0.001)

    def test_ctm_scale_2x(self):
        """Test CTM with 2x scaling."""
        ctm = calculate_ctm(
            source_width=100.0,
            source_height=100.0,
            target_bbox=PlacedBBox(x0=0.0, y0=0.0, x1=200.0, y1=200.0)
        )

        # Should scale by 2.0
        assert ctm[0] == pytest.approx(2.0, abs=0.001)  # a
        assert ctm[3] == pytest.approx(2.0, abs=0.001)  # d

    def test_ctm_with_translation(self):
        """Test CTM with translation."""
        ctm = calculate_ctm(
            source_width=100.0,
            source_height=100.0,
            target_bbox=PlacedBBox(x0=50.0, y0=100.0, x1=150.0, y1=200.0)
        )

        # Should have translation
        assert ctm[4] == pytest.approx(50.0, abs=0.001)   # e (tx)
        assert ctm[5] == pytest.approx(100.0, abs=0.001)  # f (ty)

    def test_ctm_with_90_degree_rotation(self):
        """Test CTM with 90-degree rotation."""
        ctm = calculate_ctm(
            source_width=100.0,
            source_height=100.0,
            target_bbox=PlacedBBox(x0=0.0, y0=0.0, x1=100.0, y1=100.0),
            rotation=90.0
        )

        # 90-degree rotation matrix
        assert ctm[0] == pytest.approx(0.0, abs=0.001)   # a
        assert ctm[1] == pytest.approx(1.0, abs=0.001)   # b
        assert ctm[2] == pytest.approx(-1.0, abs=0.001)  # c
        assert ctm[3] == pytest.approx(0.0, abs=0.001)   # d

    def test_ctm_with_horizontal_flip(self):
        """Test CTM with horizontal flip."""
        ctm = calculate_ctm(
            source_width=100.0,
            source_height=100.0,
            target_bbox=PlacedBBox(x0=0.0, y0=0.0, x1=100.0, y1=100.0),
            flip_h=True
        )

        # Should have negative X scale
        assert ctm[0] == pytest.approx(-1.0, abs=0.001)  # a

    def test_ctm_with_vertical_flip(self):
        """Test CTM with vertical flip."""
        ctm = calculate_ctm(
            source_width=100.0,
            source_height=100.0,
            target_bbox=PlacedBBox(x0=0.0, y0=0.0, x1=100.0, y1=100.0),
            flip_v=True
        )

        # Should have negative Y scale
        assert ctm[3] == pytest.approx(-1.0, abs=0.001)  # d


# ============================================================================
# TEST: Multi-Column Layout
# ============================================================================


class TestMultiColumnPlacement:
    """Test placement in multi-column layouts."""

    def test_placement_in_left_column(self, two_column_layout, a4_page_size):
        """Test placing asset in left column."""
        normalized = NormalizedBBox(x=0.1, y=0.1, width=0.8, height=0.2)

        placed = calculate_placement_position(
            normalized,
            two_column_layout[0],
            a4_page_size["height"]
        )

        # Should be within left column bounds
        assert placed.x0 >= 50.0
        assert placed.x1 <= 250.0

    def test_placement_in_right_column(self, two_column_layout, a4_page_size):
        """Test placing asset in right column."""
        normalized = NormalizedBBox(x=0.1, y=0.1, width=0.8, height=0.2)

        placed = calculate_placement_position(
            normalized,
            two_column_layout[1],
            a4_page_size["height"]
        )

        # Should be within right column bounds
        assert placed.x0 >= 280.0
        assert placed.x1 <= 480.0

    def test_same_normalized_different_columns(self, two_column_layout, a4_page_size):
        """Test same normalized bbox in different columns."""
        normalized = NormalizedBBox(x=0.0, y=0.0, width=1.0, height=0.5)

        placed_left = calculate_placement_position(
            normalized,
            two_column_layout[0],
            a4_page_size["height"]
        )

        placed_right = calculate_placement_position(
            normalized,
            two_column_layout[1],
            a4_page_size["height"]
        )

        # Should have same relative position but different absolute coords
        assert placed_left.x0 != placed_right.x0
        assert placed_left.width == pytest.approx(placed_right.width, abs=0.1)


# ============================================================================
# TEST: Edge Cases
# ============================================================================


class TestPlacementEdgeCases:
    """Test edge cases and special scenarios."""

    def test_zero_size_bbox(self, sample_column, a4_page_size):
        """Test placing zero-size bbox."""
        normalized = NormalizedBBox(x=0.5, y=0.5, width=0.0, height=0.0)

        placed = calculate_placement_position(
            normalized,
            sample_column,
            a4_page_size["height"]
        )

        assert placed.width == 0.0
        assert placed.height == 0.0

    def test_very_small_bbox(self, sample_column, a4_page_size):
        """Test placing very small bbox (< 1pt)."""
        normalized = NormalizedBBox(x=0.5, y=0.5, width=0.001, height=0.001)

        placed = calculate_placement_position(
            normalized,
            sample_column,
            a4_page_size["height"]
        )

        # Should be very small but non-zero
        assert placed.width > 0.0
        assert placed.width < 1.0

    def test_aspect_ratio_preservation(self, sample_column, a4_page_size):
        """Test that aspect ratio is preserved during conversion."""
        # 16:9 aspect ratio
        normalized = NormalizedBBox(x=0.1, y=0.1, width=0.8, height=0.45)

        placed = calculate_placement_position(
            normalized,
            sample_column,
            a4_page_size["height"]
        )

        # Check aspect ratio (with tolerance for column aspect ratio)
        normalized_aspect = normalized.width / normalized.height
        placed_aspect = placed.width / placed.height

        # Aspect ratios should match
        assert placed_aspect == pytest.approx(normalized_aspect, rel=0.01)

    def test_placement_at_column_boundary(self, sample_column, a4_page_size):
        """Test placing exactly at column boundary."""
        normalized = NormalizedBBox(x=1.0, y=1.0, width=0.0, height=0.0)

        placed = calculate_placement_position(
            normalized,
            sample_column,
            a4_page_size["height"]
        )

        # Should be at bottom-right corner of column
        assert placed.x0 == pytest.approx(300.0, abs=0.1)
        assert placed.y0 == pytest.approx(700.0, abs=0.1)
