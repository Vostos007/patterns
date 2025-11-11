"""DOCX export helpers for KPS pipeline."""

from __future__ import annotations

import logging
from html import unescape
from pathlib import Path
from typing import Iterable, List, Optional

from docx import Document
from docx.document import Document as DocxDocument
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import _Cell, Table
from docx.text.paragraph import Paragraph

from kps.core.document import BlockType, KPSDocument

logger = logging.getLogger(__name__)


def render_docx_inplace(
    original_docx: Path,
    original_doc: KPSDocument,
    translated_doc: KPSDocument,
    output_path: Path,
) -> Path:
    """Render translated DOCX by replacing text inside the original template."""

    document = Document(str(original_docx))
    paragraphs = list(_iter_paragraphs(document))

    original_texts = _collect_block_text(original_doc)
    translated_texts = _collect_block_text(translated_doc)

    if len(original_texts) != len(translated_texts):
        logger.warning(
            "Block count mismatch: original=%s translated=%s",
            len(original_texts),
            len(translated_texts),
        )

    matches = _align_paragraphs(paragraphs, original_texts)

    updated = 0
    skipped = 0
    for match, translated in zip(matches, translated_texts):
        if match is None:
            skipped += 1
            continue
        _replace_paragraph_text(match, translated)
        updated += 1

    if skipped:
        logger.warning("Skipped %s blocks because matching paragraph not found", skipped)
    logger.info("Updated %s paragraphs in DOCX", updated)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    document.save(str(output_path))
    return output_path


def _collect_block_text(doc: KPSDocument) -> List[str]:
    texts: List[str] = []
    for section in doc.sections:
        for block in section.blocks:
            texts.append(block.content or "")
    return texts


def _iter_block_items(parent) -> Iterable[object]:
    if isinstance(parent, DocxDocument):
        parent_elm = parent.element.body
    elif isinstance(parent, _Cell):
        parent_elm = parent._tc
    else:  # Table, etc.
        parent_elm = parent._tbl
    for child in parent_elm.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)


def _iter_paragraphs(parent) -> Iterable[Paragraph]:
    for block in _iter_block_items(parent):
        if isinstance(block, Paragraph):
            yield block
        elif isinstance(block, Table):
            for row in block.rows:
                for cell in row.cells:
                    for paragraph in _iter_paragraphs(cell):
                        yield paragraph


def _align_paragraphs(
    paragraphs: List[Paragraph], original_texts: List[str]
) -> List[Optional[Paragraph]]:
    matches: List[Optional[Paragraph]] = []
    idx = 0
    total = len(paragraphs)
    for original_text in original_texts:
        norm = _normalize(original_text)
        if not norm:
            matches.append(None)
            continue
        found = None
        while idx < total:
            para = paragraphs[idx]
            para_norm = _normalize(para.text)
            idx += 1
            if para_norm == norm:
                found = para
                break
        matches.append(found)
    return matches


def _replace_paragraph_text(paragraph: Paragraph, new_text: str) -> None:
    for run in paragraph.runs:
        run.text = ""
    if not paragraph.runs:
        paragraph.add_run("")
    paragraph.runs[0].text = new_text


def _normalize(text: str) -> str:
    if not text:
        return ""
    text = unescape(text)
    text = text.replace("\xa0", " ")
    return " ".join(text.split())


def build_docx_from_structure(translated_doc: KPSDocument, output_path: Path) -> Path:
    """Create a fresh DOCX from translated blocks when original template is unavailable."""

    doc = Document()
    _clear_paragraph(doc.paragraphs[0])

    for section in translated_doc.sections:
        if section.title:
            doc.add_heading(section.title, level=2)
        for block in section.blocks:
            _append_block(doc, block.block_type, block.content)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    return output_path


def _append_block(doc: Document, block_type: BlockType, content: str) -> None:
    text = content or ""
    if block_type == BlockType.HEADING:
        doc.add_heading(text, level=3)
    elif block_type == BlockType.LIST:
        for line in text.splitlines():
            if line.strip():
                doc.add_paragraph(line.strip(), style="List Bullet")
    elif block_type == BlockType.TABLE:
        rows = [line.split("\t") for line in text.splitlines() if line]
        if not rows:
            doc.add_paragraph(text)
            return
        cols = max(len(row) for row in rows)
        table = doc.add_table(rows=len(rows), cols=cols)
        for r_idx, row in enumerate(rows):
            for c_idx, value in enumerate(row):
                cell = table.cell(r_idx, c_idx)
                _clear_paragraph(cell.paragraphs[0])
                cell.paragraphs[0].add_run(value)
    elif block_type == BlockType.FIGURE:
        para = doc.add_paragraph()
        para.style = "Caption"
        para.add_run(text)
    else:
        for idx, line in enumerate(text.splitlines() or [""]):
            if idx == 0:
                para = doc.add_paragraph()
            else:
                para = doc.add_paragraph()
            para.add_run(line)


def _clear_paragraph(paragraph: Paragraph) -> None:
    for run in paragraph.runs:
        run.text = ""
