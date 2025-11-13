import pytest

from kps.export.docling_pipeline import (
    export_docx_with_fallback,
    export_markdown_with_fallback,
    export_pdf_with_fallback,
)
from kps.export.html_contract import write_html_document


class _FakeDoclingDoc:
    def __init__(self, html: str = "<p>Hello</p>", markdown: str = "Hello") -> None:
        self._html = html
        self._markdown = markdown

    def export_to_html(self) -> str:  # pragma: no cover - invoked via monkeypatched renderer
        return self._html

    def export_to_markdown(self) -> str:
        return self._markdown


@pytest.fixture()
def fake_doc() -> _FakeDoclingDoc:
    return _FakeDoclingDoc(html="<table><tr><td>1</td></tr></table>", markdown="|ru|en|\n|--|--|")


def test_docling_docx_pipeline_falls_back(monkeypatch, tmp_path, fake_doc):
    out_path = tmp_path / "doc.docx"

    def _fail(*_args, **_kwargs):
        raise RuntimeError("pandoc missing")

    monkeypatch.setattr("kps.export.docling_pipeline.docling_render_docx", _fail)

    def _fallback():
        out_path.write_text("fallback", encoding="utf-8")
        return out_path, "docx-structure"

    result = export_docx_with_fallback(fake_doc, out_path, fallback_builder=_fallback)
    assert result.fallback_used is True
    assert any("Docling DOCX export failed" in msg for msg in result.warnings)
    assert out_path.exists()


def test_docling_markdown_pipeline_primary(monkeypatch, tmp_path, fake_doc):
    out_path = tmp_path / "doc.md"

    def _primary(doc, path):
        path.write_text(doc.export_to_markdown(), encoding="utf-8")

    monkeypatch.setattr(
        "kps.export.docling_pipeline.docling_render_markdown",
        _primary,
    )

    result = export_markdown_with_fallback(fake_doc, out_path)
    assert result.fallback_used is False
    text = out_path.read_text(encoding="utf-8")
    assert "|ru|en|" in text


def test_docling_pdf_pipeline_fallback(monkeypatch, tmp_path, fake_doc):
    out_path = tmp_path / "doc.pdf"

    def _fail_pdf(*_args, **_kwargs):
        raise RuntimeError("weasy missing")

    monkeypatch.setattr(
        "kps.export.docling_pipeline.render_pdf_from_docling",
        _fail_pdf,
    )

    def _fallback_pdf():
        out_path.write_bytes(b"fallback")
        return out_path, "pdf-html"

    result = export_pdf_with_fallback(fake_doc, out_path, fallback_builder=_fallback_pdf)
    assert result.fallback_used is True
    assert out_path.read_bytes() == b"fallback"


def test_docling_html_contract(tmp_path, fake_doc):
    out_path = tmp_path / "doc.html"
    write_html_document(fake_doc, out_path, css_text="body { color: red; }")
    text = out_path.read_text(encoding="utf-8")
    assert "color: red" in text
    assert "<table>" in text
