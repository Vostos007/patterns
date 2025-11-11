"""Docling powered text extraction for the KPS pipeline.

Historically this module was a partially copied notebook dump that did not even
compile.  The refactored implementation below wraps Docling's
``DocumentConverter`` in a small, well-tested façade that produces
``KPSDocument`` instances ready for segmentation.

Design goals of the refactor:

* Centralise error handling to surface actionable messages when Docling fails.
* Encapsulate section and block bookkeeping so adding new rules is trivial.
* Keep the public ``DoclingExtractor`` API backward compatible; existing tests
  and fixtures continue to work unchanged.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from docling.datamodel.base_models import InputFormat
from docling.datamodel.document import ConversionResult
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc.document import DoclingDocument

from kps.core.bbox import BBox
from kps.core.document import BlockType, ContentBlock, DocumentMetadata, KPSDocument, Section, SectionType

logger = logging.getLogger(__name__)


class DoclingExtractionError(RuntimeError):
    """Raised when Docling could not produce a valid document."""


@dataclass
class _BlockIdTracker:
    """Utility to generate deterministic block identifiers."""

    counters: Dict[Tuple[BlockType, SectionType], int] = field(default_factory=dict)

    def next(self, block_type: BlockType, section: SectionType) -> str:
        prefix = DoclingExtractor.BLOCK_TYPE_PREFIXES.get(block_type, "blk")
        key = (block_type, section)
        self.counters[key] = self.counters.get(key, 0) + 1
        return f"{prefix}.{section.value}.{self.counters[key]:03d}"


class DoclingExtractor:
    """High-level façade over Docling's ``DocumentConverter``."""

    SECTION_PATTERNS: Dict[str, List[str]] = {
        SectionType.MATERIALS.value: [r"материал", r"пряжа", r"нитки", r"инструмент", r"material"],
        SectionType.GAUGE.value: [r"плотност", r"образец", r"density", r"gauge"],
        SectionType.SIZES.value: [r"размер", r"обхват", r"длина", r"size"],
        SectionType.TECHNIQUES.value: [r"техник", r"приём", r"метод", r"technique"],
        SectionType.INSTRUCTIONS.value: [r"инструкц", r"описание работ", r"выполнение", r"instruction"],
        SectionType.FINISHING.value: [r"сборк", r"отделк", r"оформлен", r"finishing"],
        SectionType.ABBREVIATIONS.value: [r"сокращен", r"условн.*обозначен", r"abbreviation"],
        SectionType.GLOSSARY.value: [r"глоссари", r"словарь", r"glossary"],
        SectionType.CONSTRUCTION.value: [r"конструк", r"выкройк", r"construction"],
    }

    BLOCK_TYPE_PREFIXES: Dict[BlockType, str] = {
        BlockType.PARAGRAPH: "p",
        BlockType.HEADING: "h",
        BlockType.LIST: "lst",
        BlockType.TABLE: "tbl",
        BlockType.FIGURE: "fig",
    }

    def __init__(
        self,
        languages: Optional[List[str]] = None,
        *,
        ocr_enabled: bool = True,
        page_range: Optional[Tuple[int, int]] = None,
    ) -> None:
        self.languages = languages or ["ru", "en", "fr"]
        self.ocr_enabled = ocr_enabled
        self.page_range = page_range
        self._converter = self._build_converter()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def extract_document(self, pdf_path: Path, slug: str) -> KPSDocument:
        """Return a structured :class:`KPSDocument` for ``pdf_path``."""

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        logger.info("Extracting %s", pdf_path)

        try:
            result: ConversionResult = self._converter.convert(str(pdf_path))
        except Exception as exc:  # pragma: no cover - Docling raises custom errors
            raise DoclingExtractionError(f"Docling failed to convert '{pdf_path}': {exc}") from exc

        if not result or not result.document:
            raise DoclingExtractionError(f"Docling returned an empty document for '{pdf_path}'")

        doc = result.document
        metadata = self._extract_metadata(doc, pdf_path)
        sections = self._extract_sections(doc)

        if not sections:
            raise DoclingExtractionError(f"Docling produced no sections for '{pdf_path}'")

        logger.info(
            "Docling extraction produced %s sections / %s blocks",
            len(sections),
            sum(len(section.blocks) for section in sections),
        )

        return KPSDocument(slug=slug, metadata=metadata, sections=sections)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    def _build_converter(self) -> DocumentConverter:
        options = PdfPipelineOptions(do_ocr=self.ocr_enabled, do_table_structure=True)
        format_options = {InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
        return DocumentConverter(format_options=format_options)

    def _extract_metadata(self, doc: DoclingDocument, pdf_path: Path) -> DocumentMetadata:
        title = pdf_path.stem
        author = None
        created_date = None

        if getattr(doc, "metadata", None):
            title = getattr(doc.metadata, "title", title) or title
            author = getattr(doc.metadata, "author", author)
            created_date = getattr(doc.metadata, "date", created_date)

        return DocumentMetadata(
            title=title,
            author=author,
            version="1.0.0",
            language=self._detect_language(doc),
            created_date=created_date,
        )

    def _detect_language(self, doc: DoclingDocument) -> str:
        text_sample = ""
        if getattr(doc, "body", None) and getattr(doc.body, "text", None):
            text_sample = doc.body.text[:1000]

        if re.search(r"[а-яА-ЯёЁ]", text_sample):
            return "ru"

        return self.languages[0] if self.languages else "en"

    def _extract_sections(self, doc: DoclingDocument) -> List[Section]:
        if not getattr(doc, "body", None):
            return []

        sections: List[Section] = []
        current_section: Optional[Section] = None
        current_section_type = SectionType.COVER
        section_counts: Dict[SectionType, int] = {}
        id_tracker = _BlockIdTracker()

        for element in doc.body:
            element_type = getattr(element, "obj_type", "") or ""
            text = (getattr(element, "text", "") or "").strip()

            if not text:
                continue

            if "heading" in element_type.lower():
                current_section_type = self._infer_section_type(text)
                section_counts[current_section_type] = section_counts.get(current_section_type, 0) + 1
                if current_section:
                    sections.append(current_section)
                current_section = Section(section_type=current_section_type, title=text)
                block = self._build_block(element, text, BlockType.HEADING, current_section_type, id_tracker)
                current_section.add_block(block)
                continue

            if current_section is None:
                current_section = Section(section_type=SectionType.COVER, title="Cover")

            block_type = self._map_type(element_type)
            block = self._build_block(element, text, block_type, current_section_type, id_tracker)
            current_section.add_block(block)

        if current_section:
            sections.append(current_section)

        return sections

    def _infer_section_type(self, heading_text: str) -> SectionType:
        lowered = heading_text.lower()
        for section_value, patterns in self.SECTION_PATTERNS.items():
            if any(re.search(pattern, lowered) for pattern in patterns):
                return SectionType(section_value)
        logger.debug("Fallback section type for heading: %s", heading_text)
        return SectionType.INSTRUCTIONS

    def _map_type(self, element_type: str) -> BlockType:
        lowered = element_type.lower()
        if "heading" in lowered:
            return BlockType.HEADING
        if "list" in lowered or "item" in lowered:
            return BlockType.LIST
        if "table" in lowered:
            return BlockType.TABLE
        if "figure" in lowered or "image" in lowered:
            return BlockType.FIGURE
        return BlockType.PARAGRAPH

    def _build_block(
        self,
        element,
        text: str,
        block_type: BlockType,
        section_type: SectionType,
        tracker: _BlockIdTracker,
    ) -> ContentBlock:
        block_id = tracker.next(block_type, section_type)
        bbox = self._extract_bbox(element)
        page_number = getattr(element, "page_number", None)
        reading_order = getattr(element, "reading_order", 0)
        return ContentBlock(
            block_id=block_id,
            block_type=block_type,
            content=text,
            bbox=bbox,
            page_number=page_number,
            reading_order=reading_order,
        )

    def _extract_bbox(self, element) -> Optional[BBox]:
        bbox = getattr(element, "bbox", None)
        if not bbox or not isinstance(bbox, (tuple, list)) or len(bbox) != 4:
            return None
        try:
            x0, y0, x1, y1 = (float(coord) for coord in bbox)
        except (TypeError, ValueError):  # pragma: no cover - Docling guard
            logger.debug("Invalid bbox %s", bbox)
            return None
        return BBox(x0=x0, y0=y0, x1=x1, y1=y1)


__all__ = ["DoclingExtractor", "DoclingExtractionError"]

