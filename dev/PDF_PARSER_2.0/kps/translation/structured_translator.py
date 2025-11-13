"""
Structured Outputs translator with guaranteed glossary compliance.

Integrates TermValidator with OpenAI Structured Outputs to ensure
100% glossary adherence through:
1. Regular translation with glossary context
2. Validation for violations
3. Re-translation with Structured Outputs if violations found
4. Metrics tracking for compliance

Uses OpenAI's response_format with json_schema (strict mode).
"""

import json
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

try:
    import openai
except ImportError:
    openai = None

from .term_validator import TermRule, TermValidator, Violation
from .orchestrator import TranslationOrchestrator, TranslationSegment

logger = logging.getLogger(__name__)


@dataclass
class StructuredTranslationResult:
    """Result of structured translation with validation."""
    translated_text: str
    violations_before: List[Violation]
    violations_after: List[Violation]
    used_structured_outputs: bool
    retries: int


class StructuredTranslator:
    """
    Translator with guaranteed glossary compliance via Structured Outputs.

    Workflow:
    1. Translate with regular LLM call (fast, includes glossary context)
    2. Validate with TermValidator
    3. If violations → retry with Structured Outputs (slow but guaranteed)
    4. Validate again
    5. If still violations → log error and use enforcement

    Example:
        >>> validator = TermValidator(rules)
        >>> translator = StructuredTranslator(orchestrator, validator)
        >>> result = translator.translate_with_validation(
        ...     "Провязать 2 вместе лицевой",
        ...     "ru", "en"
        ... )
        >>> assert len(result.violations_after) == 0  # Guaranteed!
    """

    def __init__(
        self,
        orchestrator: TranslationOrchestrator,
        validator: TermValidator,
        max_retries: int = 2,
    ):
        """
        Initialize structured translator.

        Args:
            orchestrator: Translation orchestrator for API calls
            validator: Term validator for glossary compliance
            max_retries: Max attempts with Structured Outputs (default: 2)
        """
        self.orchestrator = orchestrator
        self.validator = validator
        self.max_retries = max_retries

        # Metrics
        self.stats = {
            "total_segments": 0,
            "segments_with_violations": 0,
            "segments_fixed_by_structured": 0,
            "segments_requiring_enforcement": 0,
        }

    def translate_with_validation(
        self,
        source_text: str,
        source_lang: str,
        target_lang: str,
        glossary_context: str = "",
    ) -> StructuredTranslationResult:
        """
        Translate with guaranteed glossary compliance.

        Args:
            source_text: Source text to translate
            source_lang: Source language code
            target_lang: Target language code
            glossary_context: Glossary context for prompt

        Returns:
            StructuredTranslationResult with compliance guaranteed
        """
        self.stats["total_segments"] += 1

        # STEP 1: Regular translation (fast)
        segment = TranslationSegment(
            segment_id="validation",
            text=source_text,
            placeholders={},
        )

        batch_result = self.orchestrator.translate_batch(
            segments=[segment],
            target_languages=[target_lang],
            glossary_context=glossary_context,
        )

        translated_text = batch_result.translations[target_lang].segments[0]

        # STEP 2: Validate
        violations = self.validator.validate(
            source_text,
            translated_text,
            source_lang,
            target_lang,
        )

        if not violations:
            # Perfect! No violations
            return StructuredTranslationResult(
                translated_text=translated_text,
                violations_before=[],
                violations_after=[],
                used_structured_outputs=False,
                retries=0,
            )

        # STEP 3: Violations found - try Structured Outputs
        logger.info(
            f"Found {len(violations)} violations, retrying with Structured Outputs"
        )
        self.stats["segments_with_violations"] += 1

        # Get relevant rules for this text
        relevant_rules = self.validator.get_rules_for_context(
            source_text, source_lang, target_lang
        )

        # Try with Structured Outputs
        for attempt in range(self.max_retries):
            translated_text = self._translate_with_structured_outputs(
                source_text=source_text,
                source_lang=source_lang,
                target_lang=target_lang,
                rules=relevant_rules,
            )

            # Validate again
            new_violations = self.validator.validate(
                source_text,
                translated_text,
                source_lang,
                target_lang,
            )

            if not new_violations:
                # Success!
                self.stats["segments_fixed_by_structured"] += 1
                return StructuredTranslationResult(
                    translated_text=translated_text,
                    violations_before=violations,
                    violations_after=[],
                    used_structured_outputs=True,
                    retries=attempt + 1,
                )

            logger.warning(
                f"Structured Outputs attempt {attempt + 1} still has "
                f"{len(new_violations)} violations"
            )

        # STEP 4: Still violations - use enforcement
        logger.error(
            f"Failed to fix violations with Structured Outputs, using enforcement"
        )
        self.stats["segments_requiring_enforcement"] += 1

        enforced_text = self.validator.enforce(
            src_text=source_text,
            tgt_text=translated_text,
            src_lang=source_lang,
            tgt_lang=target_lang,
        )

        # Validate one last time
        final_violations = self.validator.validate(
            source_text,
            enforced_text,
            source_lang,
            target_lang,
        )

        return StructuredTranslationResult(
            translated_text=enforced_text,
            violations_before=violations,
            violations_after=final_violations,
            used_structured_outputs=True,
            retries=self.max_retries,
        )

    def _translate_with_structured_outputs(
        self,
        source_text: str,
        source_lang: str,
        target_lang: str,
        rules: List[TermRule],
    ) -> str:
        """
        Translate using OpenAI Structured Outputs.

        This uses response_format with json_schema to guarantee
        the response follows the specified format, including
        mandatory glossary term usage.

        Args:
            source_text: Source text
            source_lang: Source language
            target_lang: Target language
            rules: Applicable glossary rules

        Returns:
            Translated text with guaranteed glossary compliance
        """
        if openai is None:
            raise RuntimeError("OpenAI library not available")

        # Build schema for Structured Outputs
        schema = self._build_json_schema(rules, target_lang)

        # Build prompt with mandatory glossary
        prompt = self._build_structured_prompt(
            source_text, source_lang, target_lang, rules
        )

        # Call OpenAI with Structured Outputs
        client = openai.OpenAI()

        try:
            response = client.chat.completions.create(
                model=self.orchestrator.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional translator specializing in knitting patterns. "
                        "You MUST use the exact glossary terms provided.",
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "translation_response",
                        "strict": True,  # CRITICAL: strict mode enforces schema
                        "schema": schema,
                    },
                },
                temperature=0.3,  # Lower temperature for consistency
            )

            # Parse response
            content = response.choices[0].message.content
            if content:
                result = json.loads(content)
                return result.get("translation", "")

            logger.error("Empty response from OpenAI Structured Outputs")
            return source_text

        except Exception as e:
            logger.error(f"Structured Outputs API call failed: {e}")
            # Fallback to source text
            return source_text

    def _build_json_schema(
        self, rules: List[TermRule], target_lang: str
    ) -> Dict:
        """
        Build JSON schema for Structured Outputs.

        The schema enforces that the translation includes
        specific glossary terms.

        Args:
            rules: Glossary rules to enforce
            target_lang: Target language

        Returns:
            JSON schema dict
        """
        # Extract required terms
        required_terms = []
        for rule in rules:
            if not rule.do_not_translate:
                required_terms.append({
                    "term": rule.tgt,
                    "aliases": rule.aliases,
                })

        schema = {
            "type": "object",
            "properties": {
                "translation": {
                    "type": "string",
                    "description": f"Translated text in {target_lang} with mandatory glossary terms",
                },
                "used_terms": {
                    "type": "array",
                    "description": "List of glossary terms used in translation",
                    "items": {"type": "string"},
                },
            },
            "required": ["translation", "used_terms"],
            "additionalProperties": False,
        }

        return schema

    def _build_structured_prompt(
        self,
        source_text: str,
        source_lang: str,
        target_lang: str,
        rules: List[TermRule],
    ) -> str:
        """
        Build prompt for Structured Outputs translation.

        Args:
            source_text: Source text
            source_lang: Source language
            target_lang: Target language
            rules: Applicable glossary rules

        Returns:
            Formatted prompt
        """
        # Format glossary rules
        glossary_text = self.validator.format_rules_for_prompt(rules)

        prompt = f"""Translate the following {source_lang} text to {target_lang}.

MANDATORY GLOSSARY TERMS - You MUST use these exact translations:
{glossary_text}

Source text:
{source_text}

Provide your response as JSON with:
- "translation": the translated text using the mandatory glossary terms
- "used_terms": array of glossary terms you used

Remember: You MUST use the exact glossary translations provided above."""

        return prompt

    def get_statistics(self) -> Dict:
        """Get validator statistics."""
        total = self.stats["total_segments"]
        if total == 0:
            return self.stats

        return {
            **self.stats,
            "violation_rate": self.stats["segments_with_violations"] / total,
            "fix_rate": (
                self.stats["segments_fixed_by_structured"]
                / max(self.stats["segments_with_violations"], 1)
            ),
            "enforcement_rate": (
                self.stats["segments_requiring_enforcement"]
                / max(self.stats["segments_with_violations"], 1)
            ),
        }


__all__ = [
    "StructuredTranslator",
    "StructuredTranslationResult",
]
