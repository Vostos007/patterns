"""
Export module for DOCX/PDF rendering.

Provides:
- Docling to Markdown/HTML conversion
- Pandoc renderer for DOCX (with reference.docx styling)
- WeasyPrint renderer for PDF (with CSS Paged Media)
"""

from .docling_to_markdown import doc_to_markdown, markdown_to_html
from .docx_renderer import render_docx_inplace, build_docx_from_structure
from .html_renderer import load_style_map as load_pdf_style_map, render_html, render_pdf
from .pdf_browser import export_pdf_browser
from .docling_renderer import (
    render_docx as render_docx_from_docling,
    render_html as render_html_from_docling,
    render_markdown as render_markdown_from_docling,
    render_pdf_from_docling,
)
from .html_contract import write_html_document
from .docling_pipeline import (
    DoclingExportResult,
    export_docx_with_fallback,
    export_pdf_with_fallback,
    export_markdown_with_fallback,
    export_html_with_fallback,
)
from .pandoc_renderer import (
    load_style_contract,
    render_docx,
    render_docx_with_contract,
    render_pdf_via_html,
    render_pdf_with_contract,
    render_pdf_via_latex,
)

__all__ = [
    "doc_to_markdown",
    "markdown_to_html",
    "render_docx_inplace",
    "build_docx_from_structure",
    "render_html",
    "render_pdf",
    "load_pdf_style_map",
    "render_docx_from_docling",
    "render_html_from_docling",
    "render_markdown_from_docling",
    "render_pdf_from_docling",
    "write_html_document",
    "DoclingExportResult",
    "export_docx_with_fallback",
    "export_pdf_with_fallback",
    "export_markdown_with_fallback",
    "export_html_with_fallback",
    "export_pdf_browser",
    "load_style_contract",
    "render_docx",
    "render_docx_with_contract",
    "render_pdf_via_html",
    "render_pdf_with_contract",
    "render_pdf_via_latex",
]
