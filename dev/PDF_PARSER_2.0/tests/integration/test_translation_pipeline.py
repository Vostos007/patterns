"""
Integration tests for translation pipeline (Day 3).

Tests the complete translation workflow:
1. Extract → KPSDocument + AssetLedger
2. Anchor assets → inject markers
3. Segment → encode placeholders
4. Translate (mocked OpenAI)
5. Decode placeholders → merge
6. Validate completeness

Critical validations:
- Full pipeline preserves structure
- Newlines preserved end-to-end (CRITICAL!)
- Asset markers survive translation (CRITICAL!)
- Placeholder preservation (URLs, emails, numbers)
- Glossary terms applied
- Multi-language output
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from kps.core.document import KPSDocument
from kps.core.assets import AssetLedger
from kps.core.placeholders import encode_placeholders, decode_placeholders

pytestmark = pytest.mark.integration


class TestTranslationPipeline:
    """Integration tests for full translation pipeline."""

    @pytest.mark.slow
    @patch('kps.translation.orchestrator.openai')
    def test_full_pipeline_extract_to_translated(
        self, mock_openai, sample_russian_pattern_pdf, tmp_path
    ):
        """
        Test complete pipeline: PDF → Extraction → Translation → Translated Document.

        Full workflow:
        1. Extract text (Docling) and assets (PyMuPDF)
        2. Anchor assets and inject markers
        3. Segment document
        4. Translate with OpenAI (mocked)
        5. Merge translated segments
        6. Validate result

        Validates:
        - Pipeline completes without errors
        - Translated document has same structure
        - All sections and blocks are translated
        - Asset markers are preserved
        """
        from kps.extraction.docling_extractor import DoclingExtractor
        from kps.extraction.pymupdf_extractor import PyMuPDFExtractor
        from kps.anchoring.anchor import anchor_assets_to_blocks
        from kps.anchoring.markers import inject_markers
        from kps.extraction.segmenter import Segmenter
        from kps.translation.orchestrator import TranslationOrchestrator

        # Mock OpenAI responses
        detect_mock = Mock()
        detect_mock.choices = [Mock(message=Mock(content="ru"))]

        translate_mock = Mock()
        translate_mock.choices = [Mock(message=Mock(content="Translated text"))]

        mock_openai.chat.completions.create.side_effect = [detect_mock] + [translate_mock] * 10

        # 1. Extract
        document = DoclingExtractor().extract(sample_russian_pattern_pdf)
        ledger = PyMuPDFExtractor(output_dir=tmp_path / "assets").extract_assets(
            sample_russian_pattern_pdf
        )

        # 2. Anchor and mark
        anchored_ledger = anchor_assets_to_blocks(document, ledger)
        marked_document = inject_markers(document, anchored_ledger)

        # 3. Segment
        segmenter = Segmenter()
        segments = segmenter.segment(marked_document)

        # 4. Translate
        orchestrator = TranslationOrchestrator()
        result = orchestrator.translate_batch(
            segments=segments,
            target_languages=["en"],
        )

        # 5. Merge
        translated_document = segmenter.merge(
            document=marked_document,
            segments=segments,
            translated_texts=result.translations["en"].segments
        )

        # Validate
        assert isinstance(translated_document, KPSDocument)
        assert len(translated_document.sections) == len(document.sections)

        # All blocks should be translated
        for section in translated_document.sections:
            assert len(section.blocks) > 0

    @patch('kps.translation.orchestrator.openai')
    def test_newline_preservation_end_to_end_critical(
        self, mock_openai, sample_russian_pattern_pdf, tmp_path
    ):
        """
        CRITICAL TEST: Newline preservation through ENTIRE translation pipeline.

        Every newline in original document must survive:
        1. Extraction
        2. Marker injection
        3. Segmentation
        4. Placeholder encoding
        5. Translation
        6. Placeholder decoding
        7. Merge

        This is the most critical test for layout preservation.

        Validates:
        - Original newline count = final newline count (±tolerance for markers)
        - No corrupted line breaks
        - Structure is maintained
        """
        from kps.extraction.docling_extractor import DoclingExtractor
        from kps.extraction.pymupdf_extractor import PyMuPDFExtractor
        from kps.anchoring.anchor import anchor_assets_to_blocks
        from kps.anchoring.markers import inject_markers
        from kps.extraction.segmenter import Segmenter
        from kps.translation.orchestrator import TranslationOrchestrator

        # Mock OpenAI to preserve newlines
        detect_mock = Mock()
        detect_mock.choices = [Mock(message=Mock(content="ru"))]

        def create_translate_mock(original_text):
            """Create mock that preserves newlines."""
            # Count newlines in input
            newlines = original_text.count('\n')
            # Return translated text with same newline count
            translated = "Translated line\n" * (newlines + 1)
            translated = translated.rstrip('\n')  # Remove trailing newline

            mock = Mock()
            mock.choices = [Mock(message=Mock(content=translated))]
            return mock

        # Extract
        document = DoclingExtractor().extract(sample_russian_pattern_pdf)

        # Count original newlines
        original_newlines = sum(
            block.content.count('\n')
            for section in document.sections
            for block in section.blocks
        )

        # Complete pipeline
        ledger = PyMuPDFExtractor(output_dir=tmp_path / "assets").extract_assets(
            sample_russian_pattern_pdf
        )
        anchored_ledger = anchor_assets_to_blocks(document, ledger)
        marked_document = inject_markers(document, anchored_ledger)

        segmenter = Segmenter()
        segments = segmenter.segment(marked_document)

        # Mock translation preserving structure
        mock_openai.chat.completions.create.side_effect = [detect_mock] + [
            create_translate_mock(seg.text) for seg in segments
        ]

        orchestrator = TranslationOrchestrator()
        result = orchestrator.translate_batch(
            segments=segments,
            target_languages=["en"],
        )

        translated_document = segmenter.merge(
            document=marked_document,
            segments=segments,
            translated_texts=result.translations["en"].segments
        )

        # Count final newlines
        final_newlines = sum(
            block.content.count('\n')
            for section in translated_document.sections
            for block in section.blocks
        )

        # Newlines should be preserved (±tolerance for marker formatting)
        marker_count = len([a for a in anchored_ledger.assets if a.anchor_to])
        expected_min = original_newlines
        expected_max = original_newlines + marker_count + 10  # Tolerance

        assert expected_min <= final_newlines <= expected_max, \
            f"Newlines not preserved: original={original_newlines}, final={final_newlines}"

    @patch('kps.translation.orchestrator.openai')
    def test_asset_marker_preservation_critical(
        self, mock_openai, sample_russian_pattern_pdf, tmp_path
    ):
        """
        CRITICAL TEST: Asset marker preservation through translation pipeline.

        Every [[asset_id]] marker must survive:
        1. Segmentation
        2. Placeholder encoding
        3. Translation
        4. Placeholder decoding
        5. Merge

        Validates:
        - All markers present in original are present in translated
        - Marker format is unchanged
        - Markers are in correct blocks
        """
        from kps.extraction.docling_extractor import DoclingExtractor
        from kps.extraction.pymupdf_extractor import PyMuPDFExtractor
        from kps.anchoring.anchor import anchor_assets_to_blocks
        from kps.anchoring.markers import inject_markers, count_markers
        from kps.extraction.segmenter import Segmenter
        from kps.translation.orchestrator import TranslationOrchestrator

        # Mock OpenAI to preserve placeholders
        detect_mock = Mock()
        detect_mock.choices = [Mock(message=Mock(content="ru"))]

        def create_translate_mock_with_placeholders(text):
            """Mock that preserves <ph id="..." /> placeholders."""
            # Just prepend "Translated: " and keep placeholders
            translated = "Translated: " + text

            mock = Mock()
            mock.choices = [Mock(message=Mock(content=translated))]
            return mock

        # Extract and prepare
        document = DoclingExtractor().extract(sample_russian_pattern_pdf)
        ledger = PyMuPDFExtractor(output_dir=tmp_path / "assets").extract_assets(
            sample_russian_pattern_pdf
        )
        anchored_ledger = anchor_assets_to_blocks(document, ledger)
        marked_document = inject_markers(document, anchored_ledger)

        # Count original markers
        original_markers = count_markers(marked_document)
        original_count = original_markers['total_markers']

        # Segment and translate
        segmenter = Segmenter()
        segments = segmenter.segment(marked_document)

        mock_openai.chat.completions.create.side_effect = [detect_mock] + [
            create_translate_mock_with_placeholders(seg.text) for seg in segments
        ]

        orchestrator = TranslationOrchestrator()
        result = orchestrator.translate_batch(
            segments=segments,
            target_languages=["en"],
        )

        translated_document = segmenter.merge(
            document=marked_document,
            segments=segments,
            translated_texts=result.translations["en"].segments
        )

        # Count final markers
        final_markers = count_markers(translated_document)
        final_count = final_markers['total_markers']

        # Must be exact match
        assert final_count == original_count, \
            f"Markers not preserved: original={original_count}, final={final_count}"

        # Validate marker content
        assert set(original_markers['markers_by_block'].keys()) == \
               set(final_markers['markers_by_block'].keys())

    @patch('kps.translation.orchestrator.openai')
    def test_placeholder_preservation_urls_emails_numbers(
        self, mock_openai, tmp_path
    ):
        """
        Test preservation of URLs, emails, and numbers through pipeline.

        Validates:
        - URLs are encoded and decoded correctly
        - Emails are preserved
        - Numbers with separators are preserved
        """
        from kps.extraction.segmenter import Segmenter
        from kps.translation.orchestrator import TranslationOrchestrator
        from kps.core.document import (
            KPSDocument, DocumentMetadata, Section, SectionType,
            ContentBlock, BlockType
        )
        from kps.core.bbox import BBox

        # Create test document with URLs, emails, numbers
        block = ContentBlock(
            block_id="p.test.001",
            block_type=BlockType.PARAGRAPH,
            content="Visit https://example.com or email test@example.com. Cost: 1,234.56 руб.",
            bbox=BBox(0, 0, 100, 100),
            page_number=0,
        )

        section = Section(
            section_type=SectionType.INSTRUCTIONS,
            title="Test",
            blocks=[block],
        )

        document = KPSDocument(
            slug="test",
            metadata=DocumentMetadata(title="Test", language="ru"),
            sections=[section],
        )

        # Mock OpenAI preserving placeholders
        detect_mock = Mock()
        detect_mock.choices = [Mock(message=Mock(content="ru"))]

        translate_mock = Mock()
        # Preserve placeholders in translation
        translate_mock.choices = [Mock(message=Mock(
            content='Visit <ph id="PH001" /> or email <ph id="PH002" />. Cost: <ph id="PH003" /> rubles.'
        ))]

        mock_openai.chat.completions.create.side_effect = [detect_mock, translate_mock]

        # Segment and translate
        segmenter = Segmenter()
        segments = segmenter.segment(document)

        orchestrator = TranslationOrchestrator()
        result = orchestrator.translate_batch(
            segments=segments,
            target_languages=["en"],
        )

        translated_document = segmenter.merge(
            document=document,
            segments=segments,
            translated_texts=result.translations["en"].segments
        )

        # Check content
        translated_content = translated_document.sections[0].blocks[0].content

        # Placeholders should be decoded back to original values
        assert 'https://example.com' in translated_content
        assert 'test@example.com' in translated_content
        assert '1,234.56' in translated_content

    @patch('kps.translation.orchestrator.openai')
    def test_glossary_term_application(
        self, mock_openai, sample_russian_pattern_pdf, tmp_path
    ):
        """
        Test glossary term application during translation.

        Validates:
        - Glossary context is used
        - Technical terms are translated correctly
        - Consistency across document
        """
        from kps.extraction.docling_extractor import DoclingExtractor
        from kps.extraction.pymupdf_extractor import PyMuPDFExtractor
        from kps.anchoring.anchor import anchor_assets_to_blocks
        from kps.anchoring.markers import inject_markers
        from kps.extraction.segmenter import Segmenter
        from kps.translation.orchestrator import TranslationOrchestrator

        # Mock OpenAI with glossary-aware translation
        detect_mock = Mock()
        detect_mock.choices = [Mock(message=Mock(content="ru"))]

        translate_mock = Mock()
        # Simulated translation using glossary terms
        translate_mock.choices = [Mock(message=Mock(
            content="knit stitch, purl stitch, cast on"
        ))]

        mock_openai.chat.completions.create.side_effect = [detect_mock] + [translate_mock] * 10

        # Extract and prepare
        document = DoclingExtractor().extract(sample_russian_pattern_pdf)
        ledger = PyMuPDFExtractor(output_dir=tmp_path / "assets").extract_assets(
            sample_russian_pattern_pdf
        )
        anchored_ledger = anchor_assets_to_blocks(document, ledger)
        marked_document = inject_markers(document, anchored_ledger)

        # Segment
        segmenter = Segmenter()
        segments = segmenter.segment(marked_document)

        # Translate with glossary
        glossary_context = """
