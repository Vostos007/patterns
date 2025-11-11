"""Placeholder PyMuPDF extractor implementation.

The original code base contained an enormous, incomplete implementation that did
not even parse.  Re-implementing the full feature set is beyond the scope of
this refactor, but the pipeline at least needs a well-defined surface area so
other modules can import it without crashing.  The minimal façade below captures
configuration and emits a clear error explaining that the heavy lifting still
needs to be provided.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kps.core.assets import AssetLedger


@dataclass(slots=True)
class PyMuPDFExtractorConfig:
    vector_dpi: int = 300
    image_format: str = "png"
    extract_images: bool = True
    extract_vectors: bool = True
    extract_tables: bool = True


class PyMuPDFExtractor:
    """Skeleton extractor used until the production implementation lands."""

    def __init__(self, *, config: PyMuPDFExtractorConfig | None = None, output_dir: Path | None = None) -> None:
        self.config = config or PyMuPDFExtractorConfig()
        self.output_dir = Path(output_dir) if output_dir else None

    def extract_assets(self, pdf_path: Path) -> AssetLedger:  # pragma: no cover - explicit failure path
        raise NotImplementedError(
            "The PyMuPDF asset extractor is not implemented in this refactor. "
            "A future iteration should provide a faithful port of the production "
            "logic before enabling these tests."
        )


__all__ = ["PyMuPDFExtractor", "PyMuPDFExtractorConfig"]

