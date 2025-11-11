"""Unit tests for glossary enforcement inside TranslationOrchestrator."""

from unittest.mock import Mock, patch

from kps.translation.orchestrator import TranslationOrchestrator, TranslationSegment
from kps.translation.term_validator import TermRule, TermValidator


def _mock_completion(content: str, prompt_tokens: int = 0, completion_tokens: int = 0):
    """Create a minimal mock compatible with openai.chat.completions.create."""

    choice = Mock()
    choice.message = Mock()
    choice.message.content = content

    response = Mock()
    response.choices = [choice]
    usage = Mock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens
    response.usage = usage
    return response


@patch("kps.translation.orchestrator.openai")
def test_orchestrator_retries_with_structured_outputs(mock_openai):
    """Ensure glossary violations trigger a structured retry before enforcement."""

    # 1) language detection → returns "ru"
    detect_response = _mock_completion("ru")

    # 2) first translation misses required term "Rowan"
    first_translation = _mock_completion(
        content="This yarn is amazing", prompt_tokens=50, completion_tokens=20
    )

    # 3) structured retry returns JSON containing the protected term
    structured_retry = _mock_completion('{"translation": "Rowan yarn instructions"}')

    mock_openai.chat.completions.create.side_effect = [
        detect_response,
        first_translation,
        structured_retry,
    ]

    validator = TermValidator(
        [
            TermRule(
                src_lang="ru",
                tgt_lang="en",
                src="Rowan",
                tgt="Rowan",
                do_not_translate=True,
            )
        ]
    )

    orchestrator = TranslationOrchestrator(term_validator=validator)

    segments = [
        TranslationSegment(
            segment_id="p.demo.seg0",
            text="Пряжа Rowan",
            placeholders={},
        )
    ]

    result = orchestrator.translate_batch(segments, target_languages=["en"])

    translated = result.translations["en"].segments[0]
    assert "Rowan" in translated
    assert mock_openai.chat.completions.create.call_count == 3
