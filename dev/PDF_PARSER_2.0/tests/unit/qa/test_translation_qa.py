"""Unit tests for TranslationQAGate."""

from kps.qa.translation_qa import TranslationQAGate
from kps.translation.term_validator import TermRule, TermValidator


def _validator_with_rule(src: str, tgt: str) -> TermValidator:
    return TermValidator([TermRule(src_lang="ru", tgt_lang="en", src=src, tgt=tgt)])


def test_translation_qa_blocks_missing_terms():
    gate = TranslationQAGate(_validator_with_rule("петли", "stitches"), min_pass_rate=1.0)
    batch = [
        {
            "id": "seg1",
            "src": "Свяжите петли",
            "tgt": "Knit the loops",
            "src_lang": "ru",
            "tgt_lang": "en",
        }
    ]
    result = gate.check_batch(batch)
    assert not result.passed
    assert result.findings[0].kind == "term_missing"


def test_translation_qa_checks_length_ratio():
    validator = TermValidator([])
    gate = TranslationQAGate(validator, min_pass_rate=1.0, min_len_ratio=0.9, max_len_ratio=1.1)
    batch = [
        {
            "id": "seg2",
            "src": "Очень длинный оригинальный текст для проверки",
            "tgt": "Short translated text",
            "src_lang": "ru",
            "tgt_lang": "en",
        }
    ]
    result = gate.check_batch(batch)
    assert not result.passed
    assert any(f.kind == "len_ratio" for f in result.findings)


def test_translation_qa_detects_long_tokens():
    validator = TermValidator([])
    gate = TranslationQAGate(validator, min_pass_rate=1.0, max_token_len=5)
    batch = [
        {
            "id": "seg3",
            "src": "token",
            "tgt": "supercalifragilistic",
            "src_lang": "en",
            "tgt_lang": "en",
        }
    ]
    result = gate.check_batch(batch)
    assert not result.passed
    assert any(f.kind == "long_token" for f in result.findings)


def test_translation_qa_passes_clean_batch():
    gate = TranslationQAGate(_validator_with_rule("петли", "stitches"), min_pass_rate=1.0)
    batch = [
        {
            "id": "seg4",
            "src": "Свяжите петли",
            "tgt": "Knit stitches",
            "src_lang": "ru",
            "tgt_lang": "en",
        }
    ]
    result = gate.check_batch(batch)
    assert result.passed
    assert result.findings == []
