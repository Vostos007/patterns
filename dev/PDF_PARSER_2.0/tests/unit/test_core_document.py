"""Unit tests for the refactored core document structures."""

from __future__ import annotations

from pathlib import Path

import pytest

from kps.core.bbox import BBox
from kps.core.document import (
    BlockType,
    ContentBlock,
    DocumentMetadata,
    KPSDocument,
    Section,
    SectionType,
)


@pytest.fixture()
def sample_document(tmp_path: Path) -> KPSDocument:
    metadata = DocumentMetadata(title="Sample", author="Tester", language="ru")
    cover = Section(section_type=SectionType.COVER, title="Cover")
    cover.add_block(
        ContentBlock(
            block_id="p.cover.001",
            block_type=BlockType.PARAGRAPH,
            content="Привет мир",
            bbox=BBox(0, 0, 100, 20),
            page_number=0,
            reading_order=0,
        )
    )
    instructions = Section(section_type=SectionType.INSTRUCTIONS, title="Instructions")
    instructions.add_block(
        ContentBlock(
            block_id="p.instructions.001",
            block_type=BlockType.PARAGRAPH,
            content="1. Сделайте петлю",
            bbox=BBox(0, 20, 100, 40),
            page_number=1,
            reading_order=0,
        )
    )
    return KPSDocument(slug="sample", metadata=metadata, sections=[cover, instructions])


def test_iter_blocks_preserves_order(sample_document: KPSDocument) -> None:
    block_ids = [block.block_id for block in sample_document.iter_blocks()]
    assert block_ids == ["p.cover.001", "p.instructions.001"]


def test_json_roundtrip(sample_document: KPSDocument, tmp_path: Path) -> None:
    path = tmp_path / "document.json"
    sample_document.save_json(path)
    restored = KPSDocument.load_json(path)

    assert restored.slug == sample_document.slug
    assert restored.metadata.title == sample_document.metadata.title
    assert [block.block_id for block in restored.iter_blocks()] == [
        block.block_id for block in sample_document.iter_blocks()
    ]