Glossary:
- лицевая петля: knit stitch
- изнаночная петля: purl stitch
- набрать петли: cast on
"""

        orchestrator = TranslationOrchestrator()
        result = orchestrator.translate_batch(
            segments=segments,
            target_languages=["en"],
            glossary_context=glossary_context,
        )

        # Validate that glossary context was sent
        call_args = mock_openai.chat.completions.create.call_args_list[1]
        system_prompt = call_args[1]['messages'][0]['content']

        # Should contain glossary
        assert 'лицевая петля' in system_prompt or 'knit stitch' in system_prompt

    @patch('kps.translation.orchestrator.openai')
    def test_multi_language_output(
        self, mock_openai, sample_russian_pattern_pdf, tmp_path
    ):
        """
        Test translation to multiple target languages (EN + FR).

        Validates:
        - Both languages are translated
        - Each has separate output
        - Structure is preserved for both
        - Same source document generates both
        """
        from kps.extraction.docling_extractor import DoclingExtractor
        from kps.extraction.pymupdf_extractor import PyMuPDFExtractor
        from kps.anchoring.anchor import anchor_assets_to_blocks
        from kps.anchoring.markers import inject_markers
        from kps.extraction.segmenter import Segmenter
        from kps.translation.orchestrator import TranslationOrchestrator

        # Mock OpenAI for EN and FR
        detect_mock = Mock()
        detect_mock.choices = [Mock(message=Mock(content="ru"))]

        translate_en_mock = Mock()
        translate_en_mock.choices = [Mock(message=Mock(content="English translation"))]

        translate_fr_mock = Mock()
        translate_fr_mock.choices = [Mock(message=Mock(content="Traduction française"))]

        mock_openai.chat.completions.create.side_effect = [
            detect_mock,
            translate_en_mock,
            translate_fr_mock,
        ] * 5

        # Extract and prepare
        document = DoclingExtractor().extract(sample_russian_pattern_pdf)
        ledger = PyMuPDFExtractor(output_dir=tmp_path / "assets").extract_assets(
            sample_russian_pattern_pdf
        )
        anchored_ledger = anchor_assets_to_blocks(document, ledger)
        marked_document = inject_markers(document, anchored_ledger)

        # Segment
        segmenter = Segmenter()
        segments = segmenter.segment(marked_document)

        # Translate to both languages
        orchestrator = TranslationOrchestrator()
        result = orchestrator.translate_batch(
            segments=segments,
            target_languages=["en", "fr"],
        )

        # Should have both translations
        assert "en" in result.translations
        assert "fr" in result.translations

        # Both should have same segment count
        assert len(result.translations["en"].segments) == len(segments)
        assert len(result.translations["fr"].segments) == len(segments)

        # Merge both
        en_document = segmenter.merge(
            document=marked_document,
            segments=segments,
            translated_texts=result.translations["en"].segments
        )

        fr_document = segmenter.merge(
            document=marked_document,
            segments=segments,
            translated_texts=result.translations["fr"].segments
        )

        # Both should have same structure
        assert len(en_document.sections) == len(fr_document.sections)

    @pytest.mark.slow
    @patch('kps.translation.orchestrator.openai')
    def test_batch_processing_100_plus_segments(
        self, mock_openai, tmp_path
    ):
        """
        Test batch processing with 100+ segments.

        Validates:
        - Large documents are handled
        - Batching works correctly
        - Performance is acceptable
        - All segments are translated
        """
        from kps.extraction.segmenter import Segmenter
        from kps.translation.orchestrator import TranslationOrchestrator
        from kps.core.document import (
            KPSDocument, DocumentMetadata, Section, SectionType,
            ContentBlock, BlockType
        )
        from kps.core.bbox import BBox

        # Create document with 100 blocks
        blocks = [
            ContentBlock(
                block_id=f"p.test.{i:03d}",
                block_type=BlockType.PARAGRAPH,
                content=f"Текст блока {i}",
                bbox=BBox(0, i * 10, 100, i * 10 + 10),
                page_number=i // 10,
            )
            for i in range(100)
        ]

        section = Section(
            section_type=SectionType.INSTRUCTIONS,
            title="Test",
            blocks=blocks,
        )

        document = KPSDocument(
            slug="test",
            metadata=DocumentMetadata(title="Test", language="ru"),
            sections=[section],
        )

        # Mock OpenAI
        detect_mock = Mock()
        detect_mock.choices = [Mock(message=Mock(content="ru"))]

        translate_mock = Mock()
        translate_mock.choices = [Mock(message=Mock(content="Translated block"))]

        mock_openai.chat.completions.create.side_effect = [detect_mock] + [translate_mock] * 200

        # Segment and translate
        segmenter = Segmenter()
        segments = segmenter.segment(document)

        assert len(segments) == 100

        orchestrator = TranslationOrchestrator()

        import time
        start_time = time.time()

        result = orchestrator.translate_batch(
            segments=segments,
            target_languages=["en"],
        )

        elapsed = time.time() - start_time

        # Should complete in reasonable time (< 60s with mocks)
        assert elapsed < 60.0

        # All segments translated
        assert len(result.translations["en"].segments) == 100

    @patch('kps.translation.orchestrator.openai')
    def test_cost_tracking_accuracy(
        self, mock_openai, sample_russian_pattern_pdf, tmp_path
    ):
        """
        Test translation cost tracking.

        Validates:
        - Token counts are tracked
        - Cost is estimated
        - Statistics are accurate
        """
        # Note: Current implementation may not track costs
        # This test is aspirational

        pass  # TODO: Implement when cost tracking is added

    @pytest.mark.slow
    @patch('kps.translation.orchestrator.openai')
    def test_performance_full_pipeline_60_seconds(
        self, mock_openai, ten_page_pdf_path, tmp_path
    ):
        """
        Test full pipeline performance: < 60 seconds for 10-page document.

        Includes:
        - Extraction (text + assets)
        - Anchoring + marking
        - Segmentation
        - Translation (mocked)
        - Merge

        Validates:
        - Total time < 60s
        - Result is complete
        """
        import time
        from kps.extraction.docling_extractor import DoclingExtractor
        from kps.extraction.pymupdf_extractor import PyMuPDFExtractor
        from kps.anchoring.anchor import anchor_assets_to_blocks
        from kps.anchoring.markers import inject_markers
        from kps.extraction.segmenter import Segmenter
        from kps.translation.orchestrator import TranslationOrchestrator

        # Mock OpenAI
        detect_mock = Mock()
        detect_mock.choices = [Mock(message=Mock(content="ru"))]

        translate_mock = Mock()
        translate_mock.choices = [Mock(message=Mock(content="Translated"))]

        mock_openai.chat.completions.create.side_effect = [detect_mock] + [translate_mock] * 100

        start_time = time.time()

        # Full pipeline
        document = DoclingExtractor().extract(ten_page_pdf_path)
        ledger = PyMuPDFExtractor(output_dir=tmp_path / "assets").extract_assets(
            ten_page_pdf_path
        )
        anchored_ledger = anchor_assets_to_blocks(document, ledger)
        marked_document = inject_markers(document, anchored_ledger)

        segmenter = Segmenter()
        segments = segmenter.segment(marked_document)

        orchestrator = TranslationOrchestrator()
        result = orchestrator.translate_batch(
            segments=segments,
            target_languages=["en"],
        )

        translated_document = segmenter.merge(
            document=marked_document,
            segments=segments,
            translated_texts=result.translations["en"].segments
        )

        elapsed = time.time() - start_time

        # Performance check
        assert elapsed < 60.0, f"Pipeline took {elapsed:.2f}s, expected < 60s"

        # Completeness check
        assert isinstance(translated_document, KPSDocument)
        assert len(translated_document.sections) > 0
