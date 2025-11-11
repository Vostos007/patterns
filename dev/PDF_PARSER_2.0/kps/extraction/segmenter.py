"""Segmentation utilities converting a :class:`KPSDocument` into segments."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, List

from kps.core.document import ContentBlock, KPSDocument
from kps.core.placeholders import decode_placeholders, encode_placeholders
from kps.translation.orchestrator import TranslationSegment as _TranslationSegment

TranslationSegment = _TranslationSegment

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SegmenterConfig:
    max_segment_length: int = 8_000
    preserve_newlines: bool = True
    placeholder_start_index: int = 1


class Segmenter:
    """Convert structured content blocks into translation segments."""

    def __init__(self, config: SegmenterConfig | None = None) -> None:
        self.config = config or SegmenterConfig()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def segment_document(self, document: KPSDocument) -> List[TranslationSegment]:
        segments: List[TranslationSegment] = []
        for index, block in enumerate(document.iter_blocks()):
            segment = self._segment_block(block, index)
            segments.append(segment)
        self._validate_segments(document, segments)
        return segments

    def segment(self, document: KPSDocument) -> List[TranslationSegment]:
        """Backward compatible alias used by legacy tests."""

        return self.segment_document(document)

    def merge_segments(self, translated_segments: Iterable[str], original: KPSDocument) -> KPSDocument:
        translated_list = list(translated_segments)
        expected = sum(1 for _ in original.iter_blocks())
        if not translated_list:
            raise ValueError("Translated segment list is empty")
        if len(translated_list) != expected:
            raise ValueError(f"Segment count mismatch: expected {expected}, received {len(translated_list)}")

        # Create a mutable copy
        from copy import deepcopy

        merged = deepcopy(original)
        idx = 0
        for block in merged.iter_blocks():
            block.content = translated_list[idx]
            idx += 1
        return merged

    def decode_segments(self, segments: Iterable[TranslationSegment]) -> List[TranslationSegment]:
        decoded: List[TranslationSegment] = []
        for segment in segments:
            decoded.append(
                TranslationSegment(
                    segment_id=segment.segment_id,
                    text=decode_placeholders(segment.text, segment.placeholders),
                    placeholders=segment.placeholders,
                )
            )
        return decoded

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _segment_block(self, block: ContentBlock, index: int) -> TranslationSegment:
        segment_id = f"{block.block_id}.seg{index}"
        encoded_text, placeholders = encode_placeholders(
            block.content, start_index=self.config.placeholder_start_index
        )
        self._ensure_length(segment_id, encoded_text)
        if self.config.preserve_newlines:
            self._assert_newlines(block.content, encoded_text, segment_id)
        return TranslationSegment(segment_id=segment_id, text=encoded_text, placeholders=placeholders)

    def _ensure_length(self, segment_id: str, text: str) -> None:
        if len(text) > self.config.max_segment_length:
            logger.warning(
                "Segment %s exceeds configured max length (%s > %s)",
                segment_id,
                len(text),
                self.config.max_segment_length,
            )

    def _assert_newlines(self, original: str, encoded: str, segment_id: str) -> None:
        original_count = original.count("\n")
        encoded_count = encoded.count("\n")
        if original_count != encoded_count:
            raise ValueError(
                f"Newline preservation failed for {segment_id}: {original_count} → {encoded_count}"
            )

    def _validate_segments(self, document: KPSDocument, segments: List[TranslationSegment]) -> None:
        block_count = sum(1 for _ in document.iter_blocks())
        if block_count != len(segments):
            raise ValueError(f"Segment count mismatch: {len(segments)} vs {block_count}")
        for segment in segments:
            if segment.placeholders is None:
                raise ValueError(f"Segment {segment.segment_id} is missing placeholder mapping")


__all__ = ["Segmenter", "SegmenterConfig", "TranslationSegment"]

