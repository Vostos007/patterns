"""IDML anchored object system.

This module implements the anchored object system for IDML export,
converting KPS normalized coordinates to InDesign anchored object settings.

Anchored objects in InDesign:
    - Inline: Flows with text like a character
    - Custom: Positioned relative to text frame with offsets

References:
    - InDesign Scripting Guide: AnchoredObjectSettings
    - IDML Cookbook: Anchored Object chapter
"""

from dataclasses import dataclass
from enum import Enum
from typing import Tuple

from ..core.bbox import BBox, NormalizedBBox
from ..anchoring.columns import Column


class AnchorType(Enum):
    """InDesign anchor types."""

    INLINE = "inline"  # Inline with text, flows with text
    CUSTOM = "custom"  # Custom position relative to text frame


class AnchorPoint(Enum):
    """InDesign anchor point positions (9-point system)."""

    TOP_LEFT = "TopLeftAnchor"
    TOP_CENTER = "TopCenterAnchor"
    TOP_RIGHT = "TopRightAnchor"
    CENTER_LEFT = "CenterLeftAnchor"
    CENTER = "CenterAnchor"
    CENTER_RIGHT = "CenterRightAnchor"
    BOTTOM_LEFT = "BottomLeftAnchor"
    BOTTOM_CENTER = "BottomCenterAnchor"
    BOTTOM_RIGHT = "BottomRightAnchor"


class HorizontalAlignment(Enum):
    """Horizontal alignment for anchored objects."""

    LEFT_ALIGN = "LeftAlign"
    CENTER_ALIGN = "CenterAlign"
    RIGHT_ALIGN = "RightAlign"
    TEXT_ALIGN = "TextAlign"


class HorizontalReferencePoint(Enum):
    """Horizontal reference point for positioning."""

    TEXT_FRAME = "TextFrame"
    COLUMN_EDGE = "ColumnEdge"
    PAGE_EDGE = "PageEdge"
    PAGE_MARGINS = "PageMargins"
    ANCHOR_LOCATION = "AnchorLocation"


class VerticalReferencePoint(Enum):
    """Vertical reference point for positioning."""

    LINE_BASELINE = "LineBaseline"
    LINE_XHEIGHT = "LineXHeight"
    TOP_OF_FRAME = "TopOfFrame"
    BOTTOM_OF_FRAME = "BottomOfFrame"
    TOP_OF_PAGE = "TopOfPage"
    BOTTOM_OF_PAGE = "BottomOfPage"


class SpaceBeforeAfter(Enum):
    """How anchored object affects text spacing."""

    NONE = "None"
    HEIGHT = "Height"
    BOUNDING_BOX = "BoundingBox"


class AnchoredPosition(Enum):
    """Position of anchored object relative to text."""

    ANCHORED = "Anchored"
    ABOVE_LINE = "AboveLine"
    INLINE_POSITION = "InlinePosition"


@dataclass
class AnchoredObjectSettings:
    """
    InDesign AnchoredObjectSettings representation.

    Maps to IDML XML attributes for anchored objects.
    These settings control how graphics are positioned relative to text.

    Attributes:
        anchor_point: Point on object to use as anchor
        anchored_position: Position type (inline, above line, anchored)
        horizontal_alignment: Horizontal alignment
        horizontal_reference_point: What to align horizontally to
        vertical_reference_point: What to align vertically to
        anchor_x_offset: Horizontal offset in points
        anchor_y_offset: Vertical offset in points
        space_before: Space before object
        space_after: Space after object
        anchor_space_above: Space above in points
        pin_position: Whether to pin position (prevent reflow)
        prevent_manual_positioning: Lock object position
    """

    anchor_point: AnchorPoint = AnchorPoint.TOP_LEFT
    anchored_position: AnchoredPosition = AnchoredPosition.ANCHORED
    horizontal_alignment: HorizontalAlignment = HorizontalAlignment.LEFT_ALIGN
    horizontal_reference_point: HorizontalReferencePoint = (
        HorizontalReferencePoint.COLUMN_EDGE
    )
    vertical_reference_point: VerticalReferencePoint = (
        VerticalReferencePoint.LINE_BASELINE
    )
    anchor_x_offset: float = 0.0
    anchor_y_offset: float = 0.0
    space_before: SpaceBeforeAfter = SpaceBeforeAfter.NONE
    space_after: SpaceBeforeAfter = SpaceBeforeAfter.NONE
    anchor_space_above: float = 0.0
    pin_position: bool = False
    prevent_manual_positioning: bool = False

    def to_idml_attributes(self) -> dict:
        """
        Convert to IDML XML attributes.

        Returns:
            Dictionary of attribute name -> value for IDML XML

        Example:
            >>> settings = AnchoredObjectSettings(
            ...     anchor_point=AnchorPoint.TOP_LEFT,
            ...     anchor_x_offset=10.0
            ... )
            >>> attrs = settings.to_idml_attributes()
            >>> print(attrs["AnchorPoint"])
            'TopLeftAnchor'
        """
        return {
            "AnchorPoint": self.anchor_point.value,
            "AnchoredPosition": self.anchored_position.value,
            "HorizontalAlignment": self.horizontal_alignment.value,
            "HorizontalReferencePoint": self.horizontal_reference_point.value,
            "VerticalReferencePoint": self.vertical_reference_point.value,
            "AnchorXOffset": str(self.anchor_x_offset),
            "AnchorYOffset": str(self.anchor_y_offset),
            "SpaceBefore": self.space_before.value,
            "SpaceAfter": self.space_after.value,
            "AnchorSpaceAbove": str(self.anchor_space_above),
            "PinPosition": str(self.pin_position).lower(),
            "PreventManualPositioning": str(self.prevent_manual_positioning).lower(),
        }


