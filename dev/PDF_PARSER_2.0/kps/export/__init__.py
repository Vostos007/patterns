"""
Export module for DOCX/PDF rendering.

Provides:
- Docling to Markdown/HTML conversion
- Pandoc renderer for DOCX (with reference.docx styling)
- WeasyPrint renderer for PDF (with CSS Paged Media)
"""

from .docling_to_markdown import doc_to_markdown, markdown_to_html
from .pandoc_renderer import (
    render_docx,
    render_pdf_via_html,
    render_pdf_via_latex,
)

__all__ = [
    "doc_to_markdown",
    "markdown_to_html",
    "render_docx",
    "render_pdf_via_html",
    "render_pdf_via_latex",
]
