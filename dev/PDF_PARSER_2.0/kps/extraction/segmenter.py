"""
Text segmentation with placeholder encoding for KPS v2.0.

Prepares ContentBlocks for translation by:
1. Creating one segment per ContentBlock (no splitting)
2. Encoding fragile tokens (URLs, emails, numbers, [[asset_id]])
3. Preserving all newlines (critical for layout)
4. Generating unique segment IDs for tracking
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from ..core.document import ContentBlock, KPSDocument
from ..core.placeholders import encode_placeholders, decode_placeholders
from ..translation.orchestrator import TranslationSegment


@dataclass
class SegmenterConfig:
    """Configuration for text segmentation."""

    max_segment_length: int = 8000  # API token limit safety margin
    preserve_newlines: bool = True  # Always preserve (critical for layout)
    placeholder_start_index: int = 1  # Starting index for placeholders


class Segmenter:
    """
    Text segmenter with placeholder encoding for translation.

    Strategy: One segment per ContentBlock (no splitting within blocks).
    This preserves document structure and simplifies reconstruction.

    Encoding handles:
    - URLs (http://, https://)
    - Email addresses (user@example.com)
    - Numbers with separators (123,456.78)
    - [[asset_id]] markers (NEW in KPS v2.0)
    """

    def __init__(self, config: SegmenterConfig | None = None):
        """
        Initialize segmenter.

        Args:
            config: Optional configuration. Uses defaults if None.
        """
        self.config = config or SegmenterConfig()

    def segment_document(self, document: KPSDocument) -> List[TranslationSegment]:
        """
        Segment document into translation-ready segments.

        Each ContentBlock becomes one segment with encoded placeholders.

        Args:
            document: KPSDocument with ContentBlocks (after marker injection)

        Returns:
            List of TranslationSegment objects with encoded placeholders
        """
        segments: List[TranslationSegment] = []
        segment_counter = 0

        for section in document.sections:
            for block in section.blocks:
                # Create segment from block
                segment = self._segment_block(block, segment_counter)
                segments.append(segment)
                segment_counter += 1

        # Validate
        self._validate_segments(segments, document)

        return segments

    def _segment_block(
        self, block: ContentBlock, segment_index: int
    ) -> TranslationSegment:
        """
        Create a translation segment from a single ContentBlock.

        Segment ID format: {block_id}.seg{index}
        Example: "p.materials.001.seg0"

        Args:
            block: ContentBlock to segment
            segment_index: Global segment index for unique ID

        Returns:
            TranslationSegment with encoded text and placeholders
        """
        # Generate segment ID
        segment_id = f"{block.block_id}.seg{segment_index}"

        # Encode text with placeholders
        encoded_text, placeholders = self._encode_block_text(block.content)

        # Validate length
        if len(encoded_text) > self.config.max_segment_length:
            # Log warning but don't fail (API can handle slightly over)
            print(
                f"Warning: Segment {segment_id} length {len(encoded_text)} "
                f"exceeds max {self.config.max_segment_length}"
            )

        return TranslationSegment(
            segment_id=segment_id, text=encoded_text, placeholders=placeholders
        )

    def _encode_block_text(self, text: str) -> Tuple[str, Dict[str, str]]:
        """
        Encode fragile tokens in text as placeholders.

        Wrapper around core.placeholders.encode_placeholders() with
        segmentation-specific logic.

        Encodes:
        - URLs (http://, https://...)
        - Email addresses (user@example.com)
        - Numbers with separators (123,456.78)
        - [[asset_id]] markers (e.g., [[img-abc123-p0-occ1]])

        Args:
            text: Raw text from ContentBlock

        Returns:
            Tuple of (encoded_text, placeholder_mapping)
            where placeholder_mapping is {placeholder_id: original_value}

        Example:
            Input:  "Visit https://example.com or [[img-abc-p0-occ1]] for details."
            Output: ("Visit <ph id=\"PH001\" /> or <ph id=\"ASSET_IMG_ABC_P0_OCC1\" /> for details.",
                    {"PH001": "https://example.com",
                     "ASSET_IMG_ABC_P0_OCC1": "[[img-abc-p0-occ1]]"})
        """
        if not text:
            return text, {}

        # Use existing placeholder encoding from core
        encoded_text, placeholders = encode_placeholders(
            text, start_index=self.config.placeholder_start_index
        )

        # Validate newlines preserved (if enabled)
        if self.config.preserve_newlines:
            original_newlines = text.count("\n")
            encoded_newlines = encoded_text.count("\n")
            if original_newlines != encoded_newlines:
                raise ValueError(
                    f"Newline preservation failed: "
                    f"original={original_newlines}, encoded={encoded_newlines}"
                )

        return encoded_text, placeholders

    def merge_segments(
        self, translated_segments: List[str], original_document: KPSDocument
    ) -> KPSDocument:
        """
        Reconstruct document after translation.

        Takes translated segments (with placeholders still encoded) and
        merges them back into the original document structure, then
        decodes placeholders.

        Args:
            translated_segments: List of translated texts (same order as segment_document())
            original_document: Original KPSDocument for structure reference

        Returns:
            New KPSDocument with translated content
        """
        if not translated_segments:
            raise ValueError("Empty translated segments list")

        # Count expected segments
        expected_count = sum(len(section.blocks) for section in original_document.sections)

        if len(translated_segments) != expected_count:
            raise ValueError(
                f"Segment count mismatch: expected {expected_count}, "
                f"got {len(translated_segments)}"
            )

        # Create new document with same structure
        from copy import deepcopy

        merged_doc = deepcopy(original_document)

        # Merge segments back into blocks
        segment_idx = 0
        for section in merged_doc.sections:
            for block in section.blocks:
                if segment_idx >= len(translated_segments):
                    raise ValueError(
                        f"Ran out of translated segments at block {block.block_id}"
                    )

                # Replace block content with translated text
                block.content = translated_segments[segment_idx]
                segment_idx += 1

        return merged_doc

    def decode_segments(
        self, segments: List[TranslationSegment]
    ) -> List[TranslationSegment]:
        """
        Decode placeholders in translated segments.

        This is a convenience method for post-translation processing.
        Typically called after translation but before merging.

        Args:
            segments: List of segments with encoded placeholders in text

        Returns:
            List of segments with decoded text
        """
        decoded_segments = []

        for segment in segments:
            decoded_text = decode_placeholders(segment.text, segment.placeholders)

            decoded_segment = TranslationSegment(
                segment_id=segment.segment_id,
                text=decoded_text,
                placeholders=segment.placeholders,  # Keep for reference
            )
            decoded_segments.append(decoded_segment)

        return decoded_segments

    def _validate_segments(
        self, segments: List[TranslationSegment], document: KPSDocument
    ) -> None:
        """
        Validate segmentation results.

        Checks:
        1. Segment count matches block count
        2. All segments have placeholders mapping
        3. Newlines preserved (if enabled)

        Args:
            segments: Generated segments
            document: Source document

        Raises:
            ValueError: If validation fails
        """
        # Count blocks in document
        total_blocks = sum(len(section.blocks) for section in document.sections)

        # Check count
        if len(segments) != total_blocks:
            raise ValueError(
                f"Segment count mismatch: {len(segments)} segments "
                f"vs {total_blocks} blocks"
            )

        # Check placeholders
        for segment in segments:
            if segment.placeholders is None:
                raise ValueError(
                    f"Segment {segment.segment_id} has None placeholders "
                    "(should be empty dict if no placeholders)"
                )

        # Validate newlines preserved (if enabled)
        if self.config.preserve_newlines:
            segment_idx = 0
            for section in document.sections:
                for block in section.blocks:
                    if segment_idx >= len(segments):
                        break

                    segment = segments[segment_idx]
                    original_newlines = block.content.count("\n")
                    segment_newlines = segment.text.count("\n")

                    if original_newlines != segment_newlines:
                        raise ValueError(
                            f"Newline preservation failed for {segment.segment_id}: "
                            f"original={original_newlines}, segment={segment_newlines}"
                        )

                    segment_idx += 1


__all__ = ["Segmenter", "SegmenterConfig"]
