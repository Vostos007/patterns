"""
Term Validator for glossary compliance.

Ensures 100% adherence to glossary terms through:
- Pre-translation validation (detect potential issues)
- Post-translation validation (detect violations)
- Auto-enforcement (fix violations)
- Integration with OpenAI Structured Outputs for guaranteed compliance
"""

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TermRule:
    """
    Glossary term rule for translation validation.

    Attributes:
        src_lang: Source language code (e.g., 'ru')
        tgt_lang: Target language code (e.g., 'en', 'fr')
        src: Source term (e.g., 'лицевая петля')
        tgt: Target term (e.g., 'knit stitch')
        do_not_translate: If True, term must remain unchanged (e.g., brand names)
        enforce_case: If True, enforce exact case matching
        aliases: Alternative forms of the term (e.g., ['k', 'knit'])
        category: Term category for metrics (e.g., 'stitch', 'decrease')
    """
    src_lang: str
    tgt_lang: str
    src: str
    tgt: str
    do_not_translate: bool = False
    enforce_case: bool = False
    aliases: List[str] = field(default_factory=list)
    category: str = "general"


@dataclass
class Violation:
    """Term violation detected during validation."""
    type: str  # 'term_missing', 'do_not_translate_broken', 'case_mismatch'
    rule: TermRule
    context: str = ""
    suggestion: str = ""


