"""Extraction QA helpers for Docling outputs."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional

from kps.core.document import KPSDocument, ContentBlock


@dataclass
class ExtractionMetrics:
    source_file: str
    sections: int
    total_blocks: int
    block_types: Dict[str, int]
    doc_refs_with_block: int
    doc_refs_missing: int
    docling_block_map: int

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def _iter_blocks(document: KPSDocument) -> Iterable[ContentBlock]:
    for section in document.sections:
        for block in section.blocks:
            yield block


def compute_metrics(
    document: KPSDocument,
    *,
    source_file: Path,
    block_map: Optional[Mapping[str, object]] = None,
) -> ExtractionMetrics:
    block_counter: Counter[str] = Counter()
    doc_refs_with_block = 0
    doc_refs_missing = 0

    for block in _iter_blocks(document):
        block_counter[block.block_type.value] += 1
        if block.doc_ref:
            doc_refs_with_block += 1
        else:
            doc_refs_missing += 1

    total_blocks = sum(block_counter.values())
    block_map_size = len(block_map or {})

    return ExtractionMetrics(
        source_file=str(source_file.resolve()),
        sections=len(document.sections),
        total_blocks=total_blocks,
        block_types=dict(block_counter),
        doc_refs_with_block=doc_refs_with_block,
        doc_refs_missing=doc_refs_missing,
        docling_block_map=block_map_size,
    )


def compare_metrics(current: ExtractionMetrics, baseline: Mapping[str, object], *, tolerance: int = 0) -> Dict[str, object]:
    """Compare metrics to a baseline, returning dictionary of differences."""

    current_dict = current.to_dict()
    diffs: Dict[str, object] = {}

    for key, current_value in current_dict.items():
        expected_value = baseline.get(key)
        if expected_value is None:
            diffs[key] = {"expected": None, "actual": current_value}
            continue

        if key == "source_file":
            try:
                from pathlib import Path

                current_name = Path(current_value).name
                expected_name = Path(expected_value).name
            except Exception:
                current_name = current_value
                expected_name = expected_value

            if current_name == expected_name:
                continue

        if isinstance(current_value, dict) and isinstance(expected_value, dict):
            nested_diff = compare_metrics_dict(current_value, expected_value, tolerance)
            if nested_diff:
                diffs[key] = nested_diff
        elif isinstance(current_value, int) and isinstance(expected_value, (int, float, list)):
            if not _int_matches(current_value, expected_value, tolerance):
                diffs[key] = {"expected": expected_value, "actual": current_value}
        else:
            if not _values_match(current_value, expected_value):
                diffs[key] = {"expected": expected_value, "actual": current_value}

    return diffs


def compare_metrics_dict(
    current: Mapping[str, int],
    baseline: Mapping[str, int],
    tolerance: int,
) -> Dict[str, Dict[str, int]]:
    diffs: Dict[str, Dict[str, int]] = {}
    keys = set(current.keys()) | set(baseline.keys())
    for key in keys:
        current_value = current.get(key, 0)
        expected_value = baseline.get(key, 0)
        if not _int_matches(current_value, expected_value, tolerance):
            diffs[key] = {"expected": expected_value, "actual": current_value}
    return diffs


def _int_matches(current: int, expected: object, tolerance: int) -> bool:
    """Check if current integer matches expected integer/list within tolerance."""
    if isinstance(expected, list):
        return any(_int_matches(current, value, tolerance) for value in expected)
    if isinstance(expected, (int, float)):
        return abs(current - int(expected)) <= tolerance
    return False


def _values_match(current: object, expected: object) -> bool:
    """Check value equality, treating lists as alternatives."""
    if isinstance(expected, list):
        return any(_values_match(current, value) for value in expected)
    return current == expected


def write_metrics(metrics: ExtractionMetrics, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(metrics.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


__all__ = [
    "ExtractionMetrics",
    "compute_metrics",
    "compare_metrics",
    "write_metrics",
]
