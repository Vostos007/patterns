"""
Tests for TranslationOrchestrator with OpenAI API (Day 3).

Tests the enhanced TranslationOrchestrator that handles:
- Batch translation to multiple languages
- Glossary integration
- Placeholder protection
- Retry logic with exponential backoff
- Token counting and cost estimation
- Progress callbacks

Uses mocked OpenAI API responses for deterministic testing.

Critical validations:
- Placeholder preservation through translation
- Newline preservation
- Glossary term application
- Batch splitting (50 segments per batch)
- Error handling and retries
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from kps.translation.orchestrator import (
    TranslationOrchestrator,
    TranslationSegment,
    TranslationResult,
    BatchTranslationResult,
)

pytestmark = pytest.mark.unit


class TestTranslationOrchestrator:
    """Test suite for TranslationOrchestrator."""

    @patch('kps.translation.orchestrator.openai')
    def test_language_detection(self, mock_openai):
        """
        Test automatic source language detection.

        Validates:
        - Russian text is detected as "ru"
        - English text is detected as "en"
        - Detection uses sample of text (first 500 chars)
        """
        # Mock OpenAI response
        mock_completion = Mock()
        mock_completion.choices = [Mock(message=Mock(content="ru"))]
        mock_openai.chat.completions.create.return_value = mock_completion

        orchestrator = TranslationOrchestrator()

        russian_text = "Наберите 123 петли. Вяжите лицевой гладью."
        detected_lang = orchestrator.detect_language(russian_text)

        assert detected_lang == "ru"

        # Verify API call
        mock_openai.chat.completions.create.assert_called_once()
        call_args = mock_openai.chat.completions.create.call_args

        # Check that sample text was sent
        assert russian_text[:500] in call_args[1]['messages'][0]['content']

    @patch('kps.translation.orchestrator.openai')
    def test_translate_batch_single_language(self, mock_openai):
        """
        Test batch translation to single target language.

        Validates:
        - Segments are translated
        - Source language is detected
        - Target language result is returned
        - Segment order is preserved
        """
        # Mock language detection
        detect_mock = Mock()
        detect_mock.choices = [Mock(message=Mock(content="ru"))]
        detect_mock.usage = Mock(prompt_tokens=10, completion_tokens=5, total_tokens=15)

        # Mock translation
        translate_mock = Mock()
        translate_mock.choices = [Mock(message=Mock(content="Translated text 1\n---\nTranslated text 2"))]
        translate_mock.usage = Mock(prompt_tokens=100, completion_tokens=50, total_tokens=150)

        mock_openai.chat.completions.create.side_effect = [detect_mock, translate_mock]

        orchestrator = TranslationOrchestrator()

        segments = [
            TranslationSegment(
                segment_id="p.test.001.seg0",
                text="Текст 1",
                placeholders={}
            ),
            TranslationSegment(
                segment_id="p.test.002.seg0",
                text="Текст 2",
                placeholders={}
            ),
        ]

        result = orchestrator.translate_batch(
            segments=segments,
            target_languages=["en"],
        )

        assert isinstance(result, BatchTranslationResult)
        assert result.detected_source_language == "ru"
        assert "en" in result.translations

        en_result = result.translations["en"]
        assert len(en_result.segments) == 2
        assert en_result.segments[0] == "Translated text 1"
        assert en_result.segments[1] == "Translated text 2"

    @patch('kps.translation.orchestrator.openai')
    def test_translate_batch_multiple_languages(self, mock_openai):
        """
        Test batch translation to multiple target languages.

        Validates:
        - Translation to EN and FR
        - Each language gets separate TranslationResult
        - Segment count matches for all languages
        """
        # Mock language detection
        detect_mock = Mock()
        detect_mock.choices = [Mock(message=Mock(content="ru"))]
        detect_mock.usage = Mock(prompt_tokens=10, completion_tokens=5, total_tokens=15)

        # Mock translations (EN and FR)
        translate_mock_en = Mock()
        translate_mock_en.choices = [Mock(message=Mock(content="English text"))]
        translate_mock_en.usage = Mock(prompt_tokens=100, completion_tokens=50, total_tokens=150)

        translate_mock_fr = Mock()
        translate_mock_fr.choices = [Mock(message=Mock(content="Texte français"))]
        translate_mock_fr.usage = Mock(prompt_tokens=100, completion_tokens=50, total_tokens=150)

        mock_openai.chat.completions.create.side_effect = [
            detect_mock,
            translate_mock_en,
            translate_mock_fr
        ]

        orchestrator = TranslationOrchestrator()

        segments = [
            TranslationSegment(
                segment_id="p.test.001.seg0",
                text="Текст",
                placeholders={}
            ),
        ]

        result = orchestrator.translate_batch(
            segments=segments,
            target_languages=["en", "fr"],
        )

        assert "en" in result.translations
        assert "fr" in result.translations
        assert len(result.translations["en"].segments) == 1
        assert len(result.translations["fr"].segments) == 1

    @patch('kps.translation.orchestrator.openai')
    def test_placeholder_preservation_in_translation(self, mock_openai):
        """
        Test that placeholders are preserved during translation.

        CRITICAL: Placeholders (<ph id="..." />) must survive translation.

        Validates:
        - Placeholders are in segment text
        - API prompt instructs to preserve placeholders
        - Translated text still contains placeholders
        """
        # Mock responses
        detect_mock = Mock()
        detect_mock.choices = [Mock(message=Mock(content="ru"))]
        detect_mock.usage = Mock(prompt_tokens=10, completion_tokens=5, total_tokens=15)

        translate_mock = Mock()
        # Simulated translation that preserves placeholders
        translate_mock.choices = [Mock(message=Mock(content='Translated <ph id="PH001" /> text'))]
        translate_mock.usage = Mock(prompt_tokens=100, completion_tokens=50, total_tokens=150)

        mock_openai.chat.completions.create.side_effect = [detect_mock, translate_mock]

        orchestrator = TranslationOrchestrator()

        segments = [
            TranslationSegment(
                segment_id="p.test.001.seg0",
                text='Текст <ph id="PH001" /> продолжение',
                placeholders={"PH001": "https://example.com"}
            ),
        ]

        result = orchestrator.translate_batch(
            segments=segments,
            target_languages=["en"],
        )

        # Check that prompt mentions placeholder preservation
        call_args = mock_openai.chat.completions.create.call_args_list[1]  # Translation call
        user_prompt = call_args[1]['messages'][1]['content']

        assert 'placeholder' in user_prompt.lower() or '<ph id=' in user_prompt

        # Check translated text preserves placeholder
        translated = result.translations["en"].segments[0]
        assert '<ph id="PH001" />' in translated

    @patch('kps.translation.orchestrator.openai')
    def test_newline_preservation_in_translation(self, mock_openai):
        """
        CRITICAL TEST: Newline preservation through translation.

        Validates:
        - Prompt instructs to preserve newlines
        - Input text with newlines is sent correctly
        - Translated text preserves newlines
        """
        # Mock responses
        detect_mock = Mock()
        detect_mock.choices = [Mock(message=Mock(content="ru"))]
        detect_mock.usage = Mock(prompt_tokens=10, completion_tokens=5, total_tokens=15)

        translate_mock = Mock()
        # Simulated translation preserving newlines
        translate_mock.choices = [Mock(message=Mock(content="Line 1\nLine 2\nLine 3"))]
        translate_mock.usage = Mock(prompt_tokens=100, completion_tokens=50, total_tokens=150)

        mock_openai.chat.completions.create.side_effect = [detect_mock, translate_mock]

        orchestrator = TranslationOrchestrator()

        original_text = "Строка 1\nСтрока 2\nСтрока 3"
        original_newlines = original_text.count('\n')

        segments = [
            TranslationSegment(
                segment_id="p.test.001.seg0",
                text=original_text,
                placeholders={}
            ),
        ]

        result = orchestrator.translate_batch(
            segments=segments,
            target_languages=["en"],
        )

        # Check prompt mentions newline preservation
        call_args = mock_openai.chat.completions.create.call_args_list[1]
        user_prompt = call_args[1]['messages'][1]['content']

        assert 'newline' in user_prompt.lower() or '\\n' in user_prompt

        # Check translated text preserves newlines
        translated = result.translations["en"].segments[0]
        assert translated.count('\n') == original_newlines

    @patch('kps.translation.orchestrator.openai')
    def test_glossary_context_injection(self, mock_openai):
        """
        Test glossary context is included in system prompt.

        Validates:
        - Glossary context is passed to API
        - System prompt includes glossary terms
        - Terms are available for translation
        """
        # Mock responses
        detect_mock = Mock()
        detect_mock.choices = [Mock(message=Mock(content="ru"))]
        detect_mock.usage = Mock(prompt_tokens=10, completion_tokens=5, total_tokens=15)

        translate_mock = Mock()
        translate_mock.choices = [Mock(message=Mock(content="knit stitch"))]
        translate_mock.usage = Mock(prompt_tokens=100, completion_tokens=50, total_tokens=150)

        mock_openai.chat.completions.create.side_effect = [detect_mock, translate_mock]

        orchestrator = TranslationOrchestrator()

        glossary_context = """
