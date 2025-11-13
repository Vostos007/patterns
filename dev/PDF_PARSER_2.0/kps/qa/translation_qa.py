"""Translation-specific QA gate ensuring glossary and formatting compliance."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Dict, List, Sequence, Optional

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
        len_ratio_overrides: Optional[Dict[tuple[str, str], tuple[float, float]]] = None,
    ) -> None:
        self.term_validator = term_validator
        self.min_pass_rate = min_pass_rate
        self.min_len_ratio = min_len_ratio
        self.max_len_ratio = max_len_ratio
        self.max_token_len = max_token_len
        self.len_ratio_overrides = len_ratio_overrides or {}
        self._placeholder_re = re.compile(r"<ph[^>]*?/?>|\[\[[^\]]+\]\]")

    def check_batch(self, segments: Sequence[Dict[str, str]]) -> QABatchResult:
        findings: List[QAFinding] = []
        passed = 0

        for record in segments:
            segment_id = record.get("id", "unknown")
            src_raw = record.get("src", "")
            tgt_raw = record.get("tgt", "")
            src = self._strip_placeholders(src_raw)
            tgt = self._strip_placeholders(tgt_raw)
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

            min_ratio, max_ratio = self._resolve_len_ratio(src_lang, tgt_lang)
            src_len = len(src.strip())
            tgt_len = len(tgt.strip())
            if min(src_len, tgt_len) > 15:
                ratio = (tgt_len + 1) / (src_len + 1)
                if ratio < min_ratio or ratio > max_ratio:
                    findings.append(
                        QAFinding(
                            kind="len_ratio",
                            detail=f"ratio={ratio:.2f}",
                            segment_id=segment_id,
                        )
                    )
                    issues = True

            for token in tgt_raw.split():
                if self._placeholder_re.fullmatch(token.strip()):
                    continue
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
        epsilon = 1e-6
        return QABatchResult(
            passed=(pass_rate + epsilon) >= self.min_pass_rate,
            findings=findings,
            pass_rate=pass_rate,
        )

    def _resolve_len_ratio(
        self, source_lang: str, target_lang: str
    ) -> tuple[float, float]:
        key = (source_lang.lower(), target_lang.lower())
        if key in self.len_ratio_overrides:
            return self.len_ratio_overrides[key]
        return self.min_len_ratio, self.max_len_ratio

    def _strip_placeholders(self, text: str) -> str:
        cleaned = self._placeholder_re.sub("", text)
        return cleaned.strip()


__all__ = [
    "QAFinding",
    "QABatchResult",
    "TranslationQAGate",
]
