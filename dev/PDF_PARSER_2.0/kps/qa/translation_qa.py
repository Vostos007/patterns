"""Translation-specific QA gate ensuring glossary and formatting compliance."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence

from kps.translation.term_validator import TermValidator


@dataclass
class QAFinding:
    kind: str
    detail: str
    segment_id: str


@dataclass
class QABatchResult:
    passed: bool
    findings: List[QAFinding]
    pass_rate: float


class TranslationQAGate:
    """Fail-closed QA gate for translated segments."""

    def __init__(
        self,
        term_validator: TermValidator,
        min_pass_rate: float = 0.98,
        min_len_ratio: float = 0.5,
        max_len_ratio: float = 2.0,
        max_token_len: int = 50,
    ) -> None:
        self.term_validator = term_validator
        self.min_pass_rate = min_pass_rate
        self.min_len_ratio = min_len_ratio
        self.max_len_ratio = max_len_ratio
        self.max_token_len = max_token_len

    def check_batch(self, segments: Sequence[Dict[str, str]]) -> QABatchResult:
        findings: List[QAFinding] = []
        passed = 0

        for record in segments:
            segment_id = record.get("id", "unknown")
            src = record.get("src", "")
            tgt = record.get("tgt", "")
            src_lang = record.get("src_lang", "ru")
            tgt_lang = record.get("tgt_lang", "en")

            issues = False

            violations = self.term_validator.validate(src, tgt, src_lang, tgt_lang)
            for violation in violations:
                kind = (
                    "brand_broken"
                    if violation.type == "do_not_translate_broken"
                    else violation.type
                )
                detail = violation.suggestion or violation.context or violation.rule.tgt
                findings.append(QAFinding(kind=kind, detail=detail, segment_id=segment_id))
                issues = True

            ratio = (len(tgt.strip()) + 1) / (len(src.strip()) + 1)
            if ratio < self.min_len_ratio or ratio > self.max_len_ratio:
                findings.append(
                    QAFinding(
                        kind="len_ratio",
                        detail=f"ratio={ratio:.2f}",
                        segment_id=segment_id,
                    )
                )
                issues = True

            for token in tgt.split():
                if len(token) > self.max_token_len:
                    findings.append(
                        QAFinding(
                            kind="long_token",
                            detail=token[:80],
                            segment_id=segment_id,
                        )
                    )
                    issues = True
                    break

            if not issues:
                passed += 1

        total = len(segments) or 1
        pass_rate = passed / total
        return QABatchResult(
            passed=pass_rate >= self.min_pass_rate,
            findings=findings,
            pass_rate=pass_rate,
        )


__all__ = [
    "QAFinding",
    "QABatchResult",
    "TranslationQAGate",
]