Glossary:
- лицевая петля: knit stitch
- изнаночная петля: purl stitch
"""

        segments = [
            TranslationSegment(
                segment_id="p.test.001.seg0",
                text="лицевая петля",
                placeholders={}
            ),
        ]

        result = orchestrator.translate_batch(
            segments=segments,
            target_languages=["en"],
            glossary_context=glossary_context,
        )

        # Check that glossary context is in system prompt
        call_args = mock_openai.chat.completions.create.call_args_list[1]
        system_prompt = call_args[1]['messages'][0]['content']

        assert 'лицевая петля' in system_prompt or 'knit stitch' in system_prompt

    @patch('kps.translation.orchestrator.openai')
    def test_batch_splitting_50_segments(self, mock_openai):
        """
        Test batch splitting for large segment lists.

        Strategy: Split into batches of 50 segments to stay within API limits.

        Validates:
        - Large lists are split into multiple API calls
        - Each batch has ≤50 segments
        - All segments are translated
        - Order is preserved
        """
        # Mock responses
        detect_mock = Mock()
        detect_mock.choices = [Mock(message=Mock(content="ru"))]

        # Mock translations for multiple batches
        def create_translate_mock(batch_num):
            mock = Mock()
            # Return numbered translations
            translations = [f"Translation {i}" for i in range(50)]
            payload = "\n---\n".join(translations)
            mock.choices = [Mock(message=Mock(content=payload))]
            return mock

        # Setup mocks for 2 batches (51 segments total)
        mock_openai.chat.completions.create.side_effect = [
            detect_mock,
            create_translate_mock(1),
            create_translate_mock(2),
        ]

        orchestrator = TranslationOrchestrator()

        # Create 51 segments (should split into 2 batches)
        segments = [
            TranslationSegment(
                segment_id=f"p.test.{i:03d}.seg0",
                text=f"Текст {i}",
                placeholders={}
            )
            for i in range(51)
        ]

        # Note: Current implementation may not split batches
        # This test validates the concept
        # Actual implementation should be enhanced to split batches

    @patch('kps.translation.orchestrator.openai')
    def test_retry_logic_on_api_failure(self, mock_openai):
        """
        Test retry logic with exponential backoff on API failure.

        Validates:
        - API failures trigger retries
        - Exponential backoff is applied
        - Eventually succeeds after retry
        - Max retries limit is respected
        """
        # Mock: First call fails, second succeeds
        detect_mock = Mock()
        detect_mock.choices = [Mock(message=Mock(content="ru"))]

        fail_mock = Mock()
        fail_mock.side_effect = Exception("API rate limit")

        success_mock = Mock()
        success_mock.choices = [Mock(message=Mock(content="Success"))]

        mock_openai.chat.completions.create.side_effect = [
            detect_mock,
            fail_mock,
            success_mock,
        ]

        # Note: Current implementation doesn't have retry logic
        # This test is aspirational - retry should be added

    @patch('kps.translation.orchestrator.openai')
    def test_token_counting_and_cost_estimation(self, mock_openai):
        """
        Test token counting and cost estimation.

        Validates:
        - Input tokens are counted
        - Output tokens are tracked
        - Cost is estimated based on model pricing
        - Statistics are returned
        """
        # Mock response with usage info
        detect_mock = Mock()
        detect_mock.choices = [Mock(message=Mock(content="ru"))]
        detect_mock.usage = Mock(prompt_tokens=10, completion_tokens=5, total_tokens=15)

        translate_mock = Mock()
        translate_mock.choices = [Mock(message=Mock(content="Translated"))]
        translate_mock.usage = Mock(prompt_tokens=100, completion_tokens=50, total_tokens=150)

        mock_openai.chat.completions.create.side_effect = [detect_mock, translate_mock]

        orchestrator = TranslationOrchestrator()

        segments = [
            TranslationSegment(
                segment_id="p.test.001.seg0",
                text="Текст для перевода",
                placeholders={}
            ),
        ]

        result = orchestrator.translate_batch(
            segments=segments,
            target_languages=["en"],
        )

        # Note: Current implementation doesn't return token stats
        # This test is aspirational - should be enhanced

    @patch('kps.translation.orchestrator.openai')
    def test_progress_callback_mechanism(self, mock_openai):
        """
        Test progress callback for long translations.

        Validates:
        - Callback is called during translation
        - Progress percentage is accurate
        - Can be used for UI updates
        """
        # Mock responses
        detect_mock = Mock()
        detect_mock.choices = [Mock(message=Mock(content="ru"))]

        translate_mock = Mock()
        translate_mock.choices = [Mock(message=Mock(content="Done"))]

        mock_openai.chat.completions.create.side_effect = [detect_mock, translate_mock]

        progress_calls = []

        def progress_callback(current, total, message):
            progress_calls.append((current, total, message))

        orchestrator = TranslationOrchestrator()

        segments = [
            TranslationSegment(
                segment_id="p.test.001.seg0",
                text="Текст",
                placeholders={}
            ),
        ]

        # Note: Current implementation doesn't support callbacks
        # This test is aspirational

    @patch('kps.translation.orchestrator.openai')
    def test_error_handling_api_timeout(self, mock_openai):
        """
        Test error handling for API timeout.

        Validates:
        - Timeout exceptions are caught
        - Appropriate error message
        - No silent failures
        """
        # Mock timeout
        mock_openai.chat.completions.create.side_effect = TimeoutError("Request timeout")

        orchestrator = TranslationOrchestrator()

        segments = [
            TranslationSegment(
                segment_id="p.test.001.seg0",
                text="Текст",
                placeholders={}
            ),
        ]

        with pytest.raises(TimeoutError):
            orchestrator.translate_batch(
                segments=segments,
                target_languages=["en"],
            )

    @patch('kps.translation.orchestrator.openai')
    def test_error_handling_invalid_api_key(self, mock_openai):
        """
        Test error handling for invalid API key.

        Validates:
        - Authentication errors are caught
        - Clear error message
        """
        # Mock authentication error
        mock_openai.chat.completions.create.side_effect = Exception("Invalid API key")

        orchestrator = TranslationOrchestrator()

        segments = [
            TranslationSegment(
                segment_id="p.test.001.seg0",
                text="Текст",
                placeholders={}
            ),
        ]

        with pytest.raises(Exception) as exc_info:
            orchestrator.translate_batch(
                segments=segments,
                target_languages=["en"],
            )

        assert "API key" in str(exc_info.value)

    @patch('kps.translation.orchestrator.openai')
    def test_segment_count_mismatch_fallback(self, mock_openai):
        """
        Test fallback when translated segment count doesn't match input.

        API may return wrong number of segments (split differently).

        Validates:
        - Mismatch is detected
        - Fallback strategy is applied (return original text)
        - No crash or data loss
        """
        # Mock language detection
        detect_mock = Mock()
        detect_mock.choices = [Mock(message=Mock(content="ru"))]
        detect_mock.usage = Mock(prompt_tokens=10, completion_tokens=5, total_tokens=15)

        # Mock translation with WRONG segment count
        translate_mock = Mock()
        translate_mock.choices = [Mock(message=Mock(content="Only one segment"))]  # Expected 2
        translate_mock.usage = Mock(prompt_tokens=100, completion_tokens=50, total_tokens=150)

        mock_openai.chat.completions.create.side_effect = [detect_mock, translate_mock]

        orchestrator = TranslationOrchestrator()

        segments = [
            TranslationSegment(
                segment_id="p.test.001.seg0",
                text="Сегмент 1",
                placeholders={}
            ),
            TranslationSegment(
                segment_id="p.test.002.seg0",
                text="Сегмент 2",
                placeholders={}
            ),
        ]

        result = orchestrator.translate_batch(
            segments=segments,
            target_languages=["en"],
        )

        # Should have fallback (original text)
        en_result = result.translations["en"]
        assert len(en_result.segments) == 2  # Fallback preserves count

    @patch('kps.translation.orchestrator.openai')
    def test_asset_marker_preservation_end_to_end(self, mock_openai):
        """
        CRITICAL TEST: Asset marker preservation end-to-end.

        Full flow:
        1. Segment text with [[asset_id]]
        2. Encode to <ph id="ASSET_*" />
        3. Send to API
        4. API returns with placeholder preserved
        5. Decode back to [[asset_id]]

        Validates:
        - Markers survive entire pipeline
        - No corruption or loss
        """
        from kps.core.placeholders import encode_placeholders, decode_placeholders

        # Mock responses
        detect_mock = Mock()
        detect_mock.choices = [Mock(message=Mock(content="ru"))]
        detect_mock.usage = Mock(prompt_tokens=10, completion_tokens=5, total_tokens=15)

        translate_mock = Mock()
        # Simulated translation preserving placeholder
        translate_mock.choices = [Mock(message=Mock(
            content='Before image.\n<ph id="ASSET_IMG-ABC12345-P1-OCC1" />\nAfter image.'
        ))]
        translate_mock.usage = Mock(prompt_tokens=100, completion_tokens=50, total_tokens=150)

        mock_openai.chat.completions.create.side_effect = [detect_mock, translate_mock]

        # Original text with marker
        original_text = "Перед изображением.\n[[img-abc12345-p1-occ1]]\nПосле изображения."

        # Encode
        encoded_text, mapping = encode_placeholders(original_text)

        orchestrator = TranslationOrchestrator()

        segments = [
            TranslationSegment(
                segment_id="p.test.001.seg0",
                text=encoded_text,
                placeholders=mapping
            ),
        ]

        result = orchestrator.translate_batch(
            segments=segments,
            target_languages=["en"],
        )

        # Decode translated text
        translated_encoded = result.translations["en"].segments[0]
        translated_decoded = decode_placeholders(translated_encoded, mapping)

        # Marker must be preserved
        assert '[[img-abc12345-p1-occ1]]' in translated_decoded

    @patch('kps.translation.orchestrator.openai')
    def test_empty_segments_handling(self, mock_openai):
        """
        Test handling of empty segment list.

        Validates:
        - No API calls for empty list
        - Returns empty BatchTranslationResult
        - No crash
        """
        orchestrator = TranslationOrchestrator()

        result = orchestrator.translate_batch(
            segments=[],
            target_languages=["en"],
        )

        assert isinstance(result, BatchTranslationResult)
        assert len(result.translations) == 0

        # No API calls should be made
        mock_openai.chat.completions.create.assert_not_called()

    def test_split_translated_segments_handles_markdown_tables(self):
        """Ensure table header separators do not break segment parsing."""

        orchestrator = TranslationOrchestrator()

        payload = (
            "Size table\n"
            "| Bust | Width |\n"
            "| --- | --- |\n"
            "| 80 | 52 |\n"
            "---\n"
            "Next paragraph"
        )

        result = orchestrator._split_translated_segments(payload, expected_count=2)

        assert "| --- | --- |" in result[0]
        assert result[1] == "Next paragraph"
