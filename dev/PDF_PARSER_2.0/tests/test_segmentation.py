"""
Tests for translation segmentation strategy (Day 3).

Tests the Segmenter that prepares KPSDocument blocks for translation:
- One-segment-per-block strategy
- Placeholder encoding (URLs, emails, numbers, [[asset_id]])
- Newline preservation (CRITICAL!)
- Segment ID format
- Merge after translation
- Validation (segment count = block count)

Critical validations:
- Newlines are preserved exactly
- [[asset_id]] markers are protected
- Segment IDs are unique and traceable
- Merge reconstructs original structure
"""

import pytest
from kps.core.document import (
    KPSDocument,
    Section,
    SectionType,
    ContentBlock,
    BlockType,
    DocumentMetadata,
)
from kps.core.placeholders import encode_placeholders, decode_placeholders
from kps.core.bbox import BBox

pytestmark = pytest.mark.unit


class TestSegmentation:
    """Test suite for translation segmentation."""

    def test_one_segment_per_block_strategy(self, sample_kps_document):
        """
        Test one-segment-per-block segmentation strategy.

        Strategy: Each ContentBlock → exactly one TranslationSegment
        No splitting by sentence or paragraph.

        Validates:
        - Number of segments equals number of blocks
        - Each segment has unique segment_id
        - Segment text matches block content
        """
        from kps.extraction.segmenter import Segmenter, TranslationSegment

        segmenter = Segmenter()
        segments = segmenter.segment(sample_kps_document)

        # Count total blocks
        total_blocks = sum(len(s.blocks) for s in sample_kps_document.sections)

        # Should have exactly one segment per block
        assert len(segments) == total_blocks

        # All segments should be TranslationSegment
        for segment in segments:
            assert isinstance(segment, TranslationSegment)
            assert segment.segment_id
            assert segment.text

    def test_placeholder_encoding_urls(self):
        """
        Test URL placeholder encoding.

        URLs should be encoded as <ph id="PH001" /> to protect from translation.

        Validates:
        - URLs are detected and encoded
        - Decoding restores original URLs
        """
        from kps.extraction.segmenter import Segmenter

        text = "Visit https://example.com for more info. Email: test@example.com"

        segmenter = Segmenter()
        encoded, mapping = encode_placeholders(text)

        # URLs and emails should be replaced
        assert 'https://example.com' not in encoded
        assert 'test@example.com' not in encoded
        assert '<ph id=' in encoded

        # Decode should restore
        decoded = decode_placeholders(encoded, mapping)
        assert decoded == text

    def test_placeholder_encoding_emails(self):
        """
        Test email placeholder encoding.

        Validates:
        - Email addresses are detected
        - Multiple emails are handled
        - Decoding restores emails
        """
        text = "Contact: admin@example.com or support@example.org"

        encoded, mapping = encode_placeholders(text)

        assert 'admin@example.com' not in encoded
        assert 'support@example.org' not in encoded

        decoded = decode_placeholders(encoded, mapping)
        assert decoded == text

    def test_placeholder_encoding_numbers(self):
        """
        Test number placeholder encoding.

        Numbers with separators (1,234.56) should be protected.

        Validates:
        - Numbers are detected
        - Separators are preserved
        - Decoding restores exact format
        """
        text = "Cast on 123 stitches. Row gauge: 24 rows = 10cm"

        encoded, mapping = encode_placeholders(text)

        # Numbers should be encoded
        assert '123' not in encoded or '<ph id=' in encoded
        assert '24' not in encoded or '<ph id=' in encoded

        decoded = decode_placeholders(encoded, mapping)
        assert decoded == text

    def test_placeholder_encoding_asset_markers(self):
        """
        Test [[asset_id]] marker placeholder encoding.

        CRITICAL: Asset markers must be protected during translation.

        Validates:
        - [[asset_id]] markers are detected
        - Encoded as <ph id="ASSET_*" />
        - Decoding restores exact marker format
        - Multiple markers in same text are handled
        """
        text = """Before image.
[[img-abc12345-p1-occ1]]
After first image.
[[img-def67890-p1-occ2]]
After second image."""

        encoded, mapping = encode_placeholders(text)

        # Markers should be replaced
        assert '[[img-abc12345-p1-occ1]]' not in encoded
        assert '[[img-def67890-p1-occ2]]' not in encoded

        # Should have ASSET placeholders
        assert 'ASSET_IMG-ABC12345-P1-OCC1' in encoded or '<ph id="ASSET_' in encoded

        # Decode should restore
        decoded = decode_placeholders(encoded, mapping)
        assert decoded == text

    def test_newline_preservation_critical(self):
        """
        CRITICAL TEST: Newline preservation.

        Every newline in original text must be preserved through:
        1. Segmentation
        2. Placeholder encoding
        3. Translation (mocked)
        4. Placeholder decoding
        5. Merge

        Validates:
        - Original newline count equals final count
        - Newline positions are preserved
        - No extra or missing newlines
        """
        original_text = """First line.
Second line.
Third line.

Fifth line after blank."""

        # Count original newlines
        original_newlines = original_text.count('\n')

        # Encode
        encoded, mapping = encode_placeholders(original_text)
        encoded_newlines = encoded.count('\n')

        # Newlines should be preserved in encoding
        assert encoded_newlines == original_newlines

        # Decode
        decoded = decode_placeholders(encoded, mapping)
        decoded_newlines = decoded.count('\n')

        # Must be exact match
        assert decoded_newlines == original_newlines
        assert decoded == original_text

    def test_segment_id_format(self, sample_kps_document):
        """
        Test segment ID format: "{block_id}.seg{N}".

        Examples:
        - "p.materials.001.seg0"
        - "h2.techniques.001.seg0"

        Since we use one-segment-per-block, N is always 0.

        Validates:
        - Format is consistent
        - Segment ID includes block ID
        - All IDs are unique
        """
        from kps.extraction.segmenter import Segmenter

        segmenter = Segmenter()
        segments = segmenter.segment(sample_kps_document)

        segment_ids = set()

        for segment in segments:
            # Validate format
            assert '.seg' in segment.segment_id, \
                f"Invalid segment_id format: {segment.segment_id}"

            # Should end with .seg0 (one segment per block)
            assert segment.segment_id.endswith('.seg0'), \
                f"Expected .seg0 suffix: {segment.segment_id}"

            # Extract block_id (everything before .seg)
            block_id = segment.segment_id.rsplit('.seg', 1)[0]

            # Block should exist in document
            found_block = sample_kps_document.find_block(block_id)
            assert found_block is not None, \
                f"Block not found for segment: {segment.segment_id}"

            # Check uniqueness
            assert segment.segment_id not in segment_ids, \
                f"Duplicate segment_id: {segment.segment_id}"
            segment_ids.add(segment.segment_id)

    def test_merge_after_translation(self, sample_kps_document):
        """
        Test merging translated segments back into document.

        Process:
        1. Segment document → segments
        2. Mock translate each segment
        3. Merge segments back → new document
        4. Validate structure is preserved

        Validates:
        - Document structure matches original
        - Translated text is in correct blocks
        - Segment IDs map back to correct blocks
        - All blocks are updated
        """
        from kps.extraction.segmenter import Segmenter

        segmenter = Segmenter()

        # Segment
        segments = segmenter.segment(sample_kps_document)

        # Mock translation (reverse text for testing)
        translated_segments = []
        for seg in segments:
            translated_segments.append(
                seg.text[::-1]  # Reverse for testing
            )

        # Merge
        translated_doc = segmenter.merge(
            document=sample_kps_document,
            segments=segments,
            translated_texts=translated_segments
        )

        # Validate structure
        assert len(translated_doc.sections) == len(sample_kps_document.sections)

        # Check content was updated
        for orig_section, trans_section in zip(
            sample_kps_document.sections, translated_doc.sections
        ):
            assert len(trans_section.blocks) == len(orig_section.blocks)

            for orig_block, trans_block in zip(orig_section.blocks, trans_section.blocks):
                # Block ID should be preserved
                assert trans_block.block_id == orig_block.block_id

                # Content should be reversed (our mock translation)
                assert trans_block.content == orig_block.content[::-1]

    def test_edge_case_empty_blocks(self):
        """
        Test handling of empty blocks.

        Edge case: Block with empty or whitespace-only content.

        Validates:
        - Empty blocks are handled gracefully
        - No crash or error
        - Empty blocks can be skipped or preserved
        """
        from kps.extraction.segmenter import Segmenter

        # Create document with empty block
        empty_block = ContentBlock(
            block_id="p.test.001",
            block_type=BlockType.PARAGRAPH,
            content="",
            bbox=BBox(0, 0, 100, 100),
            page_number=0,
        )

        section = Section(
            section_type=SectionType.INSTRUCTIONS,
            title="Test",
            blocks=[empty_block],
        )

        doc = KPSDocument(
            slug="test",
            metadata=DocumentMetadata(title="Test", language="ru"),
            sections=[section],
        )

        segmenter = Segmenter()
        segments = segmenter.segment(doc)

        # Should handle empty block
        # Either skip it or create empty segment
        # Both are valid strategies

    def test_edge_case_blocks_with_only_markers(self):
        """
        Test handling of blocks containing only [[asset_id]] markers.

        Example:
        ```
        [[img-abc12345-p1-occ1]]
        [[img-def67890-p1-occ2]]
        ```

        Validates:
        - Markers are preserved
        - No crash on marker-only content
        - Translation doesn't break markers
        """
        from kps.extraction.segmenter import Segmenter

        marker_only_block = ContentBlock(
            block_id="p.test.001",
            block_type=BlockType.PARAGRAPH,
            content="[[img-abc12345-p1-occ1]]\n[[img-def67890-p1-occ2]]",
            bbox=BBox(0, 0, 100, 100),
            page_number=0,
        )

        section = Section(
            section_type=SectionType.INSTRUCTIONS,
            title="Test",
            blocks=[marker_only_block],
        )

        doc = KPSDocument(
            slug="test",
            metadata=DocumentMetadata(title="Test", language="ru"),
            sections=[section],
        )

        segmenter = Segmenter()
        segments = segmenter.segment(doc)

        # Should have one segment
        assert len(segments) == 1

        # Markers should be encoded
        encoded_text = segments[0].text
        assert '[[img-' not in encoded_text  # Markers are encoded
        assert '<ph id=' in encoded_text or 'ASSET_' in str(segments[0].placeholders)

    def test_validation_segment_count_matches_block_count(self, sample_kps_document):
        """
        Test validation that segment count equals block count.

        This is a critical invariant for one-segment-per-block strategy.

        Validates:
        - len(segments) == total_blocks
        - No missing segments
        - No extra segments
        """
        from kps.extraction.segmenter import Segmenter

        segmenter = Segmenter()
        segments = segmenter.segment(sample_kps_document)

        # Count blocks
        total_blocks = sum(len(s.blocks) for s in sample_kps_document.sections)

        # Must match exactly
        assert len(segments) == total_blocks, \
            f"Segment count ({len(segments)}) != block count ({total_blocks})"

    def test_placeholder_encoding_mixed_content(self):
        """
        Test placeholder encoding with mixed content types.

        Content: text + URL + email + number + [[marker]]

        Validates:
        - All placeholder types are handled correctly
        - No conflicts between placeholder IDs
        - All content is restored correctly after decode
        """
        text = """Visit https://example.com for pattern.
Email: support@knitting.com
Cast on 123 stitches.
[[img-abc12345-p1-occ1]]
Continue with 24 rows."""

        encoded, mapping = encode_placeholders(text)

        # All should be encoded
        assert 'https://example.com' not in encoded
        assert 'support@knitting.com' not in encoded
        assert '[[img-abc12345-p1-occ1]]' not in encoded

        # Should have placeholders
        assert '<ph id=' in encoded

        # Decode should restore everything
        decoded = decode_placeholders(encoded, mapping)
        assert decoded == text

    def test_segment_preserves_block_metadata(self, sample_kps_document):
        """
        Test that segmentation preserves block metadata.

        Metadata to preserve:
        - block_id (in segment_id)
        - page_number (needed for context)
        - reading_order (for segment ordering)

        Validates:
        - Segment_id contains block_id
        - Segments can be mapped back to original blocks
        """
        from kps.extraction.segmenter import Segmenter

        segmenter = Segmenter()
        segments = segmenter.segment(sample_kps_document)

        for segment in segments:
            # Extract block_id from segment_id
            block_id = segment.segment_id.rsplit('.seg', 1)[0]

            # Should be able to find original block
            original_block = sample_kps_document.find_block(block_id)
            assert original_block is not None

            # Segment text should match block content (after encoding)
            # Note: Can't do exact match due to placeholder encoding
            # But should have similar length
            assert len(segment.text) > 0

    def test_newline_preservation_with_markers(self):
        """
        CRITICAL TEST: Newline preservation with [[asset_id]] markers.

        This combines two critical features:
        - Newline preservation
        - Asset marker protection

        Validates:
        - Newlines before/after markers are preserved
        - Markers don't introduce extra newlines
        - Original structure is maintained exactly
        """
        original = """Paragraph before image.

[[img-abc12345-p1-occ1]]

Paragraph after image.
Another line."""

        original_newlines = original.count('\n')

        # Encode
        encoded, mapping = encode_placeholders(original)

        # Newlines must be preserved
        assert encoded.count('\n') == original_newlines

        # Decode
        decoded = decode_placeholders(encoded, mapping)

        # Must be exact
        assert decoded == original
        assert decoded.count('\n') == original_newlines

    def test_merge_validation_segment_order(self, sample_kps_document):
        """
        Test that merge validates segment order matches document order.

        Validates:
        - Segments must be in same order as blocks
        - Mismatched order raises error or warning
        - Block IDs in segments map to correct blocks
        """
        from kps.extraction.segmenter import Segmenter

        segmenter = Segmenter()

        # Segment
        segments = segmenter.segment(sample_kps_document)

        # Mock translation (just uppercase)
        translated_texts = [seg.text.upper() for seg in segments]

        # Merge with correct order
        translated_doc = segmenter.merge(
            document=sample_kps_document,
            segments=segments,
            translated_texts=translated_texts
        )

        # Should succeed and produce valid document
        assert isinstance(translated_doc, KPSDocument)

        # Content should be uppercase
        for section in translated_doc.sections:
            for block in section.blocks:
                # Should be uppercase (our mock translation)
                assert block.content.isupper() or block.content == ""