def calculate_anchor_settings(
    asset_bbox: BBox, column: Column, inline: bool = False
) -> AnchoredObjectSettings:
    """
    Calculate IDML anchor settings from asset bbox and column.

    This function determines the optimal anchoring configuration based on
    the asset's position within its column.

    Strategy:
        - Inline mode: Simple inline anchoring (flows with text)
        - Custom mode:
            - Horizontal: Align to column edge based on position
            - Vertical: Offset from baseline
            - Calculate offsets from asset position

    Args:
        asset_bbox: Asset bounding box in PDF points
        column: Column containing the asset
        inline: If True, create inline anchor; else custom positioned

    Returns:
        AnchoredObjectSettings configured for this asset

    Example:
        >>> asset = BBox(100, 200, 250, 350)  # x0, y0, x1, y1
        >>> column = Column(0, 80, 300, 100, 800, [])
        >>> settings = calculate_anchor_settings(asset, column)
        >>> print(settings.horizontal_alignment)
        HorizontalAlignment.LEFT_ALIGN
    """
    if inline:
        # Simple inline anchor - no custom positioning
        return AnchoredObjectSettings(
            anchor_point=AnchorPoint.TOP_LEFT,
            anchored_position=AnchoredPosition.INLINE_POSITION,
            horizontal_alignment=HorizontalAlignment.LEFT_ALIGN,
            horizontal_reference_point=HorizontalReferencePoint.ANCHOR_LOCATION,
            vertical_reference_point=VerticalReferencePoint.LINE_BASELINE,
            anchor_x_offset=0.0,
            anchor_y_offset=0.0,
        )

    # Custom positioning based on asset location within column
    return _calculate_custom_anchor(asset_bbox, column)


def _calculate_custom_anchor(asset_bbox: BBox, column: Column) -> AnchoredObjectSettings:
    """
    Calculate custom anchor settings based on asset position in column.

    Determines:
        1. Horizontal alignment (left/center/right) based on position
        2. Horizontal offset from column edge
        3. Vertical offset from baseline

    Args:
        asset_bbox: Asset bounding box
        column: Column containing asset

    Returns:
        AnchoredObjectSettings with custom positioning
    """
    # Calculate asset position relative to column
    asset_center_x = (asset_bbox.x0 + asset_bbox.x1) / 2
    column_width = column.width

    # Relative position in column (0 = left, 0.5 = center, 1 = right)
    relative_x = (asset_center_x - column.x_min) / column_width if column_width > 0 else 0.5

    # Determine horizontal alignment based on position
    if relative_x < 0.33:
        h_align = HorizontalAlignment.LEFT_ALIGN
        h_ref = HorizontalReferencePoint.COLUMN_EDGE
        # Offset from left column edge
        x_offset = asset_bbox.x0 - column.x_min
    elif relative_x > 0.67:
        h_align = HorizontalAlignment.RIGHT_ALIGN
        h_ref = HorizontalReferencePoint.COLUMN_EDGE
        # Offset from right column edge (negative)
        x_offset = asset_bbox.x1 - column.x_max
    else:
        h_align = HorizontalAlignment.CENTER_ALIGN
        h_ref = HorizontalReferencePoint.COLUMN_EDGE
        # Offset from center
        x_offset = asset_center_x - column.center_x

    # Vertical positioning: offset from baseline
    # Use top of asset as reference
    y_offset = -(asset_bbox.y1 - column.y_min)  # Negative = above baseline

    return AnchoredObjectSettings(
        anchor_point=AnchorPoint.TOP_LEFT,
        anchored_position=AnchoredPosition.ANCHORED,
        horizontal_alignment=h_align,
        horizontal_reference_point=h_ref,
        vertical_reference_point=VerticalReferencePoint.LINE_BASELINE,
        anchor_x_offset=x_offset,
        anchor_y_offset=y_offset,
        pin_position=True,  # Prevent reflow
    )


