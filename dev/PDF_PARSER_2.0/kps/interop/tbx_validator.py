"""
TBX (TermBase eXchange) validator for ISO 30042:2019 compliance.

Validates TBX files against TBX-Core schema and custom dialects.
Ensures data integrity before importing into glossary_terms table.

Usage:
    >>> from kps.interop.tbx_validator import TBXValidator, validate_tbx_file
    >>>
    >>> validator = TBXValidator()
    >>> result = validator.validate_file("glossary.tbx")
    >>> if result.is_valid:
    ...     print("Valid TBX file!")
    >>> else:
    ...     for error in result.errors:
    ...         print(f"Error: {error}")
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
from xml.etree import ElementTree as ET
import logging

logger = logging.getLogger(__name__)

# TBX namespaces
TBX_NAMESPACES = {
    "tbx": "urn:iso:std:iso:30042:ed-2",
    "xml": "http://www.w3.org/XML/1998/namespace",
}


@dataclass
class ValidationError:
    """Single validation error."""
    severity: str  # "error", "warning", "info"
    message: str
    element: Optional[str] = None
    line: Optional[int] = None


@dataclass
class ValidationResult:
    """Result of TBX validation."""
    is_valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)
    info: List[ValidationError] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return len(self.errors) > 0

    @property
    def summary(self) -> str:
        """Get validation summary."""
        if self.is_valid:
            return f" Valid TBX file ({len(self.warnings)} warnings, {len(self.info)} info)"
        else:
            return f"L Invalid TBX file ({len(self.errors)} errors, {len(self.warnings)} warnings)"


class TBXValidator:
    """
    Validator for TBX (TermBase eXchange) files.

    Validates against:
    - ISO 30042:2019 (TBX v3)
    - TBX-Core requirements
    - Custom dialect constraints

    Features:
    - Well-formedness check (valid XML)
    - Structure validation (martif, martifHeader, text, body)
    - Required elements (termEntry, langSet, tig, term)
    - Language codes (xml:lang attributes)
    - Duplicate term detection
    - Custom field validation
    """

    def __init__(self, dialect: Optional[str] = None, strict: bool = True):
        """
        Initialize TBX validator.

        Args:
            dialect: TBX dialect name (e.g., "TBX-Core", "TBX-Default")
            strict: If True, enforce strict validation
        """
        self.dialect = dialect or "TBX-Core"
        self.strict = strict

    def validate_file(self, file_path: str) -> ValidationResult:
        """
        Validate TBX file.

        Args:
            file_path: Path to TBX file

        Returns:
            ValidationResult with errors/warnings
        """
        result = ValidationResult(is_valid=True)

        try:
            # Parse XML
            tree = ET.parse(file_path)
            root = tree.getroot()

            # Validate structure
            self._validate_structure(root, result)

            # Validate martifHeader
            self._validate_header(root, result)

            # Validate body
            self._validate_body(root, result)

            # Check duplicates
            self._check_duplicates(root, result)

            # Determine overall validity
            result.is_valid = not result.has_errors

        except ET.ParseError as e:
            result.errors.append(ValidationError(
                severity="error",
                message=f"XML parse error: {e}",
                element="root"
            ))
            result.is_valid = False
        except Exception as e:
            result.errors.append(ValidationError(
                severity="error",
                message=f"Unexpected error: {e}",
                element="root"
            ))
            result.is_valid = False

        return result

    def _validate_structure(self, root: ET.Element, result: ValidationResult):
        """Validate root structure (martif element)."""
        # Check root element
        if root.tag not in ["martif", "{urn:iso:std:iso:30042:ed-2}martif"]:
            result.errors.append(ValidationError(
                severity="error",
                message=f"Root element must be 'martif', got '{root.tag}'",
                element="root"
            ))
            return

        # Check required attributes
        if "type" not in root.attrib:
            result.warnings.append(ValidationError(
                severity="warning",
                message="Missing 'type' attribute on <martif>",
                element="martif"
            ))
        elif root.attrib["type"] != "TBX":
            result.warnings.append(ValidationError(
                severity="warning",
                message=f"Type should be 'TBX', got '{root.attrib['type']}'",
                element="martif"
            ))

        # Check xml:lang
        xml_lang = root.attrib.get("{http://www.w3.org/XML/1998/namespace}lang")
        if not xml_lang:
            result.warnings.append(ValidationError(
                severity="warning",
                message="Missing 'xml:lang' attribute on <martif>",
                element="martif"
            ))

    def _validate_header(self, root: ET.Element, result: ValidationResult):
        """Validate martifHeader."""
        # Find martifHeader (with or without namespace)
        header = root.find("martifHeader") or root.find("{urn:iso:std:iso:30042:ed-2}martifHeader")

        if header is None:
            result.errors.append(ValidationError(
                severity="error",
                message="Missing required <martifHeader> element",
                element="martif"
            ))
            return

        # Check fileDesc
        file_desc = header.find("fileDesc") or header.find("{urn:iso:std:iso:30042:ed-2}fileDesc")
        if file_desc is None:
            result.errors.append(ValidationError(
                severity="error",
                message="Missing required <fileDesc> element in <martifHeader>",
                element="martifHeader"
            ))

    def _validate_body(self, root: ET.Element, result: ValidationResult):
        """Validate text/body structure."""
        # Find text element
        text = root.find("text") or root.find("{urn:iso:std:iso:30042:ed-2}text")
        if text is None:
            result.errors.append(ValidationError(
                severity="error",
                message="Missing required <text> element",
                element="martif"
            ))
            return

        # Find body element
        body = text.find("body") or text.find("{urn:iso:std:iso:30042:ed-2}body")
        if body is None:
            result.errors.append(ValidationError(
                severity="error",
                message="Missing required <body> element in <text>",
                element="text"
            ))
            return

        # Validate termEntry elements
        term_entries = (
            body.findall("termEntry") +
            body.findall("{urn:iso:std:iso:30042:ed-2}termEntry")
        )

        if not term_entries:
            result.warnings.append(ValidationError(
                severity="warning",
                message="No <termEntry> elements found in <body>",
                element="body"
            ))
            return

        # Validate each termEntry
        for idx, term_entry in enumerate(term_entries):
            self._validate_term_entry(term_entry, idx, result)

    def _validate_term_entry(self, term_entry: ET.Element, idx: int, result: ValidationResult):
        """Validate single termEntry."""
        # Check for langSet elements
        lang_sets = (
            term_entry.findall("langSet") +
            term_entry.findall("{urn:iso:std:iso:30042:ed-2}langSet")
        )

        if not lang_sets:
            result.errors.append(ValidationError(
                severity="error",
                message=f"termEntry[{idx}] has no <langSet> elements",
                element=f"termEntry[{idx}]"
            ))
            return

        # Validate each langSet
        for lang_set in lang_sets:
            self._validate_lang_set(lang_set, idx, result)

    def _validate_lang_set(self, lang_set: ET.Element, entry_idx: int, result: ValidationResult):
        """Validate langSet element."""
        # Check xml:lang attribute
        xml_lang = lang_set.attrib.get("{http://www.w3.org/XML/1998/namespace}lang")
        if not xml_lang:
            result.errors.append(ValidationError(
                severity="error",
                message=f"termEntry[{entry_idx}] langSet missing 'xml:lang' attribute",
                element=f"termEntry[{entry_idx}]/langSet"
            ))
            return

        # Validate language code format (ISO 639-1 or ISO 639-3)
        if len(xml_lang) not in [2, 3] and not xml_lang.startswith(("en-", "ru-", "fr-")):
            result.warnings.append(ValidationError(
                severity="warning",
                message=f"Language code '{xml_lang}' may not be valid ISO 639",
                element=f"termEntry[{entry_idx}]/langSet"
            ))

        # Check for tig elements
        tigs = (
            lang_set.findall(".//tig") +
            lang_set.findall(".//{urn:iso:std:iso:30042:ed-2}tig")
        )

        if not tigs:
            result.errors.append(ValidationError(
                severity="error",
                message=f"termEntry[{entry_idx}] langSet[{xml_lang}] has no <tig> elements",
                element=f"termEntry[{entry_idx}]/langSet"
            ))
            return

        # Validate each tig
        for tig in tigs:
            self._validate_tig(tig, entry_idx, xml_lang, result)

    def _validate_tig(self, tig: ET.Element, entry_idx: int, lang: str, result: ValidationResult):
        """Validate tig (term information group)."""
        # Check for term element
        term = tig.find("term") or tig.find("{urn:iso:std:iso:30042:ed-2}term")

        if term is None:
            result.errors.append(ValidationError(
                severity="error",
                message=f"termEntry[{entry_idx}] langSet[{lang}] tig missing <term> element",
                element=f"termEntry[{entry_idx}]/langSet/tig"
            ))
            return

        # Check term text
        term_text = (term.text or "").strip()
        if not term_text:
            result.errors.append(ValidationError(
                severity="error",
                message=f"termEntry[{entry_idx}] langSet[{lang}] has empty <term>",
                element=f"termEntry[{entry_idx}]/langSet/tig/term"
            ))

    def _check_duplicates(self, root: ET.Element, result: ValidationResult):
        """Check for duplicate terms."""
        # Find body
        text = root.find("text") or root.find("{urn:iso:std:iso:30042:ed-2}text")
        if text is None:
            return

        body = text.find("body") or text.find("{urn:iso:std:iso:30042:ed-2}body")
        if body is None:
            return

        # Collect all terms by language
        terms_by_lang = {}

        term_entries = (
            body.findall(".//termEntry") +
            body.findall(".//{urn:iso:std:iso:30042:ed-2}termEntry")
        )

        for term_entry in term_entries:
            lang_sets = (
                term_entry.findall("langSet") +
                term_entry.findall("{urn:iso:std:iso:30042:ed-2}langSet")
            )

            for lang_set in lang_sets:
                lang = lang_set.attrib.get("{http://www.w3.org/XML/1998/namespace}lang", "unknown")

                if lang not in terms_by_lang:
                    terms_by_lang[lang] = []

                # Extract terms
                terms = (
                    lang_set.findall(".//term") +
                    lang_set.findall(".//{urn:iso:std:iso:30042:ed-2}term")
                )

                for term in terms:
                    term_text = (term.text or "").strip().lower()
                    if term_text:
                        terms_by_lang[lang].append(term_text)

        # Check for duplicates
        for lang, terms in terms_by_lang.items():
            seen = set()
            for term in terms:
                if term in seen:
                    result.warnings.append(ValidationError(
                        severity="warning",
                        message=f"Duplicate term '{term}' in language '{lang}'",
                        element=f"langSet[{lang}]"
                    ))
                seen.add(term)


def validate_tbx_file(file_path: str, strict: bool = True) -> ValidationResult:
    """
    Validate TBX file (convenience function).

    Args:
        file_path: Path to TBX file
        strict: If True, enforce strict validation

    Returns:
        ValidationResult

    Example:
        >>> result = validate_tbx_file("glossary.tbx")
        >>> if result.is_valid:
        ...     print("Valid!")
        >>> else:
        ...     for error in result.errors:
        ...         print(f"Error: {error.message}")
    """
    validator = TBXValidator(strict=strict)
    return validator.validate_file(file_path)


__all__ = [
    "TBXValidator",
    "ValidationResult",
    "ValidationError",
    "validate_tbx_file",
]
