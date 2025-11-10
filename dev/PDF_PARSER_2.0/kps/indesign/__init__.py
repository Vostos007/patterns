"""InDesign Automation Module for KPS v2.0.

This module provides JSX scripts and Python utilities for automating
Adobe InDesign workflows in the KPS localization pipeline.

Components:
- jsx/: ExtendScript (JSX) scripts for InDesign automation
  - utils.jsx: Common utility functions
  - label_placed_objects.jsx: Label existing objects with asset IDs
  - extract_object_labels.jsx: Extract labels from document
  - place_assets_from_manifest.jsx: Automated asset placement

- Python modules:
  - jsx_runner.py: Execute JSX scripts from Python
  - placement.py: Coordinate conversion and placement calculations
  - idml_parser.py: Parse IDML structure
  - idml_modifier.py: Modify IDML with labels and anchored objects
  - idml_exporter.py: High-level IDML export workflow
  - idml_validator.py: Validate IDML structure
  - idml_utils.py: IDML utilities (zip/unzip, XML helpers)
  - anchoring.py: Anchored object system

Usage:
    from kps.indesign import JSXRunner, calculate_placement_position

    # Execute JSX script
    runner = JSXRunner()
    result = runner.label_placed_objects(doc_path, manifest_path)

    # Calculate placement coordinates
    bbox = calculate_placement_position(normalized_bbox, column, page_height)

    # IDML Export
    from kps.indesign import IDMLExporter
    exporter = IDMLExporter()
    exporter.export_with_anchored_objects(
        source_idml, output_idml, manifest, document, columns
    )

Author: KPS v2.0 InDesign Automation
Last Modified: 2025-11-06
"""

from .jsx_runner import (
    JSXResult,
    JSXRunner,
    extract_document_labels,
    label_document,
    place_document_assets,
)
from .placement import (
    CoordinateConverter,
    PlacementSpec,
    batch_calculate_placements,
    calculate_dpi,
    calculate_placement_position,
    calculate_placement_spec,
    find_asset_column,
    suggest_scaling,
    validate_placement_bounds,
)

# IDML Export (Agent 3)
from .idml_parser import IDMLParser, IDMLDocument, IDMLStory, IDMLSpread
from .idml_modifier import IDMLModifier
from .idml_exporter import IDMLExporter, quick_export
from .idml_validator import IDMLValidator, ValidationResult, quick_validate
from .anchoring import (
    AnchorType,
    AnchorPoint,
    AnchoredObjectSettings,
    calculate_anchor_settings,
    calculate_inline_anchor,
)

__all__ = [
    # JSX Runner
    "JSXRunner",
    "JSXResult",
    "label_document",
    "extract_document_labels",
    "place_document_assets",
    # Placement utilities
    "CoordinateConverter",
    "PlacementSpec",
    "calculate_placement_position",
    "calculate_placement_spec",
    "find_asset_column",
    "validate_placement_bounds",
    "calculate_dpi",
    "suggest_scaling",
    "batch_calculate_placements",
    # IDML Export
    "IDMLParser",
    "IDMLDocument",
    "IDMLStory",
    "IDMLSpread",
    "IDMLModifier",
    "IDMLExporter",
    "quick_export",
    "IDMLValidator",
    "ValidationResult",
    "quick_validate",
    "AnchorType",
    "AnchorPoint",
    "AnchoredObjectSettings",
    "calculate_anchor_settings",
    "calculate_inline_anchor",
]
