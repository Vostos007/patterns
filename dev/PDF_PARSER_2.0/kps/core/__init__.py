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

# Unified Pipeline (lazy import to avoid heavy dependencies during simple data-model usage)
def __getattr__(name):  # type: ignore[override]
    if name in {"UnifiedPipeline", "PipelineConfig", "PipelineResult", "ExtractionMethod", "MemoryType"}:
        from . import unified_pipeline

        return getattr(unified_pipeline, name)
    raise AttributeError(name)


def __dir__():  # pragma: no cover - thin wrapper
    return sorted(set(globals()) | {"UnifiedPipeline", "PipelineConfig", "PipelineResult", "ExtractionMethod", "MemoryType"})

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

__all__.extend(
    [
        "UnifiedPipeline",
        "PipelineConfig",
        "PipelineResult",
        "ExtractionMethod",
        "MemoryType",
    ]
)
