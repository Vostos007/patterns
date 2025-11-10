"""Bounding box types for KPS."""

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class BBox:
    """
    Bounding box in PDF points (72 dpi).

    Coordinates are in PDF coordinate system:
    - Origin (0, 0) at bottom-left
    - x increases rightward
    - y increases upward
    """

    x0: float
    y0: float
    x1: float
    y1: float

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

    def __post_init__(self) -> None:
        """Validate bbox coordinates."""
        if self.x1 < self.x0:
            raise ValueError(f"Invalid bbox: x1 ({self.x1}) < x0 ({self.x0})")
        if self.y1 < self.y0:
            raise ValueError(f"Invalid bbox: y1 ({self.y1}) < y0 ({self.y0})")


@dataclass(frozen=True)
class NormalizedBBox:
    """
    Bounding box in column-relative coordinates (0-1).

    Used for geometry comparison independent of page/column size.
    """

    x: float  # 0-1, relative to column left edge
    y: float  # 0-1, relative to column top edge
    w: float  # 0-1, relative to column width
    h: float  # 0-1, relative to column height

    def __post_init__(self) -> None:
        """Validate normalized coordinates."""
        for name, value in [("x", self.x), ("y", self.y), ("w", self.w), ("h", self.h)]:
            if not 0 <= value <= 1:
                raise ValueError(f"Normalized {name} must be in [0, 1], got {value}")
