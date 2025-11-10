from src.pdf_pipeline.extractor import PDFBlock, Segment
from src.pdf_pipeline.translator import TranslationPayload, TranslationResult


def test_pipeline_uses_translator_output(tmp_path, monkeypatch):
    blocks = [
        PDFBlock(
            page_number=0,
            block_id=0,
            text="лицевая петля",
            bbox=(0.0, 0.0, 100.0, 20.0),
            font="Lato-Regular",
            font_size=12.0,
            color=(0.0, 0.0, 0.0),
        )
    ]
    segments = [
        Segment(
            page_number=0,
            block_id=0,
            segment_index=0,
            text="лицевая петля",
            placeholders={},
        )
    ]

    monkeypatch.setattr(
        "src.pdf_pipeline.pipeline.extract_pdf_blocks",
        lambda _path: blocks,
    )
    monkeypatch.setattr(
        "src.pdf_pipeline.pipeline.segment_blocks",
        lambda _blocks: segments,
    )

    captured_pdf_texts = {}

    def fake_render_pdf(src_pdf, output_pdf, translated_blocks, translated_texts, language):
        captured_pdf_texts[language] = list(translated_texts)
        output_pdf.write_text("PDF placeholder", encoding="utf-8")

    monkeypatch.setattr(
        "src.pdf_pipeline.pipeline.render_pdf",
        fake_render_pdf,
    )
    monkeypatch.setattr(
        "src.pdf_pipeline.pipeline.render_markdown",
        lambda _slug, _lang, segs: "\n".join(segment.text for segment in segs),
    )

    class FakeTranslator:
        def __init__(self, *_, **__):
            pass

        def translate(self, incoming_segments, doc_slug):
            assert incoming_segments == segments
            return TranslationResult(
                detected_language="ru",
                translations=[
                    TranslationPayload(language="en", segments=["knit stitch (k)"]),
                ],
            )

    monkeypatch.setattr(
        "src.pdf_pipeline.pipeline.TranslationOrchestrator",
        FakeTranslator,
    )

    from src.pdf_pipeline.pipeline import DocumentTranslationPipeline

    input_pdf = tmp_path / "input.pdf"
    input_pdf.write_bytes(b"%PDF-1.4 placeholder")
    output_root = tmp_path / "out"

    pipeline = DocumentTranslationPipeline()
    manifest = pipeline.run(input_pdf, output_root)

    assert manifest.outputs["en"].markdown.read_text(encoding="utf-8").strip().endswith("knit stitch (k)")
    assert captured_pdf_texts["en"] == ["knit stitch (k)"]
