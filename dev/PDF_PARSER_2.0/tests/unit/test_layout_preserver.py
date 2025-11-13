"""Unit tests for layout_preserver."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest

fitz = pytest.importorskip("fitz")

from kps import layout_preserver as lp


def _build_fixture_pdf(path: Path) -> None:
    from PIL import Image

    doc = fitz.open()
    page = doc.new_page(width=420, height=595)
    page.insert_text(
        (72, 72),
        "Merchant Account ID: 123-456\nNotes: Maintain balance thresholds.",
        fontsize=14,
    )
    image_rect = fitz.Rect(72, 220, 132, 280)
    buffer = BytesIO()
    Image.new("RGB", (32, 32), color=(255, 0, 0)).save(buffer, format="PNG")
    buffer.seek(0)
    page.insert_image(image_rect, stream=buffer.getvalue())
    doc.save(path)
    doc.close()


def test_process_pdf_removes_source_text_and_preserves_images(tmp_path, monkeypatch):
    """Translated PDF should drop source text but retain embedded images."""

    sample_pdf = tmp_path / "sample.pdf"
    _build_fixture_pdf(sample_pdf)

    monkeypatch.setattr(lp, "detect_language", lambda _: "en")
    monkeypatch.setattr(lp, "ensure_argos_model", lambda src, tgt: None)
    monkeypatch.setattr(lp, "translate_text", lambda text, src, tgt: f"[{tgt.upper()}] Перевод")

    outputs = lp.process_pdf(sample_pdf, tmp_path / "out", target_langs=["ru"])
    assert len(outputs) == 1

    translated_pdf = outputs[0]
    assert translated_pdf.exists()

    original_doc = fitz.open(sample_pdf)
    original_images = len(original_doc[0].get_images())
    original_doc.close()

    doc = fitz.open(translated_pdf)
    page = doc[0]

    text = page.get_text()
    assert "Merchant Account" not in text
    assert "[RU]" in text
    assert len(page.get_images()) == original_images

    doc.close()


def test_process_pdf_filters_source_language(tmp_path, monkeypatch):
    """Requested source language should be ignored in the output list."""

    sample_pdf = tmp_path / "sample.pdf"
    _build_fixture_pdf(sample_pdf)

    monkeypatch.setattr(lp, "detect_language", lambda _: "en")
    monkeypatch.setattr(lp, "ensure_argos_model", lambda src, tgt: None)
    monkeypatch.setattr(lp, "translate_text", lambda text, src, tgt: f"{tgt}:перевод")

    outputs = lp.process_pdf(sample_pdf, tmp_path / "out", target_langs=["en", "fr"])
    assert len(outputs) == 1
    assert outputs[0].name.endswith("_fr.pdf")


def test_split_translation_by_spans_respects_word_boundaries():
    """Word boundaries should be preserved when splitting translations across spans."""

    # Test case from Russian agreement: "СОГЛАШЕНИЕ О РАСТОРЖЕНИИ" → "AGREEMENT OF TERMINATION"
    # Original has 2 spans with different proportions
    original_spans = [
        {"text": "СОГЛАШЕНИЕ О "},  # 14 chars = 54%
        {"text": "РАСТОРЖЕНИИ "},   # 12 chars = 46%
    ]

    translated = "AGREEMENT OF TERMINATION"  # 24 chars

    result = lp.split_translation_by_spans(original_spans, translated)

    # Check we got 2 parts
    assert len(result) == 2

    # Check no mid-word breaks (all parts should be complete words or start after space)
    for i, part in enumerate(result):
        # Parts should not start/end mid-word (except first/last)
        if i > 0:  # Not first part
            # Should start with a letter (not mid-word)
            assert part[0].isalpha() or part[0].isspace()
        if i < len(result) - 1:  # Not last part
            # Should end with space or complete word
            assert part[-1].isspace() or result[i+1][0].isspace()

    # Reassemble should give original text
    assert "".join(result) == translated

    # Check specific split points are reasonable
    # First part should not end mid-word (e.g., "AGREEMENT OF T")
    # Second part should not start mid-word (e.g., "ERMINATION")

    # Verify that result[0] ends with a complete word or space
    if result[0] and not result[0][-1].isspace():
        # Last word in result[0] should be complete
        last_word_0 = result[0].split()[-1] if result[0].split() else ""
        # Check it's not a fragment of the first word in result[1]
        if result[1] and result[1][0].isalpha():
            first_word_1 = result[1].split()[0] if result[1].split() else result[1]
            # The last word of part 0 shouldn't be a prefix of first word of part 1
            assert not first_word_1.startswith(last_word_0), \
                f"Mid-word break: '{result[0]}' | '{result[1]}'"

    # Verify expected split for this specific test case
    # Should split at "AGREEMENT OF " | "TERMINATION", not "AGREEMENT OF T" | "ERMINATION"
    assert result[0].strip() == "AGREEMENT OF" or result[0] == "AGREEMENT OF ", \
        f"Unexpected split: {result[0]}"
    assert result[1].strip() == "TERMINATION", \
        f"Unexpected split: {result[1]}"


def test_split_translation_by_spans_handles_hyphens():
    """Hyphens should be treated as valid split points."""

    original_spans = [
        {"text": "First part "},   # 50%
        {"text": "Second part"},   # 50%
    ]

    translated = "Well-known multi-word phrase"

    result = lp.split_translation_by_spans(original_spans, translated)

    # Should split near middle, preferably at hyphen or space
    assert len(result) == 2
    assert "".join(result) == translated

    # No mid-word breaks (words like "multi" should not become "mul" + "ti")
    assert "kno" not in result[0] or "wn" not in result[1]  # "known" not split


def test_split_translation_by_spans_single_span():
    """Single span should return entire text unchanged."""

    original_spans = [{"text": "Full text here"}]
    translated = "Complete translated text"

    result = lp.split_translation_by_spans(original_spans, translated)

    assert len(result) == 1
    assert result[0] == translated


def test_split_translation_by_spans_fallback_when_no_boundary():
    """When no word boundary is found in search window, fall back to character split."""

    original_spans = [
        {"text": "A"},   # 50%
        {"text": "B"},   # 50%
    ]

    # Very long word with no spaces
    translated = "Supercalifragilisticexpialidocious"

    result = lp.split_translation_by_spans(original_spans, translated)

    # Should still split somehow (even if mid-word)
    assert len(result) == 2
    assert "".join(result) == translated
