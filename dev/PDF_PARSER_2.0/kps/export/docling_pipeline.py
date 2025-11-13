"""Docling-first export pipeline with structured fallbacks."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from docling_core.types.doc.document import DoclingDocument

from .docling_renderer import (
    DoclingExportError,
    render_docx as docling_render_docx,
    render_html as docling_render_html,
    render_markdown as docling_render_markdown,
    render_pdf_from_docling,
)

logger = logging.getLogger(__name__)

FallbackBuilder = Callable[[], Tuple[Path, str]]


@dataclass
class DoclingExportResult:
    """Metadata describing how a format was rendered."""

    fmt: str
    output_path: Path
    renderer: str
    warnings: List[str]

    @property
    def fallback_used(self) -> bool:
        return self.renderer != "docling"


def _run_with_fallback(
    fmt: str,
    output_path: Path,
    primary: Callable[[], None],
    fallback_builder: Optional[FallbackBuilder],
) -> DoclingExportResult:
    warnings: List[str] = []
    try:
        primary()
        return DoclingExportResult(fmt=fmt, output_path=output_path, renderer="docling", warnings=warnings)
    except Exception as exc:
        logger.warning("Docling %s export failed: %s", fmt, exc)
        warnings.append(f"Docling {fmt.upper()} export failed: {exc}")
        if fallback_builder is None:
            raise
        fallback_path, label = fallback_builder()
        return DoclingExportResult(fmt=fmt, output_path=fallback_path, renderer=label, warnings=warnings)


def export_docx_with_fallback(
    docling_doc,
    output_path: Path,
    *,
    reference_doc: Optional[Path] = None,
    fallback_builder: Optional[FallbackBuilder] = None,
) -> DoclingExportResult:
    """Render DOCX via Docling HTML + pandoc, fallback to provided builder if needed."""

    def _primary() -> None:
        docling_render_docx(docling_doc, output_path, reference_doc)

    return _run_with_fallback("docx", output_path, _primary, fallback_builder)


def export_pdf_with_fallback(
    docling_doc,
    output_path: Path,
    *,
    css_path: Optional[Path] = None,
    fallback_builder: Optional[FallbackBuilder] = None,
) -> DoclingExportResult:
    """Render PDF via Docling HTML (WeasyPrint), fallback to provided builder."""

    def _primary() -> None:
        render_pdf_from_docling(docling_doc, output_path, css_path)

    return _run_with_fallback("pdf", output_path, _primary, fallback_builder)


def export_markdown_with_fallback(
    docling_doc,
    output_path: Path,
    *,
    fallback_builder: Optional[FallbackBuilder] = None,
) -> DoclingExportResult:
    """Render Markdown via Docling export, fallback to simple segment dump."""

    def _primary() -> None:
        docling_render_markdown(docling_doc, output_path)

    return _run_with_fallback("markdown", output_path, _primary, fallback_builder)


def export_html_with_fallback(
    docling_doc,
    output_path: Path,
    *,
    fallback_builder: Optional[FallbackBuilder] = None,
) -> DoclingExportResult:
    """Render HTML from Docling, fallback if requested."""

    def _primary() -> None:
        docling_render_html(docling_doc, output_path)

    return _run_with_fallback("html", output_path, _primary, fallback_builder)


__all__ = [
    "DoclingExportResult",
    "export_docx_with_fallback",
    "export_pdf_with_fallback",
    "export_markdown_with_fallback",
    "export_html_with_fallback",
]