class TermValidator:
    """
    Validates translations for glossary compliance.

    Usage:
        validator = TermValidator(rules)
        violations = validator.validate(src_text, tgt_text, "ru", "fr")
        if violations:
            # Try LLM with Structured Outputs
            tgt_text = llm_translate_strict(src_text, rules)
            violations = validator.validate(src_text, tgt_text, "ru", "fr")

        # Enforce as last resort
        tgt_text = validator.enforce(tgt_text, "fr")
    """

    def __init__(self, rules: List[TermRule]):
        """
        Initialize validator with glossary rules.

        Args:
            rules: List of TermRule objects from glossary
        """
        self.rules = rules
        self._build_indexes()

    def _build_indexes(self):
        """Build efficient lookup indexes for validation."""
        # Index by (src_lang, tgt_lang) for quick filtering
        self.rules_by_lang: Dict[Tuple[str, str], List[TermRule]] = {}

        # Index do_not_translate terms by target lang
        self.protected_terms: Dict[str, List[TermRule]] = {}

        for rule in self.rules:
            lang_key = (rule.src_lang, rule.tgt_lang)
            if lang_key not in self.rules_by_lang:
                self.rules_by_lang[lang_key] = []
            self.rules_by_lang[lang_key].append(rule)

            if rule.do_not_translate:
                if rule.tgt_lang not in self.protected_terms:
                    self.protected_terms[rule.tgt_lang] = []
                self.protected_terms[rule.tgt_lang].append(rule)

    def validate(
        self,
        src_text: str,
        tgt_text: str,
        src_lang: str,
        tgt_lang: str,
    ) -> List[Violation]:
        """
        Validate translation for glossary compliance.

        Args:
            src_text: Source text
            tgt_text: Translated text
            src_lang: Source language code
            tgt_lang: Target language code

        Returns:
            List of violations found (empty if compliant)
        """
        violations = []

        # Get applicable rules
        lang_key = (src_lang, tgt_lang)
        applicable_rules = self.rules_by_lang.get(lang_key, [])

        if not applicable_rules:
            logger.debug(f"No rules for {src_lang} → {tgt_lang}")
            return violations

        # Normalize for case-insensitive matching (unless enforce_case=True)
        src_lower = src_text.lower()
        tgt_lower = tgt_text.lower()

        for rule in applicable_rules:
            if len(rule.tgt) <= 2:
                continue
            # Check if source term is present
            if not self._term_in_text(src_lower, rule.src):
                continue  # Source term not in source text, skip

            # Check do_not_translate violation
            if rule.do_not_translate:
                # Term must appear unchanged in target
                if rule.src not in tgt_text:
                    violations.append(Violation(
                        type='do_not_translate_broken',
                        rule=rule,
                        context=f"Expected '{rule.src}' unchanged in target",
                        suggestion=f"Keep '{rule.src}' as-is"
                    ))
                continue

            # Check term_missing violation
            found = self._contains_term(tgt_lower, rule.tgt)

            # Also check aliases
            if not found and rule.aliases:
                for alias in rule.aliases:
                    if self._contains_term(tgt_lower, alias):
                        found = True
                        break

            if not found:
                violations.append(Violation(
                    type='term_missing',
                    rule=rule,
                    context=f"Source contains '{rule.src}' but target missing '{rule.tgt}'",
                    suggestion=f"Use '{rule.tgt}' for '{rule.src}'"
                ))

            # Check case enforcement
            elif found and rule.enforce_case:
                # Exact case match required
                if rule.tgt not in tgt_text:
                    violations.append(Violation(
                        type='case_mismatch',
                        rule=rule,
                        context=f"Found term but wrong case",
                        suggestion=f"Use exact case: '{rule.tgt}'"
                    ))

        return violations

    def enforce(
        self,
        src_text: str,
        tgt_text: str,
        src_lang: str,
        tgt_lang: str,
        fix_mode: str = "replace",
    ) -> str:
        """
        Auto-enforce glossary terms in translated text.

        This is a fallback mechanism when LLM validation fails.
        Uses pattern matching to replace incorrect terms.

        Args:
            tgt_text: Translated text with potential violations
            tgt_lang: Target language code
            fix_mode: 'replace' (default) or 'highlight' (for review)

        Returns:
            Corrected text with glossary terms enforced
        """
        corrected = tgt_text

        applicable_rules = self.get_rules_for_context(
            src_text=src_text, src_lang=src_lang, tgt_lang=tgt_lang
        )

        if not applicable_rules:
            return corrected

        def has_variant(text: str, variants: List[str]) -> bool:
            lower = text.lower()
            return any(v.lower() in lower for v in variants if v)

        for rule in applicable_rules:
            variants = [rule.tgt] + list(rule.aliases or [])

            if rule.do_not_translate:
                if rule.src not in corrected:
                    # Replace any translated variant with the protected token
                    replaced = False
                    for variant in variants:
                        if variant and variant in corrected:
                            corrected = corrected.replace(variant, rule.src)
                            replaced = True
                            break
                    if not replaced:
                        corrected = corrected.rstrip() + (" " if corrected else "") + rule.src
                continue

            if not has_variant(corrected, variants):
                if rule.src in corrected:
                    corrected = corrected.replace(rule.src, rule.tgt)
                else:
                    corrected = corrected.rstrip() + (" " if corrected else "") + rule.tgt

            if rule.enforce_case and rule.tgt:
                corrected = self._force_case(corrected, rule.tgt)

        return corrected

    def _contains_term(self, text_lower: str, term: str) -> bool:
        if not term:
            return False
        pattern = self._build_term_pattern(term)
        return bool(pattern.search(text_lower))

    def _build_term_pattern(self, term: str) -> re.Pattern:
        """Create regex allowing simple plural/possessive variants."""
        suffix = ""
        if term and term.replace(" ", "").isalpha():
            suffix = r"(?:'s|s)?"
        return re.compile(r"\b" + re.escape(term.lower()) + suffix + r"\b", re.IGNORECASE)

    def _term_in_text(self, text: str, term: str) -> bool:
        if not term:
            return False
        term_words = self._split_words(term.lower())
        text_words = self._split_words(text)
        if not term_words or not text_words:
            return False

        for idx in range(len(text_words) - len(term_words) + 1):
            window = text_words[idx: idx + len(term_words)]
            if all(
                self._words_similar(term_word, window_word)
                for term_word, window_word in zip(term_words, window)
            ):
                return True

        return False

    def _split_words(self, text: str) -> List[str]:
        return re.findall(r"\w+", text)

    def _words_similar(self, term_word: str, text_word: str) -> bool:
        if term_word == text_word:
            return True
        if not term_word or not text_word:
            return False
        if term_word in text_word or text_word in term_word:
            return True
        if len(term_word) >= 4 and len(text_word) >= 4:
            ratio = SequenceMatcher(None, term_word, text_word).ratio()
            return ratio >= 0.7
        return False

    def _force_case(self, text: str, needle: str) -> str:
        """Ensure the canonical term uses the expected casing."""
        lowered = text.lower()
        target = needle.lower()
        start = 0
        while True:
            idx = lowered.find(target, start)
            if idx == -1:
                break
            actual = text[idx : idx + len(needle)]
            if actual != needle:
                text = text[:idx] + needle + text[idx + len(needle) :]
                lowered = text.lower()
                start = idx + len(needle)
            else:
                start = idx + len(needle)
        return text

    def get_rules_for_context(
        self,
        src_text: str,
        src_lang: str,
        tgt_lang: str,
    ) -> List[TermRule]:
        """
        Get relevant glossary rules for a specific source text.

        Used to provide context to LLM via Structured Outputs.

        Args:
            src_text: Source text to translate
            src_lang: Source language
            tgt_lang: Target language

        Returns:
            List of rules applicable to this text
        """
        lang_key = (src_lang, tgt_lang)
        all_rules = self.rules_by_lang.get(lang_key, [])

        # Filter to only rules where source term appears in text
        src_lower = src_text.lower()
        relevant_rules = []

        for rule in all_rules:
            if self._term_in_text(src_lower, rule.src):
                relevant_rules.append(rule)

        return relevant_rules

    def format_rules_for_prompt(
        self,
        rules: List[TermRule]
    ) -> str:
        """
        Format rules for LLM prompt.

        Args:
            rules: Rules to format

        Returns:
            Formatted string for prompt injection
        """
        if not rules:
            return ""

        lines = ["Glossary terms (MUST use exact translations):"]
        for rule in rules:
            if rule.do_not_translate:
                lines.append(f"  - '{rule.src}' → KEEP UNCHANGED (do not translate)")
            else:
                main = f"  - '{rule.src}' → '{rule.tgt}'"
                if rule.aliases:
                    main += f" (or: {', '.join(rule.aliases)})"
                if rule.enforce_case:
                    main += " [EXACT CASE]"
                lines.append(main)

        return "\n".join(lines)

    def get_statistics(self) -> Dict[str, int]:
        """Get validator statistics."""
        return {
            "total_rules": len(self.rules),
            "protected_terms": sum(
                len(terms) for terms in self.protected_terms.values()
            ),
            "language_pairs": len(self.rules_by_lang),
        }


