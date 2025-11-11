"""
Translation verification and quality assurance system.

This module provides comprehensive verification of translations including:
- Glossary term verification
- Consistency checking
- Format preservation validation
- Placeholder integrity checking
- Quality scoring
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from .glossary.advanced_matcher import AdvancedGlossaryMatcher, TermOccurrence
from .glossary.manager import GlossaryManager


@dataclass
class VerificationIssue:
    """A single verification issue found."""

    issue_type: str  # "missing_term", "incorrect_term", "format_mismatch", etc.
    severity: str  # "critical", "warning", "info"
    segment_id: str
    description: str
    expected: Optional[str] = None
    found: Optional[str] = None
    suggestion: Optional[str] = None


@dataclass
class SegmentVerification:
    """Verification result for a single segment."""

    segment_id: str
    source_text: str
    translated_text: str
    issues: List[VerificationIssue]
    quality_score: float  # 0.0-1.0
    passed: bool  # True if no critical issues


@dataclass
class VerificationReport:
    """Complete verification report."""

    total_segments: int
    passed_segments: int
    failed_segments: int
    total_issues: int
    issues_by_type: Dict[str, int]
    issues_by_severity: Dict[str, int]
    average_quality: float
    segments: List[SegmentVerification]


class TranslationVerifier:
    """
    Comprehensive translation verification system.

    This verifier checks translations for:
    1. Correct usage of glossary terms
    2. Consistency across segments
    3. Format preservation (newlines, punctuation)
    4. Placeholder integrity
    5. Protected token preservation

    Example:
        >>> verifier = TranslationVerifier(glossary_manager)
        >>> report = verifier.verify_translation(
        ...     source_segments=source,
        ...     translated_segments=translated,
        ...     source_lang="ru",
        ...     target_lang="en",
        ... )
        >>> print(f"Quality: {report.average_quality:.2%}")
        >>> print(f"Passed: {report.passed_segments}/{report.total_segments}")
    """

    def __init__(
        self,
        glossary_manager: GlossaryManager,
        min_quality_threshold: float = 0.8,
        strict_mode: bool = False,
    ):
        """
        Initialize verifier.

        Args:
            glossary_manager: Glossary manager for term lookups
            min_quality_threshold: Minimum quality score to pass (0.0-1.0)
            strict_mode: If True, treat warnings as failures
        """
        self.glossary = glossary_manager
        self.matcher = AdvancedGlossaryMatcher(glossary_manager)
        self.min_quality = min_quality_threshold
        self.strict_mode = strict_mode

    def verify_translation(
        self,
        source_segments: List[Tuple[str, str]],  # (id, text)
        translated_segments: List[Tuple[str, str]],  # (id, text)
        source_lang: str,
        target_lang: str,
    ) -> VerificationReport:
        """
        Verify complete translation.

        Args:
            source_segments: List of (segment_id, source_text) tuples
            translated_segments: List of (segment_id, translated_text) tuples
            source_lang: Source language code
            target_lang: Target language code

        Returns:
            VerificationReport with detailed results
        """
        segment_verifications = []

        for (src_id, src_text), (tgt_id, tgt_text) in zip(
            source_segments, translated_segments
        ):
            # Verify each segment
            verification = self._verify_segment(
                segment_id=src_id,
                source_text=src_text,
                translated_text=tgt_text,
                source_lang=source_lang,
                target_lang=target_lang,
            )
            segment_verifications.append(verification)

        # Calculate report statistics
        total_segments = len(segment_verifications)
        passed_segments = sum(1 for v in segment_verifications if v.passed)
        failed_segments = total_segments - passed_segments

        total_issues = sum(len(v.issues) for v in segment_verifications)

        issues_by_type = {}
        issues_by_severity = {}
        for verification in segment_verifications:
            for issue in verification.issues:
                issues_by_type[issue.issue_type] = (
                    issues_by_type.get(issue.issue_type, 0) + 1
                )
                issues_by_severity[issue.severity] = (
                    issues_by_severity.get(issue.severity, 0) + 1
                )

        average_quality = (
            sum(v.quality_score for v in segment_verifications) / total_segments
            if total_segments > 0
            else 0.0
        )

        return VerificationReport(
            total_segments=total_segments,
            passed_segments=passed_segments,
            failed_segments=failed_segments,
            total_issues=total_issues,
            issues_by_type=issues_by_type,
            issues_by_severity=issues_by_severity,
            average_quality=average_quality,
            segments=segment_verifications,
        )

    def _verify_segment(
        self,
        segment_id: str,
        source_text: str,
        translated_text: str,
        source_lang: str,
        target_lang: str,
    ) -> SegmentVerification:
        """
        Verify a single translated segment.

        Args:
            segment_id: Segment identifier
            source_text: Original text
            translated_text: Translated text
            source_lang: Source language code
            target_lang: Target language code

        Returns:
            SegmentVerification result
        """
        issues = []

        # Check 1: Glossary term verification
        issues.extend(
            self._verify_glossary_terms(
                segment_id, source_text, translated_text, source_lang, target_lang
            )
        )

        # Check 2: Format preservation
        issues.extend(
            self._verify_format_preservation(segment_id, source_text, translated_text)
        )

        # Check 3: Placeholder integrity
        issues.extend(
            self._verify_placeholder_integrity(segment_id, source_text, translated_text)
        )

        # Check 4: Protected tokens
        issues.extend(
            self._verify_protected_tokens(segment_id, source_text, translated_text)
        )

        # Calculate quality score
        quality_score = self._calculate_quality_score(issues)

        # Determine if passed
        has_critical = any(i.severity == "critical" for i in issues)
        has_warnings = any(i.severity == "warning" for i in issues)

        passed = not has_critical
        if self.strict_mode:
            passed = passed and not has_warnings

        passed = passed and quality_score >= self.min_quality

        return SegmentVerification(
            segment_id=segment_id,
            source_text=source_text,
            translated_text=translated_text,
            issues=issues,
            quality_score=quality_score,
            passed=passed,
        )

    def _verify_glossary_terms(
        self,
        segment_id: str,
        source_text: str,
        translated_text: str,
        source_lang: str,
        target_lang: str,
    ) -> List[VerificationIssue]:
        """Verify correct usage of glossary terms."""
        issues = []

        # Find terms in source
        source_terms = self.matcher.find_terms(source_text, source_lang, target_lang)

        # Check if expected terms appear in translation
        for term_occ in source_terms:
            expected_translation = getattr(term_occ.entry, target_lang, "")
            if not expected_translation:
                continue

            # Check if term appears in translation
            translated_lower = translated_text.lower()
            expected_lower = expected_translation.lower()

            if expected_lower not in translated_lower:
                # Term is missing
                issue = VerificationIssue(
                    issue_type="missing_term",
                    severity="warning",
                    segment_id=segment_id,
                    description=f"Glossary term '{term_occ.matched_text}' not properly translated",
                    expected=expected_translation,
                    found=None,
                    suggestion=f"Should contain '{expected_translation}'",
                )
                issues.append(issue)

        # Check for untranslated source terms in translation (bidirectional check)
        target_terms = self.matcher.find_terms(
            translated_text, target_lang, source_lang, min_confidence=0.9
        )

        for term_occ in target_terms:
            if term_occ.strategy == "bidirectional":
                # Found source language term in translation
                issue = VerificationIssue(
                    issue_type="untranslated_term",
                    severity="warning",
                    segment_id=segment_id,
                    description=f"Untranslated term found: '{term_occ.matched_text}'",
                    expected=getattr(term_occ.entry, target_lang, ""),
                    found=term_occ.matched_text,
                    suggestion=f"Should be translated to '{getattr(term_occ.entry, target_lang, '')}'",
                )
                issues.append(issue)

        return issues

    def _verify_format_preservation(
        self, segment_id: str, source_text: str, translated_text: str
    ) -> List[VerificationIssue]:
        """Verify that formatting is preserved."""
        issues = []

        # Check newlines
        source_newlines = source_text.count("\n")
        translated_newlines = translated_text.count("\n")

        if source_newlines != translated_newlines:
            issue = VerificationIssue(
                issue_type="format_mismatch",
                severity="warning",
                segment_id=segment_id,
                description=f"Newline count mismatch",
                expected=f"{source_newlines} newlines",
                found=f"{translated_newlines} newlines",
            )
            issues.append(issue)

        # Check if translation is empty
        if not translated_text.strip():
            issue = VerificationIssue(
                issue_type="empty_translation",
                severity="critical",
                segment_id=segment_id,
                description="Translation is empty",
            )
            issues.append(issue)

        return issues

    def _verify_placeholder_integrity(
        self, segment_id: str, source_text: str, translated_text: str
    ) -> List[VerificationIssue]:
        """Verify that placeholders are preserved correctly."""
        issues = []

        # Find placeholders in source
        placeholder_pattern = r"<ph\s+id=['\"]([^'\"]+)['\"][\s/]*>"
        source_placeholders = set(re.findall(placeholder_pattern, source_text))
        translated_placeholders = set(re.findall(placeholder_pattern, translated_text))

        # Check for missing placeholders
        missing = source_placeholders - translated_placeholders
        if missing:
            issue = VerificationIssue(
                issue_type="missing_placeholder",
                severity="critical",
                segment_id=segment_id,
                description=f"Missing placeholders: {', '.join(missing)}",
                expected=f"{len(source_placeholders)} placeholders",
                found=f"{len(translated_placeholders)} placeholders",
            )
            issues.append(issue)

        # Check for extra placeholders
        extra = translated_placeholders - source_placeholders
        if extra:
            issue = VerificationIssue(
                issue_type="extra_placeholder",
                severity="critical",
                segment_id=segment_id,
                description=f"Extra placeholders: {', '.join(extra)}",
            )
            issues.append(issue)

        return issues

    def _verify_protected_tokens(
        self, segment_id: str, source_text: str, translated_text: str
    ) -> List[VerificationIssue]:
        """Verify that protected tokens are preserved."""
        issues = []

        # Get protected tokens from glossary
        protected_tokens = self.glossary.get_protected_tokens()

        for token in protected_tokens:
            # Check if token appears in source
            if token in source_text:
                # It should also appear in translation
                if token not in translated_text:
                    issue = VerificationIssue(
                        issue_type="missing_protected_token",
                        severity="warning",
                        segment_id=segment_id,
                        description=f"Protected token '{token}' not preserved",
                        expected=token,
                        found=None,
                    )
                    issues.append(issue)

        return issues

    def _calculate_quality_score(self, issues: List[VerificationIssue]) -> float:
        """
        Calculate quality score based on issues.

        Args:
            issues: List of verification issues

        Returns:
            Quality score (0.0-1.0)
        """
        if not issues:
            return 1.0

        # Weight by severity
        severity_weights = {"critical": 0.3, "warning": 0.1, "info": 0.05}

        total_penalty = 0.0
        for issue in issues:
            penalty = severity_weights.get(issue.severity, 0.05)
            total_penalty += penalty

        # Quality score decreases with penalties
        quality = max(0.0, 1.0 - total_penalty)

        return quality


__all__ = [
    "TranslationVerifier",
    "VerificationReport",
    "SegmentVerification",
    "VerificationIssue",
]
