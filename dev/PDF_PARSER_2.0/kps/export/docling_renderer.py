"""Rendering helpers that emit artifacts directly from a DoclingDocument."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from docling_core.types.doc.document import DoclingDocument

from .html_renderer import render_pdf


def render_markdown(docling_doc: DoclingDocument, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(docling_doc.export_to_markdown(), encoding="utf-8")
    return output_path


def render_html(docling_doc: DoclingDocument, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(docling_doc.export_to_html(), encoding="utf-8")
    return output_path


def render_docx(
    docling_doc: DoclingDocument,
    output_path: Path,
    reference_doc: Optional[Path] = None,
) -> Path:
    """Convert Docling HTML output into DOCX via pandoc."""

    html_content = docling_doc.export_to_html()

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as tmp_html:
        tmp_html.write(html_content)
        tmp_html_path = Path(tmp_html.name)

    try:
        cmd = [
            "pandoc",
            str(tmp_html_path),
            "-f",
            "html",
            "-t",
            "docx",
            "-o",
            str(output_path),
        ]
        if reference_doc:
            cmd.insert(-1, f"--reference-doc={reference_doc}")
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except FileNotFoundError as exc:
            raise RuntimeError(
                "pandoc is required for DOCX export. Install it from https://pandoc.org/installing.html"
            ) from exc
        except subprocess.CalledProcessError as exc:  # type: ignore[attr-defined]
            stderr = exc.stderr.decode("utf-8", errors="ignore") if exc.stderr else ""
            raise RuntimeError(f"pandoc failed: {stderr}") from exc
    finally:
        tmp_html_path.unlink(missing_ok=True)

    return output_path


def render_pdf_from_docling(
    docling_doc: DoclingDocument,
    output_path: Path,
    css_path: Optional[Path] = None,
) -> Path:
    html_content = docling_doc.export_to_html()
    return render_pdf(html_content, css_path, output_path)


__all__ = [
    "render_markdown",
    "render_html",
    "render_docx",
    "render_pdf_from_docling",
]
