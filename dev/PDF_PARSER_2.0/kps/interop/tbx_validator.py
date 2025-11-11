"""Lightweight TBX (ISO 30042) structural validator."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import List


@dataclass
class TBXValidationIssue:
    level: str  # "error" | "warning"
    message: str


@dataclass
class TBXValidationResult:
    is_valid: bool
    issues: List[TBXValidationIssue]


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _is_lang_code(value: str) -> bool:
    value = value or ""
    if len(value) < 2 or len(value) > 10:
        return False
    return all(part.isalpha() for part in value.split("-"))


def validate_tbx_file(path_tbx: str) -> TBXValidationResult:
    issues: List[TBXValidationIssue] = []

    try:
        tree = ET.parse(path_tbx)
    except Exception as exc:  # pragma: no cover - parsing errors depend on xml library
        return TBXValidationResult(
            is_valid=False,
            issues=[TBXValidationIssue(level="error", message=f"XML parse error: {exc}")],
        )

    root = tree.getroot()
    if _local(root.tag) != "martif":
        issues.append(TBXValidationIssue(level="error", message="Root element must be <martif>"))

    term_entries = root.findall(".//{*}termEntry") or root.findall(".//termEntry")
    if not term_entries:
        issues.append(TBXValidationIssue(level="error", message="No <termEntry> elements found"))

    for entry in term_entries:
        lang_sets = entry.findall("./{*}langSet") or entry.findall("./langSet")
        if not lang_sets:
            issues.append(TBXValidationIssue(level="error", message="termEntry without langSet"))
            continue

        for lang in lang_sets:
            lang_code = (
                lang.attrib.get("{http://www.w3.org/XML/1998/namespace}lang")
                or lang.attrib.get("lang")
                or ""
            )
            if not _is_lang_code(lang_code.lower()):
                issues.append(
                    TBXValidationIssue(
                        level="error",
                        message=f"Invalid xml:lang value '{lang_code}'",
                    )
                )

            terms = lang.findall(".//{*}term") or lang.findall(".//term")
            if not terms:
                issues.append(
                    TBXValidationIssue(
                        level="warning",
                        message=f"langSet '{lang_code}' has no <term> entries",
                    )
                )

    is_valid = not any(issue.level == "error" for issue in issues)
    return TBXValidationResult(is_valid=is_valid, issues=issues)


__all__ = ["TBXValidationIssue", "TBXValidationResult", "validate_tbx_file"]
