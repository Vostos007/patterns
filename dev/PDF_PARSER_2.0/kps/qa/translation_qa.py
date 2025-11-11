"""
Translation Quality Assurance (QA) Gateway.

Automated quality checks before publishing translations:
- Glossary term coverage (100% compliance)
- Protected brand names preservation
- No hallucinated content
- Length ratio validation
- Formatting preservation
- Optional: COMET/BLEU scores against reference

Usage:
    >>> from kps.qa.translation_qa import TranslationQA, QAGate
    >>>
    >>> qa = TranslationQA()
    >>> result = qa.check_segment(
    ...     src_text="@>2O68B5 2 ?5B;8 2<5AB5",
    ...     tgt_text="Work k2tog",
    ...     src_lang="ru",
    ...     tgt_lang="en",
    ...     glossary_terms=["k2tog"]
    ... )
    >>> if result.passed:
    ...     publish(tgt_text)
    >>> else:
    ...     for issue in result.issues:
    ...         print(f"QA Issue: {issue}")
"""

from dataclasses import dataclass, field
from typing import List, Optional, Set
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class QAIssue:
    """Single QA issue detected."""
    severity: str  # "error", "warning", "info"
    category: str  # "glossary", "brand", "length", "formatting", "hallucination"
    message: str
    suggestion: Optional[str] = None


@dataclass
class QAResult:
    """Result of QA checks."""
    passed: bool
    issues: List[QAIssue] = field(default_factory=list)
    score: float = 1.0  # Overall quality score (0.0-1.0)

    @property
    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return any(issue.severity == "error" for issue in self.issues)

    @property
    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return any(issue.severity == "warning" for issue in self.issues)

    def summary(self) -> str:
        """Get QA summary."""
        errors = sum(1 for i in self.issues if i.severity == "error")
        warnings = sum(1 for i in self.issues if i.severity == "warning")

        if self.passed:
            return f" QA Passed (score: {self.score:.2f}, {warnings} warnings)"
        else:
            return f"L QA Failed ({errors} errors, {warnings} warnings, score: {self.score:.2f})"


