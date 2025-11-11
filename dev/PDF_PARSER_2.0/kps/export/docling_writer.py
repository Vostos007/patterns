"""Utilities for writing translations back into a DoclingDocument."""

from __future__ import annotations

from copy import deepcopy
from typing import List, Sequence, Tuple

from docling_core.types.doc import TextItem
from docling_core.types.doc.document import DoclingDocument

from kps.translation.orchestrator import TranslationSegment

DoclingWriteResult = Tuple[DoclingDocument, List[str]]


def apply_translations(
    docling_document: DoclingDocument,
    segments: Sequence[TranslationSegment],
    translated_texts: Sequence[str],
) -> DoclingWriteResult:
    """Return a new DoclingDocument with translated text injected.

    Args:
        docling_document: Source Docling document returned by extractor.
        segments: Segments produced by the segmenter (must align in order).
        translated_texts: Final translated text for each segment.

    Returns:
        Tuple of (new_docling_document, missing_segment_ids)
    """

    if len(segments) != len(translated_texts):
        raise ValueError(
            "Segment count mismatch: "
            f"{len(segments)} segments vs {len(translated_texts)} translations"
        )

    updated = deepcopy(docling_document)
    missing: List[str] = []

    for segment, translated in zip(segments, translated_texts):
        doc_ref = segment.doc_ref
        if not doc_ref:
            missing.append(segment.segment_id)
            continue

        node = _resolve_pointer(updated, doc_ref)
        if node is None or not hasattr(node, "text"):
            missing.append(segment.segment_id)
            continue

        node.text = translated

    return updated, missing


def _resolve_pointer(docling_document: DoclingDocument, pointer: str):
    """Resolve a JSON pointer-like cref such as `#/texts/0` into the document tree."""

    if not pointer.startswith("#/"):
        return None

    parts = [part for part in pointer[2:].split("/") if part]
    current = docling_document

    for part in parts:
        if isinstance(current, list):
            try:
                index = int(part)
                current = current[index]
            except (ValueError, IndexError):
                return None
            continue

        if isinstance(current, DoclingDocument) and hasattr(current, part):
            current = getattr(current, part)
            continue

        if hasattr(current, part):
            current = getattr(current, part)
            continue

        return None

    return current


__all__ = ["apply_translations"]
