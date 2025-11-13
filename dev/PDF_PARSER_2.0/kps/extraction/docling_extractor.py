"""Docling-based text extraction for KPS v2.0.

This module uses Docling's DocumentConverter API to extract semantic text structure
from PDFs, converting it into KPSDocument format with proper section detection and
block hierarchy preservation.
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.document import ConversionResult
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling_core.types.doc.document import DoclingDocument

from kps.core.bbox import BBox
from kps.core.document import (
    BlockType,
    ContentBlock,
    DocumentMetadata,
    KPSDocument,
    Section,
    SectionType,
)


logger = logging.getLogger(__name__)


class DoclingExtractionError(Exception):
    """Raised when Docling extraction fails."""

    pass


class DoclingExtractor:
    """
    Extract text and structure from PDFs using Docling.

    This extractor uses Docling's semantic understanding to:
    - Detect document structure (headings, paragraphs, lists, tables)
    - Preserve reading order
    - Identify section types based on heading patterns
    - Generate unique block IDs for each content element

    Configuration:
    - languages: List of document languages (default: ["ru", "en", "fr"])
    - ocr_enabled: Enable OCR fallback for scanned PDFs (default: True)
    - page_range: Optional (start, end) tuple to limit extraction
    """

    # Russian section name patterns for detection
    SECTION_PATTERNS: Dict[str, List[str]] = {
        SectionType.MATERIALS.value: [
            r"материал",
            r"пряжа",
            r"нитки",
            r"инструмент",
            r"material",
        ],
        SectionType.GAUGE.value: [
            r"плотност",
            r"образец",
            r"density",
            r"gauge",
        ],
        SectionType.SIZES.value: [
            r"размер",
            r"обхват",
            r"длина",
            r"size",
        ],
        SectionType.TECHNIQUES.value: [
            r"техник",
            r"приём",
            r"метод",
            r"technique",
        ],
        SectionType.INSTRUCTIONS.value: [
            r"инструкц",
            r"описание работ",
            r"выполнение",
            r"instruction",
        ],
        SectionType.FINISHING.value: [
            r"сборк",
            r"отделк",
            r"оформлен",
            r"finishing",
        ],
        SectionType.ABBREVIATIONS.value: [
            r"сокращен",
            r"условн.*обозначен",
            r"abbreviation",
        ],
        SectionType.GLOSSARY.value: [
            r"глоссари",
            r"словарь",
            r"glossary",
        ],
        SectionType.CONSTRUCTION.value: [
            r"конструк",
            r"выкройк",
            r"construction",
        ],
    }

    # Block type ID prefixes
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
        ocr_enabled: bool = True,
        page_range: Optional[Tuple[int, int]] = None,
    ):
        """
        Initialize Docling extractor.

        Args:
            languages: List of document languages (ISO 639-1 codes)
            ocr_enabled: Enable OCR fallback for scanned PDFs
            page_range: Optional (start_page, end_page) for partial extraction
        """
        self.languages = languages or ["ru", "en", "fr"]
        self.ocr_enabled = ocr_enabled
        self.page_range = page_range

        # Initialize Docling converter with configuration
        self.converter = self._create_converter()

        # Section detection state
        self.current_section_type = SectionType.COVER
        self.section_counters: Dict[SectionType, int] = {}
        self.block_counters: Dict[Tuple[BlockType, SectionType], int] = {}
        self.last_docling_document: Optional[DoclingDocument] = None
        self.last_block_map: Dict[str, object] = {}

    def _create_converter(self) -> DocumentConverter:
        """Create configured Docling DocumentConverter instance."""
        # Configure PDF pipeline options
        pipeline_options = PdfPipelineOptions(
            do_ocr=self.ocr_enabled,
            do_table_structure=True,
        )

        # Create format options
        format_options = {
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }

        # Create converter
        converter = DocumentConverter(
            format_options=format_options,
        )

        logger.info(
            f"Initialized Docling converter (OCR: {self.ocr_enabled}, "
            f"languages: {self.languages})"
        )

        return converter

    def extract_document(self, pdf_path: Path, slug: str) -> KPSDocument:
        """
        Extract KPSDocument from PDF.

        Args:
            pdf_path: Path to source PDF file
            slug: Document slug (e.g., "bonjour-gloves")

        Returns:
            KPSDocument with structured sections and blocks

        Raises:
            DoclingExtractionError: If extraction fails
            FileNotFoundError: If PDF file doesn't exist
            ValueError: If PDF is empty or invalid
        """
        # Validate input
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        logger.info(f"Extracting document from {pdf_path}")

        try:
            # Convert document with Docling
            result: ConversionResult = self.converter.convert(str(pdf_path))

            if not result or not result.document:
                raise DoclingExtractionError("Docling returned empty result")

            docling_doc: DoclingDocument = result.document
            self.last_docling_document = docling_doc
            self.last_block_map = {}

            # Validate document has content
            if not docling_doc.body:
                raise ValueError(f"PDF contains no extractable content: {pdf_path}")

            # Extract metadata
            metadata = self._extract_metadata(docling_doc, pdf_path)

            # Extract sections and blocks
            sections = self._extract_sections(docling_doc)

            if not sections:
                raise ValueError(f"No sections extracted from PDF: {pdf_path}")

            # Create KPSDocument
            kps_doc = KPSDocument(
                slug=slug,
                metadata=metadata,
                sections=sections,
                docling_document=docling_doc,
            )

            logger.info(
                f"Extracted {len(sections)} sections, "
                f"{sum(len(s.blocks) for s in sections)} total blocks"
            )

            return kps_doc

        except Exception as e:
            logger.error(f"Docling extraction failed: {e}")
            raise DoclingExtractionError(f"Failed to extract document: {e}") from e

    def _extract_metadata(
        self, docling_doc: DoclingDocument, pdf_path: Path
    ) -> DocumentMetadata:
        """Extract document metadata from Docling document."""
        # Get metadata from Docling
        title = pdf_path.stem  # Default to filename
        author = None
        created_date = None

        # Try to extract from Docling metadata if available
        if hasattr(docling_doc, "metadata") and docling_doc.metadata:
            title = getattr(docling_doc.metadata, "title", title)
            author = getattr(docling_doc.metadata, "author", author)
            created_date = getattr(docling_doc.metadata, "date", created_date)

        # Detect primary language
        language = self._detect_primary_language(docling_doc)

        return DocumentMetadata(
            title=title,
            author=author,
            version="1.0.0",
            language=language,
            created_date=created_date,
        )

    def _detect_primary_language(self, docling_doc: DoclingDocument) -> str:
        """
        Detect primary document language.

        Uses simple heuristics:
        - Check for Cyrillic characters → Russian
        - Otherwise default to first configured language
        """
        # Sample text from document body
        text_sample = ""
        if docling_doc.body and hasattr(docling_doc.body, "text"):
            text_sample = docling_doc.body.text[:1000]  # First 1000 chars

        # Check for Cyrillic
        if re.search(r"[а-яА-ЯёЁ]", text_sample):
            return "ru"

        # Default to first configured language
        return self.languages[0] if self.languages else "en"

    def _extract_sections(self, docling_doc: DoclingDocument) -> List[Section]:
        """
        Extract sections from Docling document.

        Processes document body to:
        - Detect section boundaries based on headings
        - Map headings to section types
        - Create ContentBlocks for all elements
        - Preserve reading order
        """
        sections: List[Section] = []
        current_section: Optional[Section] = None

        # Reset counters
        self.section_counters.clear()
        self.block_counters.clear()
        self.current_section_type = SectionType.COVER

        # Iterate through document elements (flattening nested groups)
        iterable = self._iter_docling_items(docling_doc)

        for doc_ref, item in iterable:
            # Get item properties
            item_type = getattr(item, "obj_type", None)
            block_type = self._map_docling_type(item_type, item)

            raw_text = getattr(item, "text", "")
            text = raw_text.strip() if isinstance(raw_text, str) else ""

            if block_type == BlockType.TABLE:
                text = self._extract_table_content(item, docling_doc)

            if not text:
                continue

            # Check if this is a heading (new section)
            if item_type and "heading" in item_type.lower():
                # Detect section type from heading text
                section_type = self._detect_section_type(text)

                # Create new section
                if current_section:
                    sections.append(current_section)

                current_section = Section(section_type=section_type, title=text)

                self.current_section_type = section_type
                if section_type not in self.section_counters:
                    self.section_counters[section_type] = 0
                self.section_counters[section_type] += 1

                # Add heading as block
                block = self._create_content_block(
                    item,
                    text,
                    BlockType.HEADING,
                    section_type,
                    doc_ref=doc_ref,
                )
                current_section.add_block(block)
                self.last_block_map[block.block_id] = item

            else:
                # Regular content block
                if not current_section:
                    # No section yet, create default COVER section
                    current_section = Section(
                        section_type=SectionType.COVER, title="Cover"
                    )
                    self.current_section_type = SectionType.COVER

                # Create block
                block = self._create_content_block(
                    item,
                    text,
                    block_type,
                    self.current_section_type,
                    doc_ref=doc_ref,
                )
                current_section.add_block(block)
                self.last_block_map[block.block_id] = item

        # Add final section
        if current_section:
            sections.append(current_section)

        return sections

    def _extract_table_content(
        self, table_item: Any, docling_doc: Optional[DoclingDocument]
    ) -> str:
        """Render Docling table nodes into Markdown text."""

        if table_item is None:
            return ""

        doc = docling_doc or self.last_docling_document

        markdown = self._export_docling_table(table_item, doc)
        if markdown:
            return markdown

        dataframe_md = self._export_table_via_dataframe(table_item, doc)
        if dataframe_md:
            return dataframe_md

        fallback = self._render_table_cells(table_item)
        if fallback:
            return fallback

        logger.debug("Docling table %s had no renderable content", getattr(table_item, "cref", None))
        return ""

    def _export_docling_table(
        self, table_item: Any, docling_doc: Optional[DoclingDocument]
    ) -> str:
        """Try Docling's native Markdown export helpers."""

        exporter = getattr(table_item, "export_to_markdown", None)
        if not callable(exporter):
            return ""

        candidates: List[Optional[DoclingDocument]] = []
        if docling_doc and docling_doc not in candidates:
            candidates.append(docling_doc)
        if self.last_docling_document and self.last_docling_document not in candidates:
            candidates.append(self.last_docling_document)
        candidates.append(None)  # Fall back to legacy no-arg signature

        for candidate in candidates:
            try:
                result = (
                    exporter(candidate)
                    if candidate is not None
                    else exporter()
                )
            except TypeError:
                # Some versions only support the no-arg form
                result = exporter()
            except Exception as exc:  # pragma: no cover - diagnostic only
                logger.debug("Docling markdown export failed: %s", exc)
                break

            text = (result or "").strip()
            if text:
                caption = self._get_table_caption(table_item)
                if caption:
                    return f"{caption}\n{text}"
                return text

        return ""

    def _export_table_via_dataframe(
        self, table_item: Any, docling_doc: Optional[DoclingDocument]
    ) -> str:
        """Render table through pandas DataFrame if available."""

        exporter = getattr(table_item, "export_to_dataframe", None)
        if not callable(exporter):
            return ""

        try:  # Import locally to keep module import cost low
            import pandas as pd  # type: ignore
        except Exception:  # pragma: no cover - pandas optional
            return ""

        candidates: List[Optional[DoclingDocument]] = []
        if docling_doc and docling_doc not in candidates:
            candidates.append(docling_doc)
        if self.last_docling_document and self.last_docling_document not in candidates:
            candidates.append(self.last_docling_document)
        candidates.append(None)

        for candidate in candidates:
            try:
                df = (
                    exporter(candidate)
                    if candidate is not None
                    else exporter()
                )
            except TypeError:
                df = exporter()
            except Exception as exc:  # pragma: no cover - diagnostic only
                logger.debug("Docling dataframe export failed: %s", exc)
                break

            if df is None:
                continue

            try:
                pd_df = pd.DataFrame(df)
            except Exception:
                continue

            if pd_df.empty:
                continue

            if not isinstance(pd_df.index, pd.RangeIndex):
                pd_df = pd_df.reset_index()
                index_col = pd_df.columns[0]
                if index_col == "index":
                    pd_df = pd_df.rename(columns={"index": "Row"})

            try:
                rendered = pd_df.to_markdown(index=False).strip()
            except Exception:
                continue

            if rendered:
                caption = self._get_table_caption(table_item)
                if caption:
                    return f"{caption}\n{rendered}"
                return rendered

        return ""

    def _render_table_cells(self, table_item: Any) -> str:
        """Fallback renderer that walks Docling cell metadata."""

        data = getattr(table_item, "data", None) or {}
        cells = data.get("table_cells") if isinstance(data, dict) else None
        if not cells:
            return ""

        row_count = 0
        col_count = 0
        for cell in cells:
            row_count = max(row_count, cell.get("end_row_offset_idx", 0))
            col_count = max(col_count, cell.get("end_col_offset_idx", 0))

        if row_count == 0 or col_count == 0:
            return ""

        grid: List[List[str]] = [["" for _ in range(col_count)] for _ in range(row_count)]

        for cell in cells:
            text = (cell.get("text") or "").strip()
            if not text:
                continue

            row = min(row_count - 1, max(0, cell.get("start_row_offset_idx", 0)))
            col = min(col_count - 1, max(0, cell.get("start_col_offset_idx", 0)))

            existing = grid[row][col]
            grid[row][col] = text if not existing else f"{existing} / {text}"

        rows = [row for row in grid if any(col.strip() for col in row)]
        if not rows:
            return ""

        header = rows[0]
        lines = [" | ".join(header).strip()]

        if len(rows) > 1:
            separator = " | ".join("---" if cell else "---" for cell in header).strip()
            if separator:
                lines.append(separator)
            for row in rows[1:]:
                lines.append(" | ".join(cell or "" for cell in row).strip())

        return "\n".join(line for line in lines if line).strip()

    def _iter_docling_items(self, docling_doc: DoclingDocument):
        """
        Yield flattened Docling items, descending into nested groups/lists.

        Docling 2.x often wraps actual text nodes inside GroupItem/ListGroup
        containers. Without flattening, large portions of the document never
        reach the segmentation phase. This generator resolves RefItem objects
        and yields leaf nodes paired with their document reference IDs so we can
        stitch translations back to Docling later.
        """

        body_root = getattr(docling_doc, "body", None)
        if body_root is None:
            return []

        children = getattr(body_root, "children", None) or body_root

        def _walk(raw_item):
            resolved = self._resolve_docling_item(docling_doc, raw_item)
            doc_ref = getattr(raw_item, "cref", None) or getattr(
                resolved, "cref", None
            )

            child_items = getattr(resolved, "children", None) or []
            if child_items:
                for child in child_items:
                    yield from _walk(child)
            else:
                yield doc_ref, resolved

        for child in children:
            yield from _walk(child)

    def _detect_section_type(self, heading_text: str) -> SectionType:
        """
        Detect section type from heading text using pattern matching.

        Args:
            heading_text: Heading text to analyze

        Returns:
            SectionType enum value
        """
        text_lower = heading_text.lower()

        # Try each pattern
        for section_type_str, patterns in self.SECTION_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return SectionType(section_type_str)

        # Default to INSTRUCTIONS if no match
        logger.debug(f"No section type match for heading: {heading_text}")
        return SectionType.INSTRUCTIONS

    def _map_docling_type(
        self, docling_type: Optional[str], docling_item: Optional[Any] = None
    ) -> BlockType:
        """
        Map Docling element type to KPS BlockType.

        Args:
            docling_type: Docling element type string

        Returns:
            BlockType enum value
        """
        if not docling_type:
            label_hint = self._infer_docling_label(docling_item)
            if label_hint == "table":
                return BlockType.TABLE
            if label_hint in {"figure", "image", "picture"}:
                return BlockType.FIGURE
            return BlockType.PARAGRAPH

        type_lower = docling_type.lower()

        if "heading" in type_lower:
            return BlockType.HEADING
        elif "list" in type_lower or "item" in type_lower:
            return BlockType.LIST
        elif "table" in type_lower:
            return BlockType.TABLE
        elif "figure" in type_lower or "image" in type_lower:
            return BlockType.FIGURE
        else:
            label_hint = self._infer_docling_label(docling_item)
            if label_hint == "table":
                return BlockType.TABLE
            if label_hint in {"figure", "image", "picture"}:
                return BlockType.FIGURE
            return BlockType.PARAGRAPH

    def _infer_docling_label(self, docling_item: Optional[Any]) -> Optional[str]:
        """Extract lowercase label value from Docling items when available."""

        if docling_item is None:
            return None

        label = getattr(docling_item, "label", None)
        if label is None:
            return None

        if hasattr(label, "value"):
            return str(label.value).lower()

        try:
            return str(label).lower()
        except Exception:
            return None

    def _get_table_caption(self, table_item: Any) -> Optional[str]:
        """Best-effort extraction of table captions across Docling versions."""

        caption = getattr(table_item, "caption_text", None)
        if callable(caption):
            try:
                caption = caption()
            except Exception:
                caption = None

        if isinstance(caption, str):
            caption = caption.strip()
            if caption:
                return caption

        captions = getattr(table_item, "captions", None)
        if isinstance(captions, list) and captions:
            first = captions[0]
            if isinstance(first, str):
                first = first.strip()
                if first:
                    return first

        return None

    def _create_content_block(
        self,
        docling_item,
        text: str,
        block_type: BlockType,
        section_type: SectionType,
        doc_ref: Optional[str] = None,
    ) -> ContentBlock:
        """
        Create ContentBlock from Docling item.

        Args:
            docling_item: Docling document item
            text: Extracted text content
            block_type: KPS block type
            section_type: Current section type

        Returns:
            ContentBlock with unique ID and metadata
        """
        # Generate block ID
        block_id = self._generate_block_id(block_type, section_type)

        # Extract bbox if available
        bbox = self._extract_bbox(docling_item)

        # Extract page number if available
        page_number = getattr(docling_item, "page_number", None)

        # Extract reading order if available
        reading_order = getattr(docling_item, "reading_order", 0)

        return ContentBlock(
            block_id=block_id,
            block_type=block_type,
            content=text,
            bbox=bbox,
            page_number=page_number,
            reading_order=reading_order,
            doc_ref=doc_ref,
        )

    def _resolve_docling_item(self, docling_doc: DoclingDocument, item):
        """Resolve Docling references (RefItem) to actual objects."""

        # Docling 2.x emits RefItem placeholders that must be resolved against the
        # owning document via the RefItem.resolve() helper. Older releases exposed
        # DoclingDocument.resolve_ref(). Support both so we can handle either
        # representation without depending on a specific docling build.
        if hasattr(item, "resolve"):
            try:
                resolved = item.resolve(docling_doc)
                if resolved is not None:
                    return resolved
            except Exception as exc:  # pragma: no cover - debugging only
                logger.debug(
                    f"Failed to resolve reference via item.resolve for {item}: {exc}"
                )

        if hasattr(item, "cref") and hasattr(docling_doc, "resolve_ref"):
            try:
                resolved = docling_doc.resolve_ref(item)
                if resolved is not None:
                    return resolved
            except Exception as exc:  # pragma: no cover - debugging only
                logger.debug(
                    f"Failed to resolve reference via doc.resolve_ref for {item}: {exc}"
                )

        return item

    def _extract_bbox(self, docling_item) -> Optional[BBox]:
        """
        Extract bounding box from Docling item.

        Args:
            docling_item: Docling document item

        Returns:
            BBox if available, None otherwise
        """
        # Check if item has bbox
        if not hasattr(docling_item, "bbox"):
            return None

        bbox_data = docling_item.bbox

        # Docling bbox format: (x0, y0, x1, y1) or similar
        if isinstance(bbox_data, (list, tuple)) and len(bbox_data) == 4:
            try:
                return BBox(
                    x0=float(bbox_data[0]),
                    y0=float(bbox_data[1]),
                    x1=float(bbox_data[2]),
                    y1=float(bbox_data[3]),
                )
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse bbox {bbox_data}: {e}")
                return None

        return None

    def _generate_block_id(
        self, block_type: BlockType, section_type: SectionType
    ) -> str:
        """
        Generate unique block ID.

        Format: "{type_prefix}.{section}.{number:03d}"
        Examples:
        - "p.materials.001"
        - "h.techniques.002"
        - "tbl.sizes.001"

        Args:
            block_type: Block type
            section_type: Current section type

        Returns:
            Unique block ID string
        """
        # Get type prefix
        prefix = self.BLOCK_TYPE_PREFIXES.get(block_type, "blk")

        # Increment counter
        counter_key = (block_type, section_type)
        if counter_key not in self.block_counters:
            self.block_counters[counter_key] = 0
        self.block_counters[counter_key] += 1

        counter = self.block_counters[counter_key]

        # Format ID
        return f"{prefix}.{section_type.value}.{counter:03d}"
