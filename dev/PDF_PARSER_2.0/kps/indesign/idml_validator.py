"""IDML validation system.

Validates IDML structure, XML syntax, and InDesign compatibility.
Helps catch issues before opening in InDesign.

Validation Levels:
    1. Basic: File structure and mimetype
    2. Structure: Required files and directories
    3. XML: Well-formed XML in all files
    4. References: Valid cross-references between files
    5. Anchoring: Valid anchored object settings

Usage:
    >>> validator = IDMLValidator()
    >>> result = validator.validate(Path("output.idml"))
    >>> if result.is_valid:
    ...     print("IDML is valid!")
    ... else:
    ...     for error in result.errors:
    ...         print(f"ERROR: {error}")
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set
import xml.etree.ElementTree as ET

from .idml_utils import unzip_idml, validate_idml_structure, cleanup_temp_dir
from .idml_parser import IDMLParser


@dataclass
class ValidationResult:
    """
    Result of IDML validation.

    Attributes:
        is_valid: True if IDML passes all checks
        errors: List of error messages
        warnings: List of warning messages
        info: List of informational messages
    """

    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    info: List[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        """Add error message and mark as invalid."""
        self.errors.append(message)
        self.is_valid = False

    def add_warning(self, message: str) -> None:
        """Add warning message (doesn't affect validity)."""
        self.warnings.append(message)

    def add_info(self, message: str) -> None:
        """Add informational message."""
        self.info.append(message)

    def __str__(self) -> str:
        """Format validation result as string."""
        lines = []
        lines.append(f"Validation: {'PASS' if self.is_valid else 'FAIL'}")

        if self.errors:
            lines.append(f"\nErrors ({len(self.errors)}):")
            for err in self.errors:
                lines.append(f"  - {err}")

        if self.warnings:
            lines.append(f"\nWarnings ({len(self.warnings)}):")
            for warn in self.warnings:
                lines.append(f"  - {warn}")

        if self.info:
            lines.append(f"\nInfo ({len(self.info)}):")
            for info in self.info:
                lines.append(f"  - {info}")

        return "\n".join(lines)


class IDMLValidator:
    """
    IDML validation system.

    Performs multi-level validation of IDML files.
    """

    def __init__(self):
        """Initialize validator."""
        self.parser = IDMLParser()

    def validate(
        self, idml_path: Path, cleanup: bool = True
    ) -> ValidationResult:
        """
        Validate IDML file.

        Performs comprehensive validation:
            1. File existence and ZIP structure
            2. IDML directory structure
            3. XML well-formedness
            4. Cross-references
            5. Anchored object settings

        Args:
            idml_path: Path to IDML file
            cleanup: Cleanup temp directory after validation

        Returns:
            ValidationResult with errors, warnings, and info

        Example:
            >>> validator = IDMLValidator()
            >>> result = validator.validate(Path("output.idml"))
            >>> print(result)
        """
        result = ValidationResult(is_valid=True)

        # Level 1: Basic file validation
        if not self._validate_file_exists(idml_path, result):
            return result

        # Level 2: Extract and validate structure
        try:
            temp_dir = unzip_idml(idml_path)
        except Exception as e:
            result.add_error(f"Failed to extract IDML: {e}")
            return result

        try:
            # Level 3: Structure validation
            self._validate_structure(temp_dir, result)

            if not result.is_valid:
                return result

            # Level 4: XML validation
            self._validate_xml(temp_dir, result)

            # Level 5: Parse and validate content
            if result.is_valid:
                try:
                    doc = self.parser.parse_idml(idml_path)
                    self._validate_content(doc, result)
                    self._validate_references(doc, result)
                    self._validate_anchored_objects(doc, result)

                    # Add info about document
                    result.add_info(f"Stories: {len(doc.stories)}")
                    result.add_info(f"Spreads: {len(doc.spreads)}")

                except Exception as e:
                    result.add_error(f"Failed to parse IDML: {e}")

        finally:
            if cleanup:
                cleanup_temp_dir(temp_dir)

        return result

    def _validate_file_exists(
        self, idml_path: Path, result: ValidationResult
    ) -> bool:
        """Validate file existence."""
        if not idml_path.exists():
            result.add_error(f"IDML file not found: {idml_path}")
            return False

        if not idml_path.is_file():
            result.add_error(f"Path is not a file: {idml_path}")
            return False

        result.add_info(f"File size: {idml_path.stat().st_size} bytes")
        return True

    def _validate_structure(
        self, idml_dir: Path, result: ValidationResult
    ) -> None:
        """Validate IDML directory structure."""
        if not validate_idml_structure(idml_dir):
            result.add_error("Invalid IDML structure")
            return

        # Check required files
        required = {
            "mimetype": "Mimetype file",
            "designmap.xml": "Design map manifest",
            "Stories": "Stories directory",
            "Spreads": "Spreads directory",
        }

        for item, desc in required.items():
            path = idml_dir / item
            if not path.exists():
                result.add_error(f"Missing {desc}: {item}")

        # Check mimetype content
        mimetype_path = idml_dir / "mimetype"
        if mimetype_path.exists():
            try:
                content = mimetype_path.read_text().strip()
                expected = "application/vnd.adobe.indesign-idml-package"
                if content != expected:
                    result.add_error(
                        f"Invalid mimetype: got '{content}', expected '{expected}'"
                    )
            except Exception as e:
                result.add_error(f"Failed to read mimetype: {e}")

    def _validate_xml(self, idml_dir: Path, result: ValidationResult) -> None:
        """Validate XML well-formedness in all files."""
        xml_files = []

        # Collect all XML files
        xml_files.append(idml_dir / "designmap.xml")
        xml_files.extend((idml_dir / "Stories").glob("*.xml"))
        xml_files.extend((idml_dir / "Spreads").glob("*.xml"))

        # Add optional XML files
        optional = [
            idml_dir / "XML" / "BackingStory.xml",
            idml_dir / "Resources" / "Styles.xml",
        ]
        xml_files.extend([f for f in optional if f.exists()])

        # Validate each file
        for xml_file in xml_files:
            try:
                ET.parse(xml_file)
            except ET.ParseError as e:
                result.add_error(f"XML parse error in {xml_file.name}: {e}")
            except Exception as e:
                result.add_error(f"Error reading {xml_file.name}: {e}")

    def _validate_content(
        self, doc, result: ValidationResult
    ) -> None:
        """Validate document content."""
        # Check for empty stories
        empty_stories = []
        for story in doc.stories.values():
            if not story.get_all_text().strip():
                empty_stories.append(story.story_id)

        if empty_stories:
            result.add_warning(
                f"Empty stories found: {', '.join(empty_stories)}"
            )

        # Check for orphaned spreads (no pages)
        for spread in doc.spreads.values():
            pages = spread.get_pages()
            if not pages:
                result.add_warning(f"Spread {spread.spread_id} has no pages")

    def _validate_references(
        self, doc, result: ValidationResult
    ) -> None:
        """Validate cross-references between IDML components."""
        # Collect all Self IDs
        all_ids: Set[str] = set()

        for story in doc.stories.values():
            for elem in story.root.iter():
                self_id = elem.get("Self")
                if self_id:
                    all_ids.add(self_id)

        for spread in doc.spreads.values():
            for elem in spread.root.iter():
                self_id = elem.get("Self")
                if self_id:
                    all_ids.add(self_id)

        # Check ParentStory references in text frames
        for spread in doc.spreads.values():
            for text_frame in spread.get_all_text_frames():
                parent_story = text_frame.get("ParentStory")
                if parent_story:
                    # Clean reference (remove "Story_" prefix if present)
                    clean_ref = parent_story.replace("Story_", "")

                    # Check if story exists
                    if not doc.get_story(clean_ref):
                        result.add_error(
                            f"TextFrame references non-existent story: {parent_story}"
                        )

    def _validate_anchored_objects(
        self, doc, result: ValidationResult
    ) -> None:
        """Validate anchored object settings."""
        # Find all anchored objects
        anchored_count = 0

        for story in doc.stories.values():
            for elem in story.root.iter():
                anchor_settings = elem.find("AnchoredObjectSettings")
                if anchor_settings is not None:
                    anchored_count += 1
                    self._validate_anchor_settings(
                        anchor_settings, elem, result
                    )

        if anchored_count > 0:
            result.add_info(f"Anchored objects: {anchored_count}")

    def _validate_anchor_settings(
        self,
        anchor_elem: ET.Element,
        parent: ET.Element,
        result: ValidationResult,
    ) -> None:
        """Validate individual anchored object settings."""
        # Required attributes
        required = [
            "AnchoredPosition",
            "AnchorPoint",
        ]

        for attr in required:
            if not anchor_elem.get(attr):
                parent_id = parent.get("Self", "unknown")
                result.add_warning(
                    f"Anchored object {parent_id} missing attribute: {attr}"
                )

        # Validate AnchoredPosition value
        position = anchor_elem.get("AnchoredPosition")
        valid_positions = ["Anchored", "AboveLine", "InlinePosition"]
        if position and position not in valid_positions:
            result.add_error(
                f"Invalid AnchoredPosition: {position} "
                f"(must be one of {valid_positions})"
            )


def quick_validate(idml_path: Path) -> bool:
    """
    Quick validation for command-line usage.

    Args:
        idml_path: Path to IDML file

    Returns:
        True if valid, False otherwise

    Example:
        >>> from pathlib import Path
        >>> if quick_validate(Path("output.idml")):
        ...     print("Valid!")
        ... else:
        ...     print("Invalid!")
    """
    validator = IDMLValidator()
    result = validator.validate(idml_path)

    print(result)
    return result.is_valid


def validate_and_report(idml_path: Path, output_report: Optional[Path] = None) -> bool:
    """
    Validate IDML and optionally write report to file.

    Args:
        idml_path: Path to IDML file
        output_report: Optional path for report file

    Returns:
        True if valid

    Example:
        >>> validate_and_report(
        ...     Path("output.idml"),
        ...     Path("validation_report.txt")
        ... )
    """
    validator = IDMLValidator()
    result = validator.validate(idml_path)

    report = str(result)

    if output_report:
        output_report.write_text(report)
        print(f"Report written to: {output_report}")
    else:
        print(report)

    return result.is_valid
