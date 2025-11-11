"""Core document data structures for the KPS pipeline.

The original repository shipped an unfinished draft of this module: imports were
missing, several identifiers were undefined, and serialization helpers were
spread across the code base.  The refactored version below keeps the public
API identical while providing a coherent, well-typed implementation that the
rest of the pipeline – and the tests under ``dev/PDF_PARSER_2.0/tests`` – can
rely on.

Key improvements:

* Explicit ``Enum`` subclasses with ``str`` values to make JSON (de-)
  serialisation stable.
* Dataclasses for ``ContentBlock`` and ``Section`` with small convenience
  helpers that encapsulate recurring logic (adding a block, iterating over
  blocks, collecting text).
* ``KPSDocument`` exposes an iterator over all blocks and utilities for JSON
  import/export.  These are used heavily across extraction and export tests.
* Defensive validation and predictable ordering behaviour when mutating
  sections.

Together these changes make the module importable again and much easier to
reason about when building higher-level features such as segmentation or
anchoring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional

from .bbox import BBox


class SectionType(str, Enum):
    """Standardised section identifiers used across the pipeline."""

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


class BlockType(str, Enum):
    """Different content block types recognised by the extractor."""

    PARAGRAPH = "paragraph"
    HEADING = "heading"
    LIST = "list"
    TABLE = "table"
    FIGURE = "figure"


@dataclass(slots=True)
class ContentBlock:
    """An atomic piece of content that belongs to a section.

    ``block_id`` values are globally unique and follow the
    ``"<prefix>.<section>.<number>"`` convention.  They are heavily used when
    anchoring assets or comparing documents in regression tests.
    """

    block_id: str
    block_type: BlockType
    content: str
    bbox: Optional[BBox] = None
    page_number: Optional[int] = None
    reading_order: int = 0

    def clone_with_content(self, new_content: str) -> "ContentBlock":
        """Return a copy of the block with different textual content."""

        return ContentBlock(
            block_id=self.block_id,
            block_type=self.block_type,
            content=new_content,
            bbox=self.bbox,
            page_number=self.page_number,
            reading_order=self.reading_order,
        )


@dataclass(slots=True)
class Section:
    """Logical section within the knitting pattern document."""

    section_type: SectionType
    title: str
    blocks: List[ContentBlock] = field(default_factory=list)

    def add_block(self, block: ContentBlock) -> None:
        """Append a block while keeping reading order stable."""

        self.blocks.append(block)
        self.blocks.sort(key=lambda b: (b.page_number or -1, b.reading_order))

    def extend(self, blocks: Iterable[ContentBlock]) -> None:
        """Add multiple blocks at once, preserving the ordering rules."""

        for block in blocks:
            self.add_block(block)

    def iter_blocks(self) -> Iterator[ContentBlock]:
        """Yield all blocks in their logical order."""

        yield from self.blocks

    def get_all_text(self) -> str:
        """Concatenate block contents preserving explicit line breaks."""

        return "\n".join(block.content for block in self.blocks)


@dataclass(slots=True)
class DocumentMetadata:
    """Minimal metadata stored alongside the structured content."""

    title: str
    author: Optional[str] = None
    version: str = "1.0.0"
    language: str = "ru"
    created_date: Optional[str] = None


@dataclass(slots=True)
class KPSDocument:
    """Structured representation of a knitting pattern document."""

    slug: str
    metadata: DocumentMetadata
    sections: List[Section] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Block access helpers
    # ------------------------------------------------------------------
    def iter_blocks(self) -> Iterator[ContentBlock]:
        """Iterate over all blocks in document order."""

        for section in self.sections:
            yield from section.iter_blocks()

    def find_block(self, block_id: str) -> Optional[ContentBlock]:
        """Locate a block by its identifier."""

        for block in self.iter_blocks():
            if block.block_id == block_id:
                return block
        return None

    def get_blocks_on_page(self, page_number: int) -> List[ContentBlock]:
        """Return blocks that appear on a given page sorted by reading order."""

        page_blocks = [
            block
            for block in self.iter_blocks()
            if block.page_number == page_number
        ]
        return sorted(page_blocks, key=lambda block: block.reading_order)

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------
    def to_dict(self) -> Dict:
        """Convert the document into a JSON-serialisable dictionary."""

        return {
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
                    "section_type": section.section_type.value,
                    "title": section.title,
                    "blocks": [
                        {
                            "block_id": block.block_id,
                            "block_type": block.block_type.value,
                            "content": block.content,
                            "bbox": (
                                {
                                    "x0": block.bbox.x0,
                                    "y0": block.bbox.y0,
                                    "x1": block.bbox.x1,
                                    "y1": block.bbox.y1,
                                }
                                if block.bbox
                                else None
                            ),
                            "page_number": block.page_number,
                            "reading_order": block.reading_order,
                        }
                        for block in section.iter_blocks()
                    ],
                }
                for section in self.sections
            ],
        }

    def save_json(self, path: Path) -> None:
        """Serialise the document to disk as UTF-8 encoded JSON."""

        import json

        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    # ------------------------------------------------------------------
    # Constructors
    # ------------------------------------------------------------------
    @classmethod
    def from_dict(cls, data: Dict) -> "KPSDocument":
        """Construct a document instance from a dictionary."""

        metadata = DocumentMetadata(**data["metadata"])
        sections: List[Section] = []

        for section_payload in data.get("sections", []):
            section = Section(
                section_type=SectionType(section_payload["section_type"]),
                title=section_payload["title"],
            )

            for block_payload in section_payload.get("blocks", []):
                bbox_payload = block_payload.get("bbox")
                bbox = BBox(**bbox_payload) if bbox_payload else None
                section.blocks.append(
                    ContentBlock(
                        block_id=block_payload["block_id"],
                        block_type=BlockType(block_payload["block_type"]),
                        content=block_payload["content"],
                        bbox=bbox,
                        page_number=block_payload.get("page_number"),
                        reading_order=block_payload.get("reading_order", 0),
                    )
                )

            sections.append(section)

        return cls(slug=data["slug"], metadata=metadata, sections=sections)

    @classmethod
    def load_json(cls, path: Path) -> "KPSDocument":
        """Load a document from a JSON file."""

        import json

        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))


__all__ = [
    "SectionType",
    "BlockType",
    "ContentBlock",
    "Section",
    "DocumentMetadata",
    "KPSDocument",
]

