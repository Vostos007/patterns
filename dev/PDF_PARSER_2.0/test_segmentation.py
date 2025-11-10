"""
Test script for text segmentation with placeholder encoding.

Validates Day 3 implementation:
- One segment per ContentBlock
- Placeholder encoding (URLs, emails, numbers, [[asset_id]])
- Newline preservation
- Segment ID generation
- Merge functionality
"""

from kps.core.document import (
    ContentBlock,
    BlockType,
    Section,
    SectionType,
    KPSDocument,
    DocumentMetadata,
)
from kps.extraction import Segmenter, SegmenterConfig


def test_basic_segmentation():
    """Test basic segmentation: one block → one segment."""
    print("\n=== Test 1: Basic Segmentation ===")

    # Create simple document
    block = ContentBlock(
        block_id="p.materials.001",
        block_type=BlockType.PARAGRAPH,
        content="This is a simple paragraph.",
    )

    section = Section(
        section_type=SectionType.MATERIALS, title="Materials", blocks=[block]
    )

    doc = KPSDocument(
        slug="test-pattern",
        metadata=DocumentMetadata(title="Test Pattern"),
        sections=[section],
    )

    # Segment
    segmenter = Segmenter()
    segments = segmenter.segment_document(doc)

    # Validate
    assert len(segments) == 1, f"Expected 1 segment, got {len(segments)}"
    assert (
        segments[0].segment_id == "p.materials.001.seg0"
    ), f"Wrong segment ID: {segments[0].segment_id}"
    assert segments[0].text == "This is a simple paragraph."
    assert segments[0].placeholders == {}

    print(f"✓ Created {len(segments)} segment")
    print(f"  Segment ID: {segments[0].segment_id}")
    print(f"  Text: {segments[0].text}")


def test_placeholder_encoding():
    """Test placeholder encoding for URLs, emails, numbers, and asset markers."""
    print("\n=== Test 2: Placeholder Encoding ===")

    # Create block with fragile tokens
    block = ContentBlock(
        block_id="p.instructions.001",
        block_type=BlockType.PARAGRAPH,
        content=(
            "Visit https://example.com for details. "
            "Email contact@example.com for questions. "
            "Use 123,456.78 grams of yarn. "
            "See [[img-abc123-p0-occ1]] for diagram."
        ),
    )

    section = Section(
        section_type=SectionType.INSTRUCTIONS, title="Instructions", blocks=[block]
    )

    doc = KPSDocument(
        slug="test-pattern",
        metadata=DocumentMetadata(title="Test Pattern"),
        sections=[section],
    )

    # Segment
    segmenter = Segmenter()
    segments = segmenter.segment_document(doc)

    # Validate
    assert len(segments) == 1
    segment = segments[0]

    print(f"✓ Original text length: {len(block.content)}")
    print(f"✓ Encoded text length: {len(segment.text)}")
    print(f"✓ Placeholder count: {len(segment.placeholders)}")
    print(f"\nEncoded text:\n{segment.text}")
    print(f"\nPlaceholders:")
    for ph_id, original in segment.placeholders.items():
        print(f"  {ph_id}: {original}")

    # Verify placeholders exist
    assert len(segment.placeholders) > 0, "No placeholders created"
    assert "<ph id=" in segment.text, "Placeholder tags not in text"

    # Verify specific tokens encoded
    assert "https://example.com" not in segment.text, "URL not encoded"
    assert "contact@example.com" not in segment.text, "Email not encoded"
    assert "[[img-abc123-p0-occ1]]" not in segment.text, "Asset marker not encoded"

    # Verify placeholders can be decoded
    from kps.core.placeholders import decode_placeholders

    decoded = decode_placeholders(segment.text, segment.placeholders)
    assert "https://example.com" in decoded, "URL not restored"
    assert "contact@example.com" in decoded, "Email not restored"
    assert "[[img-abc123-p0-occ1]]" in decoded, "Asset marker not restored"

    print(f"\n✓ Decoding successful")
    print(f"Decoded text:\n{decoded}")


def test_newline_preservation():
    """Test that newlines are preserved exactly."""
    print("\n=== Test 3: Newline Preservation ===")

    # Create block with multiple newlines
    content = "Line 1\nLine 2\n\nLine 4 (after blank)\n\n\nLine 7 (after 2 blanks)"
    original_newline_count = content.count("\n")

    block = ContentBlock(
        block_id="p.gauge.001", block_type=BlockType.PARAGRAPH, content=content
    )

    section = Section(section_type=SectionType.GAUGE, title="Gauge", blocks=[block])

    doc = KPSDocument(
        slug="test-pattern",
        metadata=DocumentMetadata(title="Test Pattern"),
        sections=[section],
    )

    # Segment
    segmenter = Segmenter()
    segments = segmenter.segment_document(doc)

    # Validate
    segment = segments[0]
    encoded_newline_count = segment.text.count("\n")

    print(f"✓ Original newlines: {original_newline_count}")
    print(f"✓ Encoded newlines: {encoded_newline_count}")
    assert (
        original_newline_count == encoded_newline_count
    ), f"Newline count mismatch: {original_newline_count} → {encoded_newline_count}"

    print(f"✓ Newline preservation verified")


