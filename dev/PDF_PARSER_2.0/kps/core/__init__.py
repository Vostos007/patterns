"""
KPS Core - Data models and Unified Pipeline.

RECOMMENDED: Use UnifiedPipeline for end-to-end document processing.
"""

# Data models
from .assets import Asset, AssetLedger, AssetType, ColorSpace, VectorFont
from .bbox import BBox, NormalizedBBox
from .document import (
    BlockType,
    ContentBlock,
    DocumentMetadata,
    KPSDocument,
    Section,
    SectionType,
)

# Unified Pipeline
try:
    from .unified_pipeline import (
        ExtractionMethod,
        MemoryType,
        PipelineConfig,
        PipelineResult,
        UnifiedPipeline,
    )

    PIPELINE_AVAILABLE = True
except ImportError:
    PIPELINE_AVAILABLE = False

__all__ = [
    # Assets
    "Asset",
    "AssetLedger",
    "AssetType",
    "ColorSpace",
    "VectorFont",
    # BBox
    "BBox",
    "NormalizedBBox",
    # Document
    "BlockType",
    "ContentBlock",
    "DocumentMetadata",
    "KPSDocument",
    "Section",
    "SectionType",
]

# Add pipeline if available
if PIPELINE_AVAILABLE:
    __all__.extend(
        [
            "UnifiedPipeline",
            "PipelineConfig",
            "PipelineResult",
            "ExtractionMethod",
            "MemoryType",
        ]
    )
