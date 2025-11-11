"""
Tests for TermValidator.

Ensures 100% glossary compliance through validation and enforcement.
"""

import json
import pytest
from pathlib import Path

from kps.translation.term_validator import (
    TermRule,
    TermValidator,
    Violation,
    load_rules_from_glossary,
)


@pytest.fixture
def sample_rules():
    """Create sample glossary rules for testing."""
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
            src="2 вместе лицевой",
            tgt="knit 2 together",
            aliases=["k2tog"],
            category="decrease",
        ),
        TermRule(
            src_lang="ru",
            tgt_lang="en",
            src="Rowan",
            tgt="Rowan",
            do_not_translate=True,
            category="brand",
        ),
        TermRule(
            src_lang="ru",
            tgt_lang="fr",
            src="лицевая петля",
            tgt="maille endroit",
            aliases=["end"],
            category="stitch",
        ),
    ]


@pytest.fixture
def validator(sample_rules):
    """Create TermValidator with sample rules."""
    return TermValidator(sample_rules)


class TestTermRule:
    """Tests for TermRule dataclass."""

    def test_term_rule_creation(self):
        """Test creating a term rule."""
        rule = TermRule(
            src_lang="ru",
            tgt_lang="en",
            src="test",
            tgt="test translation",
        )

        assert rule.src_lang == "ru"
        assert rule.tgt_lang == "en"
        assert rule.src == "test"
        assert rule.tgt == "test translation"
        assert rule.do_not_translate is False
        assert rule.enforce_case is False
        assert rule.aliases == []

    def test_term_rule_with_protection(self):
        """Test creating a protected term rule."""
        rule = TermRule(
            src_lang="ru",
            tgt_lang="en",
            src="Rowan",
            tgt="Rowan",
            do_not_translate=True,
        )

        assert rule.do_not_translate is True


class TestTermValidator:
    """Tests for TermValidator class."""

    def test_validator_initialization(self, validator, sample_rules):
        """Test validator initialization."""
        assert len(validator.rules) == len(sample_rules)
        assert len(validator.rules_by_lang) > 0
        assert ("ru", "en") in validator.rules_by_lang

    def test_validate_no_violations(self, validator):
        """Test validation with correct translation."""
        src_text = "Провязать лицевую петлю"
        tgt_text = "Work a knit stitch"
        violations = validator.validate(src_text, tgt_text, "ru", "en")

        assert len(violations) == 0

    def test_validate_term_missing(self, validator):
        """Test detection of missing glossary term."""
        src_text = "Провязать лицевую петлю"
        tgt_text = "Work a purl stitch"  # Wrong term!

        violations = validator.validate(src_text, tgt_text, "ru", "en")

        assert len(violations) == 1
        assert violations[0].type == "term_missing"
        assert violations[0].rule.src == "лицевая петля"

    def test_validate_with_alias(self, validator):
        """Test that aliases are accepted."""
        src_text = "Провязать лицевую петлю"
        tgt_text = "Work a k"  # Using alias

        violations = validator.validate(src_text, tgt_text, "ru", "en")

        assert len(violations) == 0  # Alias should be accepted

    def test_validate_do_not_translate_broken(self, validator):
        """Test detection of translated protected term."""
        src_text = "Пряжа Rowan"
        tgt_text = "Yarn Роуан"  # Translated brand name!

        violations = validator.validate(src_text, tgt_text, "ru", "en")

        assert len(violations) == 1
        assert violations[0].type == "do_not_translate_broken"
        assert violations[0].rule.src == "Rowan"

    def test_validate_do_not_translate_correct(self, validator):
        """Test that protected terms unchanged pass validation."""
        src_text = "Пряжа Rowan"
        tgt_text = "Rowan yarn"  # Correct!

        violations = validator.validate(src_text, tgt_text, "ru", "en")

        # Should only have violations if the protected term is missing
        # In this case, "Rowan" is present, so no violations
        assert all(v.type != "do_not_translate_broken" for v in violations)

    def test_validate_case_insensitive(self, validator):
        """Test case-insensitive matching by default."""
        src_text = "ЛИЦЕВАЯ ПЕТЛЯ"
        tgt_text = "knit stitch"

        violations = validator.validate(src_text, tgt_text, "ru", "en")

        assert len(violations) == 0

    def test_validate_multiple_violations(self, validator):
        """Test detection of multiple violations."""
        src_text = "Провязать лицевую петлю и 2 вместе лицевой"
        tgt_text = "Work something else"  # Missing both terms

        violations = validator.validate(src_text, tgt_text, "ru", "en")

        assert len(violations) == 2
        violation_types = {v.rule.src for v in violations}
        assert "лицевая петля" in violation_types
        assert "2 вместе лицевой" in violation_types

    def test_validate_no_applicable_rules(self, validator):
        """Test validation when no rules apply."""
        src_text = "Some text without terms"
        tgt_text = "Some translated text"

        violations = validator.validate(src_text, tgt_text, "ru", "en")

        assert len(violations) == 0

    def test_get_rules_for_context(self, validator):
        """Test getting relevant rules for a text."""
        src_text = "Провязать лицевую петлю"

        rules = validator.get_rules_for_context(src_text, "ru", "en")

        assert len(rules) >= 1
        assert any(r.src == "лицевая петля" for r in rules)

    def test_format_rules_for_prompt(self, validator, sample_rules):
        """Test formatting rules for LLM prompt."""
        prompt_text = validator.format_rules_for_prompt(sample_rules[:2])

        assert "лицевая петля" in prompt_text
        assert "knit stitch" in prompt_text
        assert "Glossary terms" in prompt_text

    def test_format_rules_for_prompt_with_protection(self, validator, sample_rules):
        """Test formatting protected terms for prompt."""
        protected_rule = [r for r in sample_rules if r.do_not_translate][0]
        prompt_text = validator.format_rules_for_prompt([protected_rule])

        assert "KEEP UNCHANGED" in prompt_text or "do not translate" in prompt_text
        assert "Rowan" in prompt_text

    def test_get_statistics(self, validator):
        """Test getting validator statistics."""
        stats = validator.get_statistics()

        assert "total_rules" in stats
        assert "protected_terms" in stats
        assert "language_pairs" in stats
        assert stats["total_rules"] > 0


