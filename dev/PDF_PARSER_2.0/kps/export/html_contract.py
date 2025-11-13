"""Helpers for rendering Docling documents into styled HTML."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from docling_core.types.doc.document import DoclingDocument


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang=\"en\">
<head>
<meta charset=\"utf-8\" />
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
<style>
{css}
</style>
</head>
<body>
{body}
</body>
</html>
"""


def build_html_document(docling_doc: DoclingDocument, css_text: Optional[str] = None) -> str:
    """Return full HTML document preserving Docling structure."""

    fragment = docling_doc.export_to_html()
    css = css_text or "body { font-family: 'Helvetica Neue', Arial, sans-serif; }"
    return _HTML_TEMPLATE.format(css=css, body=fragment)


def write_html_document(
    docling_doc: DoclingDocument,
    output_path: Path,
    css_text: Optional[str] = None,
) -> Path:
    """Write Docling HTML with embedded CSS to disk."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    html_text = build_html_document(docling_doc, css_text=css_text)
    output_path.write_text(html_text, encoding="utf-8")
    return output_path


__all__ = ["build_html_document", "write_html_document"]
