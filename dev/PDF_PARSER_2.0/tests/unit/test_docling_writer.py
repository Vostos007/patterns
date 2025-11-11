from docling_core.types.doc import TextItem
from docling_core.types.doc.document import DoclingDocument

from kps.export.docling_writer import apply_translations
from kps.translation.orchestrator import TranslationSegment


def _sample_doc() -> DoclingDocument:
    doc = DoclingDocument(name="sample")
    doc.texts = [
        TextItem.model_construct(
            self_ref="#/texts/0",
            label="paragraph",
            orig="Original",
            text="Original",
        )
    ]
    return doc


def test_apply_translations_updates_text_nodes():
    doc = _sample_doc()
    segments = [
        TranslationSegment(
            segment_id="p.cover.001.seg0",
            text="Original",
            placeholders={},
            doc_ref="#/texts/0",
        )
    ]
    updated, missing = apply_translations(doc, segments, ["Translated"])
    assert missing == []
    assert updated.texts[0].text == "Translated"
    # Original document should remain untouched
    assert doc.texts[0].text == "Original"


def test_apply_translations_tracks_missing_refs():
    doc = _sample_doc()
    segments = [
        TranslationSegment(
            segment_id="p.cover.002.seg0",
            text="Original",
            placeholders={},
            doc_ref="#/texts/99",
        )
    ]
    _, missing = apply_translations(doc, segments, ["Translated"])
    assert missing == ["p.cover.002.seg0"]
