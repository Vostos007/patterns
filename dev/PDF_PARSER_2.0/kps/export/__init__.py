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
    "load_style_contract",
    "render_docx",
    "render_docx_with_contract",
    "render_pdf_via_html",
    "render_pdf_with_contract",
    "render_pdf_via_latex",
]
