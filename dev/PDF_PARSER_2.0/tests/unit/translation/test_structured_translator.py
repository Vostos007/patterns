"""
Tests for StructuredTranslator with OpenAI Structured Outputs.

Tests the complete validation + retry workflow.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock

from kps.translation.structured_translator import (
    StructuredTranslator,
    StructuredTranslationResult,
)
from kps.translation.term_validator import TermRule, TermValidator
from kps.translation.orchestrator import (
    TranslationOrchestrator,
    BatchTranslationResult,
    TranslationResult,
)


@pytest.fixture
def sample_rules():
    """Create sample glossary rules."""
    return [
        TermRule(
            src_lang="ru",
            tgt_lang="en",
            src="лицевая петля",
            tgt="knit stitch",
            aliases=["k"],
            category="stitch",
        ),
        TermRule(
            src_lang="ru",
            tgt_lang="en",
            src="изнаночная петля",
            tgt="purl stitch",
            aliases=["p"],
            category="stitch",
        ),
    ]


@pytest.fixture
def validator(sample_rules):
    """Create validator with sample rules."""
    return TermValidator(sample_rules)


@pytest.fixture
def mock_orchestrator():
    """Create mock orchestrator."""
    orchestrator = Mock(spec=TranslationOrchestrator)
    orchestrator.model = "gpt-4o-mini"
    return orchestrator


@pytest.fixture
def structured_translator(mock_orchestrator, validator):
    """Create StructuredTranslator."""
    return StructuredTranslator(mock_orchestrator, validator)


class TestStructuredTranslator:
    """Tests for StructuredTranslator class."""

    def test_initialization(self, structured_translator, mock_orchestrator, validator):
        """Test translator initialization."""
        assert structured_translator.orchestrator == mock_orchestrator
        assert structured_translator.validator == validator
        assert structured_translator.max_retries == 2
        assert structured_translator.stats["total_segments"] == 0

    def test_translate_no_violations(self, structured_translator, mock_orchestrator):
        """Test translation with no violations (happy path)."""
        # Mock successful translation
        mock_orchestrator.translate_batch.return_value = BatchTranslationResult(
            detected_source_language="ru",
            translations={
                "en": TranslationResult(
                    target_language="en",
                    segments=["Work a knit stitch"],
                )
            },
        )

        result = structured_translator.translate_with_validation(
            source_text="Провязать лицевую петлю",
            source_lang="ru",
            target_lang="en",
        )

        # Should not need Structured Outputs
        assert result.used_structured_outputs is False
        assert result.retries == 0
        assert len(result.violations_before) == 0
        assert len(result.violations_after) == 0
        assert result.translated_text == "Work a knit stitch"

    def test_translate_with_violations_fixed(
        self, structured_translator, mock_orchestrator
    ):
        """Test translation with violations that get fixed by Structured Outputs."""
        # First call returns bad translation
        mock_orchestrator.translate_batch.return_value = BatchTranslationResult(
            detected_source_language="ru",
            translations={
                "en": TranslationResult(
                    target_language="en",
                    segments=["Work a stitch"],  # Missing "knit"!
                )
            },
        )

        # Mock Structured Outputs to return correct translation
        with patch("kps.translation.structured_translator.openai") as mock_openai:
            mock_client = MagicMock()
            mock_openai.OpenAI.return_value = mock_client

            # Mock the response
            mock_response = MagicMock()
            mock_response.choices[0].message.content = json.dumps(
                {
                    "translation": "Work a knit stitch",  # Fixed!
                    "used_terms": ["knit stitch"],
                }
            )
            mock_client.chat.completions.create.return_value = mock_response

            result = structured_translator.translate_with_validation(
                source_text="Провязать лицевую петлю",
                source_lang="ru",
                target_lang="en",
            )

        # Should have used Structured Outputs and fixed the violation
        assert result.used_structured_outputs is True
        assert result.retries == 1
        assert len(result.violations_before) > 0
        assert len(result.violations_after) == 0
        assert "knit stitch" in result.translated_text

    def test_translate_violations_persist(
        self, structured_translator, mock_orchestrator
    ):
        """Test when Structured Outputs still has violations."""
        # Always return bad translation
        mock_orchestrator.translate_batch.return_value = BatchTranslationResult(
            detected_source_language="ru",
            translations={
                "en": TranslationResult(
                    target_language="en",
                    segments=["Work a stitch"],
                )
            },
        )

        # Mock Structured Outputs to also return bad translation
        with patch("kps.translation.structured_translator.openai") as mock_openai:
            mock_client = MagicMock()
            mock_openai.OpenAI.return_value = mock_client

            mock_response = MagicMock()
            mock_response.choices[0].message.content = json.dumps(
                {
                    "translation": "Work a stitch",  # Still bad!
                    "used_terms": [],
                }
            )
            mock_client.chat.completions.create.return_value = mock_response

            result = structured_translator.translate_with_validation(
                source_text="Провязать лицевую петлю",
                source_lang="ru",
                target_lang="en",
            )

        # Should have tried max_retries times
        assert result.used_structured_outputs is True
        assert result.retries == structured_translator.max_retries
        assert len(result.violations_before) > 0
        # After enforcement, violations might remain (enforcement is basic)
        # But we record them

    def test_build_json_schema(self, structured_translator, sample_rules):
        """Test JSON schema generation."""
        schema = structured_translator._build_json_schema(sample_rules, "en")

        assert schema["type"] == "object"
        assert "translation" in schema["properties"]
        assert "used_terms" in schema["properties"]
        assert "translation" in schema["required"]
        assert schema["additionalProperties"] is False

    def test_build_structured_prompt(self, structured_translator, sample_rules):
        """Test prompt generation for Structured Outputs."""
        prompt = structured_translator._build_structured_prompt(
            source_text="Провязать лицевую петлю",
            source_lang="ru",
            target_lang="en",
            rules=sample_rules,
        )

        assert "MANDATORY GLOSSARY" in prompt
        assert "лицевая петля" in prompt
        assert "knit stitch" in prompt
        assert "JSON" in prompt

    def test_statistics_tracking(self, structured_translator, mock_orchestrator):
        """Test that statistics are tracked correctly."""
        # Process segments with violations
        mock_orchestrator.translate_batch.return_value = BatchTranslationResult(
            detected_source_language="ru",
            translations={
                "en": TranslationResult(
                    target_language="en",
                    segments=["Bad translation"],
                )
            },
        )

        with patch("openai.OpenAI") as mock_openai_class:
            mock_client = MagicMock()
            mock_openai_class.return_value = mock_client

            mock_response = MagicMock()
            mock_response.choices[0].message.content = json.dumps(
                {"translation": "Work a knit stitch", "used_terms": ["knit stitch"]}
            )
            mock_client.chat.completions.create.return_value = mock_response

            # Process one segment
            structured_translator.translate_with_validation(
                source_text="Провязать лицевую петлю",
                source_lang="ru",
                target_lang="en",
            )

        stats = structured_translator.get_statistics()
        assert stats["total_segments"] == 1
        assert stats["segments_with_violations"] == 1
        assert stats["segments_fixed_by_structured"] == 1

    def test_api_error_handling(self, structured_translator, mock_orchestrator):
        """Test handling of API errors."""
        # First call returns bad translation
        mock_orchestrator.translate_batch.return_value = BatchTranslationResult(
            detected_source_language="ru",
            translations={
                "en": TranslationResult(
                    target_language="en",
                    segments=["Bad translation"],
                )
            },
        )

        # Mock API to raise error
        with patch("openai.OpenAI") as mock_openai_class:
            mock_client = MagicMock()
            mock_openai_class.return_value = mock_client
            mock_client.chat.completions.create.side_effect = Exception("API Error")

            result = structured_translator.translate_with_validation(
                source_text="Провязать лицевую петлю",
                source_lang="ru",
                target_lang="en",
            )

        # Should handle error gracefully
        assert result.used_structured_outputs is True
        assert len(result.violations_before) > 0


class TestIntegration:
    """Integration tests for StructuredTranslator."""

    def test_full_workflow_with_fix(self, structured_translator, mock_orchestrator):
        """Test complete workflow: bad → structured → fixed."""
        # STEP 1: Bad translation
        mock_orchestrator.translate_batch.return_value = BatchTranslationResult(
            detected_source_language="ru",
            translations={
                "en": TranslationResult(
                    target_language="en",
                    segments=["Work something"],  # Completely wrong
                )
            },
        )

        # STEP 2: Structured Outputs fixes it
        with patch("openai.OpenAI") as mock_openai_class:
            mock_client = MagicMock()
            mock_openai_class.return_value = mock_client

            mock_response = MagicMock()
            mock_response.choices[0].message.content = json.dumps(
                {
                    "translation": "Work a k, then p",  # Using aliases
                    "used_terms": ["k", "p"],
                }
            )
            mock_client.chat.completions.create.return_value = mock_response

            result = structured_translator.translate_with_validation(
                source_text="Провязать лицевую петлю, затем изнаночную петлю",
                source_lang="ru",
                target_lang="en",
            )

        # Verify workflow
        assert result.used_structured_outputs is True
        assert len(result.violations_before) > 0  # Initial violations
        assert len(result.violations_after) == 0  # Fixed by structured
        assert result.retries == 1

    def test_statistics_accuracy(self, structured_translator, mock_orchestrator):
        """Test that statistics are accurate across multiple calls."""
        # Process 3 segments: 1 perfect, 1 fixed, 1 enforcement

        # Segment 1: Perfect
        mock_orchestrator.translate_batch.return_value = BatchTranslationResult(
            detected_source_language="ru",
            translations={"en": TranslationResult("en", ["Work a knit stitch"])},
        )
        structured_translator.translate_with_validation(
            "Провязать лицевую петлю", "ru", "en"
        )

        # Segment 2: Fixed by Structured Outputs
        mock_orchestrator.translate_batch.return_value = BatchTranslationResult(
            detected_source_language="ru",
            translations={"en": TranslationResult("en", ["Bad translation"])},
        )

        with patch("kps.translation.structured_translator.openai") as mock_openai:
            mock_client = MagicMock()
            mock_openai.OpenAI.return_value = mock_client
            mock_response = MagicMock()
            mock_response.choices[0].message.content = json.dumps(
                {"translation": "Work a k", "used_terms": ["k"]}
            )
            mock_client.chat.completions.create.return_value = mock_response

            structured_translator.translate_with_validation(
                "Провязать лицевую петлю", "ru", "en"
            )

        # Segment 3: Requires enforcement
        mock_orchestrator.translate_batch.return_value = BatchTranslationResult(
            detected_source_language="ru",
            translations={"en": TranslationResult("en", ["Bad translation"])},
        )

        with patch("kps.translation.structured_translator.openai") as mock_openai:
            mock_client = MagicMock()
            mock_openai.OpenAI.return_value = mock_client
            # Always return bad translation
            mock_response = MagicMock()
            mock_response.choices[0].message.content = json.dumps(
                {"translation": "Still bad", "used_terms": []}
            )
            mock_client.chat.completions.create.return_value = mock_response

            structured_translator.translate_with_validation(
                "Провязать лицевую петлю", "ru", "en"
            )

        # Check statistics
        stats = structured_translator.get_statistics()
        assert stats["total_segments"] == 3
        assert stats["segments_with_violations"] == 2
        assert stats["segments_fixed_by_structured"] == 1
        assert stats["segments_requiring_enforcement"] == 1
        assert 0 <= stats["violation_rate"] <= 1
        assert 0 <= stats["fix_rate"] <= 1
