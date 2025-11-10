"""Docling-based text extraction for KPS v2.0.

This module uses Docling's DocumentConverter API to extract semantic text structure
from PDFs, converting it into KPSDocument format with proper section detection and
block hierarchy preservation.
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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

        # Iterate through document elements
        for item in docling_doc.body:
            # Get item properties
            item_type = getattr(item, "obj_type", None)
            text = getattr(item, "text", "").strip()

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
                    item, text, BlockType.HEADING, section_type
                )
                current_section.add_block(block)

            else:
                # Regular content block
                if not current_section:
                    # No section yet, create default COVER section
                    current_section = Section(
                        section_type=SectionType.COVER, title="Cover"
                    )
                    self.current_section_type = SectionType.COVER

                # Map Docling type to BlockType
                block_type = self._map_docling_type(item_type)

                # Create block
                block = self._create_content_block(
                    item, text, block_type, self.current_section_type
                )
                current_section.add_block(block)

        # Add final section
        if current_section:
            sections.append(current_section)

        return sections

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

    def _map_docling_type(self, docling_type: Optional[str]) -> BlockType:
        """
        Map Docling element type to KPS BlockType.

        Args:
            docling_type: Docling element type string

        Returns:
            BlockType enum value
        """
        if not docling_type:
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
            return BlockType.PARAGRAPH

    def _create_content_block(
        self,
        docling_item,
        text: str,
        block_type: BlockType,
        section_type: SectionType,
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
        )

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