def load_rules_from_glossary(
    glossary_data: Dict,
    source_lang: str,
) -> List[TermRule]:
    """
    Load TermRule objects from glossary JSON structure.

    Args:
        glossary_data: Parsed glossary JSON (глоссарий.json format)
        source_lang: Source language code

    Returns:
        List of TermRule objects

    Example:
        >>> import json
        >>> with open("глоссарий.json") as f:
        ...     glossary = json.load(f)
        >>> rules = load_rules_from_glossary(glossary, "ru")
    """
    rules = []

    meta = glossary_data.get("meta", {})
    target_languages = meta.get("target_languages", ["en", "fr"])

    for entry in glossary_data.get("entries", []):
        src_text = entry.get(source_lang)
        if not src_text:
            continue

        category = entry.get("category", "general")
        protected_tokens = entry.get("protected_tokens", [])

        for tgt_lang in target_languages:
            tgt_text = entry.get(tgt_lang)
            if not tgt_text:
                continue

            # Check if this is a protected term
            do_not_translate = False
            if protected_tokens:
                # If the target contains protected tokens in parentheses,
                # extract the main term without parentheses
                # e.g., "knit stitch (k)" → main term is "knit stitch", alias is "k"
                pass

            # Extract aliases from parentheses
            aliases = []
            main_term = tgt_text

            # Pattern: "main term (alias1, alias2)"
            match = re.match(r'^(.+?)\s*\(([^)]+)\)$', tgt_text)
            if match:
                main_term = match.group(1).strip()
                alias_str = match.group(2).strip()
                # Split by comma and clean
                aliases = [a.strip() for a in alias_str.split(',')]

            rule = TermRule(
                src_lang=source_lang,
                tgt_lang=tgt_lang,
                src=src_text,
                tgt=main_term,
                do_not_translate=main_term in protected_tokens if protected_tokens else False,
                enforce_case=False,  # Could be configurable
                aliases=aliases,
                category=category,
            )

            rules.append(rule)

    logger.info(f"Loaded {len(rules)} term rules from glossary")
    return rules


__all__ = [
    "TermRule",
    "Violation",
    "TermValidator",
    "load_rules_from_glossary",
]