def test_multiple_blocks():
    """Test segmentation with multiple blocks across sections."""
    print("\n=== Test 4: Multiple Blocks ===")

    # Create document with multiple sections and blocks
    materials_blocks = [
        ContentBlock(
            block_id="p.materials.001",
            block_type=BlockType.PARAGRAPH,
            content="Yarn: 500g of worsted weight.",
        ),
        ContentBlock(
            block_id="p.materials.002",
            block_type=BlockType.PARAGRAPH,
            content="Needles: US 7 (4.5mm) circular.",
        ),
    ]

    gauge_blocks = [
        ContentBlock(
            block_id="p.gauge.001",
            block_type=BlockType.PARAGRAPH,
            content="20 sts × 28 rows = 4 inches.",
        )
    ]

    doc = KPSDocument(
        slug="test-pattern",
        metadata=DocumentMetadata(title="Test Pattern"),
        sections=[
            Section(
                section_type=SectionType.MATERIALS,
                title="Materials",
                blocks=materials_blocks,
            ),
            Section(section_type=SectionType.GAUGE, title="Gauge", blocks=gauge_blocks),
        ],
    )

    # Segment
    segmenter = Segmenter()
    segments = segmenter.segment_document(doc)

    # Validate
    assert len(segments) == 3, f"Expected 3 segments, got {len(segments)}"

    # Check segment IDs
    expected_ids = [
        "p.materials.001.seg0",
        "p.materials.002.seg1",
        "p.gauge.001.seg2",
    ]

    for i, segment in enumerate(segments):
        assert (
            segment.segment_id == expected_ids[i]
        ), f"Wrong ID at index {i}: {segment.segment_id}"
        print(f"✓ Segment {i}: {segment.segment_id}")

    print(f"✓ Created {len(segments)} segments from {len(doc.sections)} sections")


def test_merge_segments():
    """Test merging translated segments back into document."""
    print("\n=== Test 5: Merge Segments ===")

    # Create original document
    blocks = [
        ContentBlock(
            block_id="p.materials.001",
            block_type=BlockType.PARAGRAPH,
            content="Original text 1",
        ),
        ContentBlock(
            block_id="p.materials.002",
            block_type=BlockType.PARAGRAPH,
            content="Original text 2",
        ),
    ]

    section = Section(
        section_type=SectionType.MATERIALS, title="Materials", blocks=blocks
    )

    original_doc = KPSDocument(
        slug="test-pattern",
        metadata=DocumentMetadata(title="Test Pattern"),
        sections=[section],
    )

    # Segment
    segmenter = Segmenter()
    segments = segmenter.segment_document(original_doc)

    # Simulate translation
    translated_texts = ["Translated text 1", "Translated text 2"]

    # Merge
    merged_doc = segmenter.merge_segments(translated_texts, original_doc)

    # Validate
    assert len(merged_doc.sections) == 1
    assert len(merged_doc.sections[0].blocks) == 2

    assert merged_doc.sections[0].blocks[0].content == "Translated text 1"
    assert merged_doc.sections[0].blocks[1].content == "Translated text 2"

    # Verify original unchanged
    assert original_doc.sections[0].blocks[0].content == "Original text 1"
    assert original_doc.sections[0].blocks[1].content == "Original text 2"

    print(f"✓ Merged {len(translated_texts)} translated segments")
    print(f"✓ Block 0: {merged_doc.sections[0].blocks[0].content}")
    print(f"✓ Block 1: {merged_doc.sections[0].blocks[1].content}")
    print(f"✓ Original document unchanged")


def test_asset_marker_encoding():
    """Test specific encoding of [[asset_id]] markers."""
    print("\n=== Test 6: Asset Marker Encoding ===")

    # Create block with multiple asset markers
    block = ContentBlock(
        block_id="p.instructions.001",
        block_type=BlockType.PARAGRAPH,
        content=(
            "Start with [[img-abc123-p0-occ1]] as shown. "
            "Follow the diagram in [[img-def456-p1-occ1]]. "
            "Reference [[tbl-sizes-p2-occ1]] for measurements."
        ),
    )

    section = Section(
        section_type=SectionType.INSTRUCTIONS, title="Instructions", blocks=[block]
    )

    doc = KPSDocument(
        slug="test-pattern",
        metadata=DocumentMetadata(title="Test Pattern"),
        sections=[section],
    )

    # Segment
    segmenter = Segmenter()
    segments = segmenter.segment_document(doc)

    segment = segments[0]

    print(f"✓ Original text:\n{block.content}")
    print(f"\n✓ Encoded text:\n{segment.text}")
    print(f"\n✓ Placeholders ({len(segment.placeholders)}):")

    # Find asset marker placeholders
    asset_placeholders = {
        k: v for k, v in segment.placeholders.items() if k.startswith("ASSET_")
    }

    print(f"  Asset marker placeholders: {len(asset_placeholders)}")
    for ph_id, original in asset_placeholders.items():
        print(f"    {ph_id}: {original}")

    # Verify all asset markers encoded
    assert len(asset_placeholders) == 3, "Expected 3 asset markers"
    assert "[[img-abc123-p0-occ1]]" not in segment.text, "Asset marker not encoded"
    assert "<ph id=\"ASSET_" in segment.text, "Asset placeholder format incorrect"

    # Verify decoding
    from kps.core.placeholders import decode_placeholders

    decoded = decode_placeholders(segment.text, segment.placeholders)
    assert "[[img-abc123-p0-occ1]]" in decoded, "Asset marker not restored"
    assert "[[img-def456-p1-occ1]]" in decoded, "Asset marker not restored"
    assert "[[tbl-sizes-p2-occ1]]" in decoded, "Asset marker not restored"

    print(f"\n✓ Decoding successful:\n{decoded}")


def run_all_tests():
    """Run all test cases."""
    print("=" * 60)
    print("KPS v2.0 Segmentation Test Suite")
    print("=" * 60)

    try:
        test_basic_segmentation()
        test_placeholder_encoding()
        test_newline_preservation()
        test_multiple_blocks()
        test_merge_segments()
        test_asset_marker_encoding()

        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        raise
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        raise


if __name__ == "__main__":
    run_all_tests()