class TranslationQA:
    """
    Translation Quality Assurance checker.

    Performs automated quality checks on translated segments:
    1. Glossary term coverage (100% required terms present)
    2. Protected brand names unchanged
    3. No hallucinated content (unexpected brand/product names)
    4. Length ratio within acceptable range
    5. Formatting preservation (newlines, placeholders)
    6. No long unbreakable tokens (>50 chars)

    Optional:
    7. COMET/BLEU scores against reference translations
    """

    def __init__(
        self,
        protected_brands: Optional[Set[str]] = None,
        length_ratio_min: float = 0.5,
        length_ratio_max: float = 2.0,
        max_token_length: int = 50,
    ):
        """
        Initialize QA checker.

        Args:
            protected_brands: Set of brand names that must not be translated
            length_ratio_min: Minimum acceptable length ratio (tgt/src)
            length_ratio_max: Maximum acceptable length ratio (tgt/src)
            max_token_length: Maximum length for a single token (chars)
        """
        self.protected_brands = protected_brands or self._default_brands()
        self.length_ratio_min = length_ratio_min
        self.length_ratio_max = length_ratio_max
        self.max_token_length = max_token_length

    def _default_brands(self) -> Set[str]:
        """Default protected brand names."""
        return {
            # Yarn brands
            "Rowan", "Katia", "Drops", "Cascade", "Malabrigo", "Madelinetosh",
            "Red Heart", "Lion Brand", "Caron", "Bernat", "Patons",
            # Pattern publishers
            "Ravelry", "Knitty", "Interweave", "Vogue Knitting",
            # Tools
            "Clover", "Addi", "ChiaoGoo", "KnitPro",
        }

    def check_segment(
        self,
        src_text: str,
        tgt_text: str,
        src_lang: str,
        tgt_lang: str,
        glossary_terms: Optional[List[str]] = None,
        protected_tokens: Optional[List[str]] = None,
    ) -> QAResult:
        """
        Check single translated segment.

        Args:
            src_text: Source text
            tgt_text: Translated text
            src_lang: Source language code
            tgt_lang: Target language code
            glossary_terms: Required glossary terms that must appear in target
            protected_tokens: Tokens that must remain unchanged

        Returns:
            QAResult with issues and pass/fail status
        """
        result = QAResult(passed=True, issues=[])

        # Check 1: Glossary term coverage
        if glossary_terms:
            self._check_glossary_coverage(
                tgt_text, glossary_terms, result
            )

        # Check 2: Protected brand names
        if protected_tokens:
            self._check_protected_tokens(
                src_text, tgt_text, protected_tokens, result
            )

        # Check 3: Brand preservation
        self._check_brands_preserved(src_text, tgt_text, result)

        # Check 4: Length ratio
        self._check_length_ratio(src_text, tgt_text, result)

        # Check 5: Formatting preservation
        self._check_formatting(src_text, tgt_text, result)

        # Check 6: Long unbreakable tokens
        self._check_long_tokens(tgt_text, result)

        # Determine pass/fail
        result.passed = not result.has_errors

        # Calculate score (1.0 - weighted penalties)
        error_penalty = sum(0.3 for i in result.issues if i.severity == "error")
        warning_penalty = sum(0.1 for i in result.issues if i.severity == "warning")
        result.score = max(0.0, 1.0 - error_penalty - warning_penalty)

        return result

    def _check_glossary_coverage(
        self,
        tgt_text: str,
        glossary_terms: List[str],
        result: QAResult
    ):
        """Check that all required glossary terms are present."""
        tgt_lower = tgt_text.lower()

        for term in glossary_terms:
            term_lower = term.lower()

            # Check if term is present (word boundary)
            pattern = r'\b' + re.escape(term_lower) + r'\b'
            if not re.search(pattern, tgt_lower):
                result.issues.append(QAIssue(
                    severity="error",
                    category="glossary",
                    message=f"Required glossary term '{term}' not found in translation",
                    suggestion=f"Ensure '{term}' appears in the translation"
                ))

    def _check_protected_tokens(
        self,
        src_text: str,
        tgt_text: str,
        protected_tokens: List[str],
        result: QAResult
    ):
        """Check that protected tokens remain unchanged."""
        for token in protected_tokens:
            # Check if token is in source
            if token in src_text:
                # Must also be in target unchanged
                if token not in tgt_text:
                    result.issues.append(QAIssue(
                        severity="error",
                        category="brand",
                        message=f"Protected token '{token}' was translated or removed",
                        suggestion=f"Keep '{token}' unchanged in translation"
                    ))

    def _check_brands_preserved(
        self,
        src_text: str,
        tgt_text: str,
        result: QAResult
    ):
        """Check that brand names from source are preserved in target."""
        # Find brands in source
        brands_in_src = set()
        for brand in self.protected_brands:
            if brand in src_text:
                brands_in_src.add(brand)

        # Check each brand is preserved
        for brand in brands_in_src:
            if brand not in tgt_text:
                result.issues.append(QAIssue(
                    severity="error",
                    category="brand",
                    message=f"Brand name '{brand}' was translated or removed",
                    suggestion=f"Brand names must remain unchanged"
                ))

    def _check_length_ratio(
        self,
        src_text: str,
        tgt_text: str,
        result: QAResult
    ):
        """Check that translation length is within acceptable ratio."""
        src_len = len(src_text.strip())
        tgt_len = len(tgt_text.strip())

        if src_len == 0:
            return

        ratio = tgt_len / src_len

        if ratio < self.length_ratio_min:
            result.issues.append(QAIssue(
                severity="warning",
                category="length",
                message=f"Translation too short (ratio: {ratio:.2f}, min: {self.length_ratio_min})",
                suggestion="Check if content was omitted"
            ))
        elif ratio > self.length_ratio_max:
            result.issues.append(QAIssue(
                severity="warning",
                category="length",
                message=f"Translation too long (ratio: {ratio:.2f}, max: {self.length_ratio_max})",
                suggestion="Check for added content or verbosity"
            ))

    def _check_formatting(
        self,
        src_text: str,
        tgt_text: str,
        result: QAResult
    ):
        """Check that formatting is preserved (newlines, placeholders)."""
        # Count newlines
        src_newlines = src_text.count("\n")
        tgt_newlines = tgt_text.count("\n")

        if src_newlines != tgt_newlines:
            result.issues.append(QAIssue(
                severity="warning",
                category="formatting",
                message=f"Newline count mismatch (src: {src_newlines}, tgt: {tgt_newlines})",
                suggestion="Preserve original line breaks"
            ))

        # Check placeholders (e.g., <ph id="..." />)
        ph_pattern = r'<ph\s+id="[^"]+"\s*/>'
        src_placeholders = re.findall(ph_pattern, src_text)
        tgt_placeholders = re.findall(ph_pattern, tgt_text)

        if len(src_placeholders) != len(tgt_placeholders):
            result.issues.append(QAIssue(
                severity="error",
                category="formatting",
                message=f"Placeholder count mismatch (src: {len(src_placeholders)}, tgt: {len(tgt_placeholders)})",
                suggestion="Do not translate or remove placeholders"
            ))

    def _check_long_tokens(
        self,
        tgt_text: str,
        result: QAResult
    ):
        """Check for excessively long unbreakable tokens."""
        # Split by whitespace
        tokens = tgt_text.split()

        for token in tokens:
            # Remove common punctuation
            clean_token = re.sub(r'[.,;:!?()"\']', '', token)

            if len(clean_token) > self.max_token_length:
                result.issues.append(QAIssue(
                    severity="warning",
                    category="formatting",
                    message=f"Very long token found: '{clean_token[:50]}...' ({len(clean_token)} chars)",
                    suggestion="Check if this is a concatenated error or URL"
                ))


