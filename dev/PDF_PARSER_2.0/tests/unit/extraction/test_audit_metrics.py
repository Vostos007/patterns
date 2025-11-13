from pathlib import Path

from kps.core.document import (
    BlockType,
    ContentBlock,
    DocumentMetadata,
    KPSDocument,
    Section,
    SectionType,
)
from kps.extraction.audit import compare_metrics, compute_metrics


def _make_document(texts):
    section = Section(section_type=SectionType.INSTRUCTIONS, title="Test")
    for idx, text in enumerate(texts, 1):
        section.add_block(
            ContentBlock(
                block_id=f"b{idx}",
                block_type=BlockType.PARAGRAPH,
                content=text,
                doc_ref=f"ref-{idx}" if idx % 2 else None,
            )
        )
    document = KPSDocument(slug="test", metadata=DocumentMetadata(title="Test"), sections=[section])
    return document


def test_compute_metrics_counts_blocks(tmp_path):
    document = _make_document(["a", "b", "c"])
    metrics = compute_metrics(document, source_file=tmp_path / "sample.docx", block_map={"b1": object()})

    assert metrics.sections == 1
    assert metrics.total_blocks == 3
    assert metrics.block_types == {"paragraph": 3}
    assert metrics.doc_refs_with_block == 2
    assert metrics.doc_refs_missing == 1
    assert metrics.docling_block_map == 1


def test_compare_metrics_detects_diff(tmp_path):
    document = _make_document(["a", "b"])
    metrics = compute_metrics(document, source_file=tmp_path / "sample.docx", block_map={})
    baseline = {
        "source_file": str(tmp_path / "sample.docx"),
        "sections": 1,
        "total_blocks": 2,
        "block_types": {"paragraph": 1},
        "doc_refs_with_block": 2,
        "doc_refs_missing": 0,
        "docling_block_map": 0,
    }
    diff = compare_metrics(metrics, baseline)
    assert "block_types" in diff
    assert "doc_refs_with_block" in diff
    assert diff["doc_refs_with_block"]["actual"] == 1
