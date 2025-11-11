import tempfile
from pathlib import Path

from docx import Document

from kps.extraction.docling_extractor import DoclingExtractor


def _make_docx(tmp_dir: Path) -> Path:
    doc_path = tmp_dir / "sample.docx"
    doc = Document()
    doc.add_paragraph("Sample text")
    doc.save(doc_path)
    return doc_path


def test_extractor_retains_docling_document(tmp_path):
    sample = _make_docx(tmp_path)
    extractor = DoclingExtractor()
    kps_doc = extractor.extract_document(sample, slug="sample")
    assert getattr(kps_doc, "docling_document", None) is not None
    assert extractor.last_docling_document is kps_doc.docling_document
