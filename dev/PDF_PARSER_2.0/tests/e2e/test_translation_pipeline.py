"""End-to-end smoke test for translation orchestrator + QA gate."""

from unittest.mock import Mock, patch

from kps.translation.orchestrator import TranslationOrchestrator, TranslationSegment
from kps.translation.term_validator import TermRule, TermValidator
from kps.qa.translation_qa import TranslationQAGate


def _mock_completion(content: str) -> Mock:
    choice = Mock()
    choice.message = Mock()
    choice.message.content = content

    response = Mock()
    response.choices = [choice]
    usage = Mock()
    usage.prompt_tokens = 10
    usage.completion_tokens = 10
    response.usage = usage
    return response


@patch("kps.translation.orchestrator.openai")
def test_translation_pipeline_translates_and_passes_qa(mock_openai):
    # Detect language (ru) then translate to en
    mock_openai.chat.completions.create.side_effect = [
        _mock_completion("ru"),
        _mock_completion("Use Rowan yarn for this instruction"),
    ]

    validator = TermValidator([
        TermRule("ru", "en", "Rowan", "Rowan", do_not_translate=True),
    ])
    orchestrator = TranslationOrchestrator(term_validator=validator)
    segment = TranslationSegment(
        segment_id="p.demo.seg0",
        text="Используйте пряжу Rowan",
        placeholders={},
    )

    result = orchestrator.translate_batch([segment], target_languages=["en"])
    translated = result.translations["en"].segments[0]
    assert translated != segment.text
    assert "Rowan" in translated

    gate = TranslationQAGate(validator, min_pass_rate=1.0)
    qa_result = gate.check_batch([
        {
            "id": segment.segment_id,
            "src": segment.text,
            "tgt": translated,
            "src_lang": "ru",
            "tgt_lang": "en",
        }
    ])
    assert qa_result.passed