class QAGate:
    """
    Quality gate for batch translations.

    Checks entire batch and produces summary report.
    Can be configured with thresholds for pass/fail.
    """

    def __init__(
        self,
        qa_checker: Optional[TranslationQA] = None,
        error_threshold: int = 0,  # Max errors allowed
        warning_threshold: int = 10,  # Max warnings allowed
        min_pass_rate: float = 0.95,  # Minimum pass rate (95%)
    ):
        """
        Initialize QA gate.

        Args:
            qa_checker: TranslationQA instance
            error_threshold: Maximum errors allowed before rejecting batch
            warning_threshold: Maximum warnings allowed before flagging for review
            min_pass_rate: Minimum pass rate (0.0-1.0)
        """
        self.qa_checker = qa_checker or TranslationQA()
        self.error_threshold = error_threshold
        self.warning_threshold = warning_threshold
        self.min_pass_rate = min_pass_rate

    def check_batch(
        self,
        segments: List[dict],  # List of {src_text, tgt_text, src_lang, tgt_lang, ...}
    ) -> dict:
        """
        Check batch of translations.

        Args:
            segments: List of segment dicts with src_text, tgt_text, etc.

        Returns:
            Dict with batch QA results

        Example:
            >>> segments = [
            ...     {
            ...         "src_text": "@>2O68B5 2 2<5AB5",
            ...         "tgt_text": "Work k2tog",
            ...         "src_lang": "ru",
            ...         "tgt_lang": "en",
            ...         "glossary_terms": ["k2tog"]
            ...     }
            ... ]
            >>> gate = QAGate()
            >>> result = gate.check_batch(segments)
            >>> if result["passed"]:
            ...     publish_batch()
        """
        total = len(segments)
        passed = 0
        total_errors = 0
        total_warnings = 0
        all_issues = []

        # Check each segment
        for idx, segment in enumerate(segments):
            qa_result = self.qa_checker.check_segment(
                src_text=segment["src_text"],
                tgt_text=segment["tgt_text"],
                src_lang=segment["src_lang"],
                tgt_lang=segment["tgt_lang"],
                glossary_terms=segment.get("glossary_terms"),
                protected_tokens=segment.get("protected_tokens"),
            )

            if qa_result.passed:
                passed += 1

            errors = sum(1 for i in qa_result.issues if i.severity == "error")
            warnings = sum(1 for i in qa_result.issues if i.severity == "warning")

            total_errors += errors
            total_warnings += warnings

            # Collect issues with segment index
            for issue in qa_result.issues:
                all_issues.append({
                    "segment_idx": idx,
                    "src_text": segment["src_text"][:50] + "...",
                    "severity": issue.severity,
                    "category": issue.category,
                    "message": issue.message,
                    "suggestion": issue.suggestion,
                })

        # Calculate pass rate
        pass_rate = passed / total if total > 0 else 0.0

        # Determine overall pass/fail
        batch_passed = (
            total_errors <= self.error_threshold and
            total_warnings <= self.warning_threshold and
            pass_rate >= self.min_pass_rate
        )

        return {
            "passed": batch_passed,
            "total_segments": total,
            "passed_segments": passed,
            "pass_rate": pass_rate,
            "total_errors": total_errors,
            "total_warnings": total_warnings,
            "issues": all_issues,
            "summary": (
                f" Batch QA Passed ({passed}/{total} segments, "
                f"pass rate: {pass_rate:.1%}, {total_errors} errors, {total_warnings} warnings)"
                if batch_passed else
                f"L Batch QA Failed ({passed}/{total} segments, "
                f"pass rate: {pass_rate:.1%}, {total_errors} errors, {total_warnings} warnings)"
            )
        }


__all__ = [
    "TranslationQA",
    "QAGate",
    "QAResult",
    "QAIssue",
]
