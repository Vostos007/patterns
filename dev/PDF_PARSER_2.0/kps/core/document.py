"""KPS Document structure models."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, List, Optional
import json

from .bbox import BBox


class SectionType(Enum):
    """KPS v1.0 standardized section types."""

    COVER = "cover"
    MATERIALS = "materials"
    GAUGE = "gauge"
    SIZES = "sizes"
    CONSTRUCTION = "construction"
    ABBREVIATIONS = "abbreviations"
    TECHNIQUES = "techniques"
    INSTRUCTIONS = "instructions"
    FINISHING = "finishing"
    GLOSSARY = "glossary"


class BlockType(Enum):
    """Content block types."""

    PARAGRAPH = "paragraph"
    HEADING = "heading"
    LIST = "list"
    TABLE = "table"
    FIGURE = "figure"


@dataclass
class ContentBlock:
    """
    Atomic content unit with unique ID.

    block_id format: "type.section.###"
    Examples:
    - "p.materials.001"
    - "h2.techniques.001"
    - "tbl.sizes.001"
    """

    block_id: str
    block_type: BlockType
    content: str  # Text content or table data
    bbox: Optional[BBox] = None  # Position on page
    page_number: Optional[int] = None
    reading_order: int = 0  # For sorting within page
    doc_ref: Optional[str] = None  # Reference into Docling document


@dataclass
class Section:
    """KPS v1.0 standardized section."""

    section_type: SectionType
    title: str
    blocks: List[ContentBlock] = field(default_factory=list)

    def add_block(self, block: ContentBlock) -> None:
        """Add a block to this section."""
        self.blocks.append(block)

    def get_all_text(self) -> str:
        """Get concatenated text from all blocks."""
        return "\n".join(b.content for b in self.blocks)


@dataclass
class DocumentMetadata:
    """Document metadata."""

    title: str
    author: Optional[str] = None
    version: str = "1.0.0"
    language: str = "ru"
    created_date: Optional[str] = None


@dataclass
class KPSDocument:
    """
    Unified KPS document representation.

    This is the text/structure component.
    Visual assets are tracked separately in AssetLedger.
    """

    slug: str  # e.g., "bonjour-gloves"
    metadata: DocumentMetadata
    sections: List[Section] = field(default_factory=list)
    docling_document: Optional[Any] = None  # Holds DoclingDocument when available

    def find_block(self, block_id: str) -> Optional[ContentBlock]:
        """Find a block by ID across all sections."""
        for section in self.sections:
            for block in section.blocks:
                if block.block_id == block_id:
                    return block
        return None

    def get_blocks_on_page(self, page_number: int) -> List[ContentBlock]:
        """Get all blocks on a specific page."""
        blocks = []
        for section in self.sections:
            for block in section.blocks:
                if block.page_number == page_number:
                    blocks.append(block)
        return sorted(blocks, key=lambda b: b.reading_order)

    def get_all_blocks_with_bbox(self) -> List[dict]:
        """
        Get all blocks with bbox for caption detection.

        Returns:
            List of dicts with 'text' and 'bbox' keys.
        """
        result = []
        for section in self.sections:
            for block in section.blocks:
                if block.bbox:
                    result.append({"text": block.content, "bbox": block.bbox})
        return result

    def save_json(self, path: Path) -> None:
        """Serialize to JSON."""
        data = {
            "slug": self.slug,
            "metadata": {
                "title": self.metadata.title,
                "author": self.metadata.author,
                "version": self.metadata.version,
                "language": self.metadata.language,
                "created_date": self.metadata.created_date,
            },
            "sections": [
                {
                    "section_type": s.section_type.value,
                    "title": s.title,
                    "blocks": [
                        {
                            "block_id": b.block_id,
                            "block_type": b.block_type.value,
                            "content": b.content,
                            "bbox": (
                                {
                                    "x0": b.bbox.x0,
                                    "y0": b.bbox.y0,
                                    "x1": b.bbox.x1,
                                    "y1": b.bbox.y1,
                                }
                                if b.bbox
                                else None
                            ),
                            "page_number": b.page_number,
                            "reading_order": b.reading_order,
                            "doc_ref": b.doc_ref,
                        }
                        for b in s.blocks
                    ],
                }
                for s in self.sections
            ],
        }
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    @classmethod
    def load_json(cls, path: Path) -> "KPSDocument":
        """Deserialize from JSON."""
        data = json.loads(path.read_text())

        metadata = DocumentMetadata(**data["metadata"])

        sections = [
            Section(
                section_type=SectionType(s["section_type"]),
                title=s["title"],
                blocks=[
                    ContentBlock(
                        block_id=b["block_id"],
                        block_type=BlockType(b["block_type"]),
                        content=b["content"],
                        bbox=BBox(**b["bbox"]) if b.get("bbox") else None,
                        page_number=b.get("page_number"),
                        reading_order=b.get("reading_order", 0),
                        doc_ref=b.get("doc_ref"),
                    )
                    for b in s["blocks"]
                ],
            )
            for s in data["sections"]
        ]

        return cls(slug=data["slug"], metadata=metadata, sections=sections)