class TestLoadRulesFromGlossary:
    """Tests for load_rules_from_glossary function."""

    def test_load_rules_from_glossary(self, tmp_path):
        """Test loading rules from glossary JSON."""
        glossary_data = {
            "meta": {
                "source_language": "ru",
                "target_languages": ["en", "fr"],
            },
            "entries": [
                {
                    "ru": "лицевая петля",
                    "en": "knit stitch (k)",
                    "fr": "maille endroit (end)",
                    "category": "stitch",
                    "protected_tokens": [],
                },
                {
                    "ru": "Rowan",
                    "en": "Rowan",
                    "fr": "Rowan",
                    "category": "brand",
                    "protected_tokens": ["Rowan"],
                },
            ],
        }

        rules = load_rules_from_glossary(glossary_data, "ru")

        assert len(rules) == 4  # 2 entries × 2 target languages
        assert any(r.src == "лицевая петля" and r.tgt_lang == "en" for r in rules)
        assert any(r.src == "лицевая петля" and r.tgt_lang == "fr" for r in rules)

    def test_load_rules_extracts_aliases(self, tmp_path):
        """Test that aliases are extracted from parentheses."""
        glossary_data = {
            "meta": {"source_language": "ru", "target_languages": ["en"]},
            "entries": [
                {
                    "ru": "лицевая петля",
                    "en": "knit stitch (k, knit)",
                    "category": "stitch",
                }
            ],
        }

        rules = load_rules_from_glossary(glossary_data, "ru")

        assert len(rules) == 1
        rule = rules[0]
        assert rule.tgt == "knit stitch"
        assert "k" in rule.aliases
        assert "knit" in rule.aliases

    def test_load_rules_handles_missing_languages(self):
        """Test that entries without target language are skipped."""
        glossary_data = {
            "meta": {"source_language": "ru", "target_languages": ["en", "fr"]},
            "entries": [
                {
                    "ru": "test",
                    "en": "test_en",
                    # Missing "fr"
                }
            ],
        }

        rules = load_rules_from_glossary(glossary_data, "ru")

        # Should only have ru→en, not ru→fr
        assert len(rules) == 1
        assert rules[0].tgt_lang == "en"


class TestViolation:
    """Tests for Violation dataclass."""

    def test_violation_creation(self):
        """Test creating a violation."""
        rule = TermRule(
            src_lang="ru",
            tgt_lang="en",
            src="test",
            tgt="test translation",
        )

        violation = Violation(
            type="term_missing",
            rule=rule,
            context="Some context",
            suggestion="Use correct term",
        )

        assert violation.type == "term_missing"
        assert violation.rule == rule
        assert violation.context == "Some context"
        assert violation.suggestion == "Use correct term"


class TestIntegration:
    """Integration tests for TermValidator."""

    def test_full_validation_workflow(self, validator):
        """Test complete validation workflow."""
        # STEP 1: Create source text with glossary terms
        src_text = "Провязать лицевую петлю Rowan"

        # STEP 2: Correct translation
        correct_tgt = "Work a knit stitch Rowan"
        violations = validator.validate(src_text, correct_tgt, "ru", "en")
        assert len(violations) == 0

        # STEP 3: Incorrect translation (missing term)
        incorrect_tgt = "Work a stitch Rowan"
        violations = validator.validate(src_text, incorrect_tgt, "ru", "en")
        assert len(violations) == 1
        assert violations[0].type == "term_missing"

        # STEP 4: Incorrect translation (translated protected term)
        incorrect_tgt2 = "Work a knit stitch Роуан"
        violations = validator.validate(src_text, incorrect_tgt2, "ru", "en")
        assert any(v.type == "do_not_translate_broken" for v in violations)

    def test_real_world_knitting_pattern(self, validator):
        """Test with real knitting pattern text."""
        src_text = """
        Ряд 1: Провязать лицевую петлю, затем 2 вместе лицевой.
        Повторить до конца ряда.
        """

        # Correct translation with aliases
        correct_tgt = """
        Row 1: Work k, then k2tog.
        Repeat to end of row.
        """

        violations = validator.validate(src_text, correct_tgt, "ru", "en")
        assert len(violations) == 0

        # Incorrect translation
        incorrect_tgt = """
        Row 1: Work purl, then decrease.
        Repeat to end of row.
        """

        violations = validator.validate(src_text, incorrect_tgt, "ru", "en")
        assert len(violations) >= 2  # Both terms missing
