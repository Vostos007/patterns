"""HTML/PDF rendering helpers driven by Docling structure and style map."""

from __future__ import annotations

import html
import logging
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from weasyprint import CSS, HTML

from kps.core.document import BlockType, KPSDocument

logger = logging.getLogger(__name__)


def render_html(document: KPSDocument) -> str:
    """Serialize a translated KPSDocument into semantic HTML."""

    parts: List[str] = ["<!DOCTYPE html>", "<html>", "<head>", '<meta charset="utf-8" />', "</head>", "<body>"]

    for section in document.sections:
        parts.append(
            f"<section class=\"section-{section.section_type.value}\">"
        )
        if section.title:
            parts.append(f"<h2>{html.escape(section.title)}</h2>")
        for block in section.blocks:
            parts.append(_render_block(block.block_type, block.content))
        parts.append("</section>")

    parts.extend(["</body>", "</html>"])
    return "\n".join(parts)


def _render_block(block_type: BlockType, content: str) -> str:
    safe = html.escape(content or "")
    if block_type == BlockType.HEADING:
        return f"<h3>{safe}</h3>"
    if block_type == BlockType.LIST:
        items = [f"<li>{html.escape(line.strip())}</li>" for line in safe.splitlines() if line.strip()]
        if not items:
            return "<ul></ul>"
        return "<ul>" + "".join(items) + "</ul>"
    if block_type == BlockType.TABLE:
        rows = [line.split("\t") for line in safe.splitlines()]
        table_rows = []
        for row in rows:
            cells = "".join(f"<td>{cell}</td>" for cell in row)
            table_rows.append(f"<tr>{cells}</tr>")
        return "<table>" + "".join(table_rows) + "</table>"
    if block_type == BlockType.FIGURE:
        return f"<figure><figcaption>{safe}</figcaption></figure>"
    return f"<p>{safe.replace('\n', '<br />')}</p>"


def render_pdf(html_content: str, css_path: Optional[Path], output_path: Path) -> Path:
    """Render HTML + CSS to PDF via WeasyPrint."""

    stylesheets = [CSS(filename=str(css_path))] if css_path and css_path.exists() else []
    HTML(string=html_content).write_pdf(str(output_path), stylesheets=stylesheets)
    return output_path


def load_style_map(path: Path) -> Dict:
    if not path.exists():
        raise FileNotFoundError(f"Style map not found: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))