def calculate_inline_anchor() -> AnchoredObjectSettings:
    """
    Create simple inline anchor settings.

    Inline anchors flow with text like a character, with no custom positioning.

    Returns:
        AnchoredObjectSettings for inline anchoring

    Example:
        >>> settings = calculate_inline_anchor()
        >>> assert settings.anchored_position == AnchoredPosition.INLINE_POSITION
    """
    return AnchoredObjectSettings(
        anchor_point=AnchorPoint.TOP_LEFT,
        anchored_position=AnchoredPosition.INLINE_POSITION,
        horizontal_alignment=HorizontalAlignment.LEFT_ALIGN,
        horizontal_reference_point=HorizontalReferencePoint.ANCHOR_LOCATION,
        vertical_reference_point=VerticalReferencePoint.LINE_BASELINE,
        anchor_x_offset=0.0,
        anchor_y_offset=0.0,
    )


def calculate_above_line_anchor(x_offset: float = 0.0) -> AnchoredObjectSettings:
    """
    Create above-line anchor settings.

    Above-line anchors sit above the text line, useful for callouts or notes.

    Args:
        x_offset: Horizontal offset from anchor position (in points)

    Returns:
        AnchoredObjectSettings for above-line anchoring
    """
    return AnchoredObjectSettings(
        anchor_point=AnchorPoint.BOTTOM_LEFT,
        anchored_position=AnchoredPosition.ABOVE_LINE,
        horizontal_alignment=HorizontalAlignment.LEFT_ALIGN,
        horizontal_reference_point=HorizontalReferencePoint.ANCHOR_LOCATION,
        vertical_reference_point=VerticalReferencePoint.LINE_XHEIGHT,
        anchor_x_offset=x_offset,
        anchor_y_offset=0.0,
        anchor_space_above=12.0,  # Space above line
    )


def normalize_bbox_to_column(bbox: BBox, column: Column) -> NormalizedBBox:
    """
    Convert absolute bbox to normalized coordinates relative to column.

    This is useful for geometry-independent asset comparison.

    Args:
        bbox: Absolute bounding box in PDF points
        column: Column to normalize against

    Returns:
        NormalizedBBox with coordinates in [0, 1] range

    Example:
        >>> bbox = BBox(100, 200, 200, 300)
        >>> column = Column(0, 50, 250, 100, 800, [])
        >>> normalized = normalize_bbox_to_column(bbox, column)
        >>> assert 0 <= normalized.x <= 1
        >>> assert 0 <= normalized.w <= 1
    """
    column_width = column.width
    column_height = column.height

    if column_width == 0 or column_height == 0:
        raise ValueError("Column has zero width or height")

    # Normalize x and y relative to column top-left
    x = (bbox.x0 - column.x_min) / column_width
    y = (bbox.y0 - column.y_min) / column_height

    # Normalize width and height
    w = bbox.width / column_width
    h = bbox.height / column_height

    return NormalizedBBox(x=x, y=y, w=w, h=h)


def denormalize_bbox_from_column(normalized: NormalizedBBox, column: Column) -> BBox:
    """
    Convert normalized coordinates back to absolute bbox.

    Inverse of normalize_bbox_to_column().

    Args:
        normalized: Normalized coordinates [0, 1]
        column: Column to denormalize against

    Returns:
        Absolute BBox in PDF points

    Example:
        >>> normalized = NormalizedBBox(0.25, 0.5, 0.5, 0.25)
        >>> column = Column(0, 50, 250, 100, 800, [])
        >>> bbox = denormalize_bbox_from_column(normalized, column)
        >>> assert bbox.x0 >= column.x_min
        >>> assert bbox.x1 <= column.x_max
    """
    column_width = column.width
    column_height = column.height

    x0 = column.x_min + (normalized.x * column_width)
    y0 = column.y_min + (normalized.y * column_height)
    x1 = x0 + (normalized.w * column_width)
    y1 = y0 + (normalized.h * column_height)

    return BBox(x0=x0, y0=y0, x1=x1, y1=y1)


def get_anchor_marker_text(asset_id: str) -> str:
    """
    Generate marker text for anchor point insertion.

    This marker is inserted into the Story XML at the anchor location.
    It's a zero-width character that serves as the anchor point.

    Args:
        asset_id: Asset identifier

    Returns:
        Marker text for insertion

    Example:
        >>> marker = get_anchor_marker_text("img-abc123-p0-occ1")
        >>> print(repr(marker))
        '[ANCHOR:img-abc123-p0-occ1]'
    """
    return f"[ANCHOR:{asset_id}]"


def create_inline_anchor_xml_structure() -> dict:
    """
    Create XML structure template for inline anchored object.

    Returns:
        Dictionary with element names and attributes for inline anchor

    Example:
        >>> structure = create_inline_anchor_xml_structure()
        >>> print(structure["Rectangle"]["AnchoredObjectSettings"])
    """
    return {
        "CharacterStyleRange": {
            "AppliedCharacterStyle": "CharacterStyle/$ID/[No character style]",
        },
        "Rectangle": {
            "AnchoredObjectSettings": {
                "AnchoredPosition": "InlinePosition",
                "AnchorPoint": "TopLeftAnchor",
            },
        },
    }
