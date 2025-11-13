"""IDML utilities for zip/unzip operations and XML helpers.

IDML (InDesign Markup Language) files are ZIP archives containing XML files
that define the document structure, content, and formatting.

Key IDML Structure:
    - mimetype (uncompressed, must be first)
    - designmap.xml (manifest)
    - Stories/*.xml (text content)
    - Spreads/*.xml (page layout)
    - XML/BackingStory.xml (metadata)
    - XML/Graphic.xml (graphic elements)
    - Resources/Styles.xml (styles)

References:
    - IDML Cookbook: http://wwwimages.adobe.com/www.adobe.com/content/dam/acom/en/devnet/indesign/sdk/cs6/idml/idml-cookbook.pdf
"""

import os
import tempfile
from pathlib import Path
from typing import Optional, List
from zipfile import ZipFile, ZIP_STORED, ZIP_DEFLATED
import xml.etree.ElementTree as ET
import shutil


# IDML namespace constants
IDML_NAMESPACES = {
    "idPkg": "http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging",
    "": "http://ns.adobe.com/AdobeInDesign/4.0",  # Default namespace
}

# Register namespaces for proper XML output
for prefix, uri in IDML_NAMESPACES.items():
    if prefix:  # Skip empty prefix
        ET.register_namespace(prefix, uri)


def unzip_idml(idml_path: Path, extract_to: Optional[Path] = None) -> Path:
    """
    Extract IDML file (ZIP archive) to directory.

    IDML files are standard ZIP archives. This function extracts all contents
    while preserving directory structure.

    Args:
        idml_path: Path to IDML file
        extract_to: Optional target directory. If None, creates temp directory.

    Returns:
        Path to extracted directory

    Raises:
        FileNotFoundError: If IDML file doesn't exist
        zipfile.BadZipFile: If file is not a valid ZIP archive

    Example:
        >>> idml_dir = unzip_idml(Path("document.idml"))
        >>> assert (idml_dir / "designmap.xml").exists()
        >>> assert (idml_dir / "Stories").is_dir()
    """
    if not idml_path.exists():
        raise FileNotFoundError(f"IDML file not found: {idml_path}")

    if extract_to is None:
        extract_to = Path(tempfile.mkdtemp(prefix="idml_"))

    extract_to.mkdir(parents=True, exist_ok=True)

    with ZipFile(idml_path, "r") as zip_ref:
        zip_ref.extractall(extract_to)

    return extract_to


def zip_idml(directory: Path, output_path: Path) -> None:
    """
    Package directory as IDML file (ZIP archive).

    CRITICAL: IDML requires specific ZIP structure:
        1. 'mimetype' file must be FIRST in archive
        2. 'mimetype' must be UNCOMPRESSED (ZIP_STORED)
        3. All other files use DEFLATE compression

    This is required for IDML to be recognized by InDesign.

    Args:
        directory: Directory containing extracted IDML contents
        output_path: Path for output IDML file

    Raises:
        FileNotFoundError: If directory or mimetype file doesn't exist
        ValueError: If directory structure is invalid

    Example:
        >>> zip_idml(Path("/tmp/idml_abc123"), Path("output.idml"))
    """
    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")

    mimetype_path = directory / "mimetype"
    if not mimetype_path.exists():
        raise ValueError(f"mimetype file missing in {directory}")

    # Create output directory if needed
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with ZipFile(output_path, "w") as zip_ref:
        # CRITICAL: Add mimetype first, uncompressed
        zip_ref.write(
            mimetype_path,
            arcname="mimetype",
            compress_type=ZIP_STORED,  # MUST be uncompressed
        )

        # Add all other files with compression
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file == "mimetype":
                    continue  # Already added

                file_path = Path(root) / file
                arcname = file_path.relative_to(directory)

                zip_ref.write(
                    file_path, arcname=str(arcname), compress_type=ZIP_DEFLATED
                )


def parse_xml_file(file_path: Path) -> ET.ElementTree:
    """
    Parse XML file with IDML namespace handling.

    Args:
        file_path: Path to XML file

    Returns:
        Parsed ElementTree

    Raises:
        FileNotFoundError: If file doesn't exist
        ET.ParseError: If XML is malformed
    """
    if not file_path.exists():
        raise FileNotFoundError(f"XML file not found: {file_path}")

    return ET.parse(file_path)


def write_xml_file(tree: ET.ElementTree, file_path: Path, pretty: bool = True) -> None:
    """
    Write ElementTree to XML file.

    Args:
        tree: ElementTree to write
        file_path: Output path
        pretty: If True, add indentation (development only, not production)

    Note:
        InDesign is sensitive to XML formatting. For production, use pretty=False
        to avoid introducing unwanted whitespace.
    """
    if not file_path.parent.exists():
        file_path.parent.mkdir(parents=True, exist_ok=True)

    if pretty:
        _indent_xml(tree.getroot())

    tree.write(
        file_path,
        encoding="utf-8",
        xml_declaration=True,
        method="xml",
    )


def _indent_xml(elem: ET.Element, level: int = 0) -> None:
    """
    Add indentation to XML tree for readability.

    Modifies tree in-place by adding tail and text whitespace.

    Args:
        elem: Root element
        level: Current indentation level (internal)
    """
    indent = "\n" + "  " * level
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = indent + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = indent
        for child in elem:
            _indent_xml(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = indent
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = indent


def find_element_by_self(root: ET.Element, self_id: str) -> Optional[ET.Element]:
    """
    Find element by 'Self' attribute (IDML's unique identifier).

    IDML uses 'Self' attribute as primary key for all elements.

    Args:
        root: Root element to search from
        self_id: Value of Self attribute to find

    Returns:
        Element if found, None otherwise

    Example:
        >>> root = tree.getroot()
        >>> rect = find_element_by_self(root, "u1a3")
        >>> if rect:
        ...     print(rect.get("Label"))
    """
    # Try XPath first (most efficient)
    try:
        result = root.find(f".//*[@Self='{self_id}']")
        if result is not None:
            return result
    except:
        pass

    # Fallback: manual traversal
    return _find_element_recursive(root, "Self", self_id)


def _find_element_recursive(
    elem: ET.Element, attr: str, value: str
) -> Optional[ET.Element]:
    """Recursively search for element by attribute value."""
    if elem.get(attr) == value:
        return elem

    for child in elem:
        result = _find_element_recursive(child, attr, value)
        if result is not None:
            return result

    return None


def get_story_files(idml_dir: Path) -> List[Path]:
    """
    Get all Story XML files from IDML directory.

    Args:
        idml_dir: Extracted IDML directory

    Returns:
        List of Story_*.xml file paths, sorted by name

    Example:
        >>> story_files = get_story_files(Path("/tmp/idml_abc"))
        >>> for story in story_files:
        ...     print(story.name)  # Story_u123.xml, Story_u456.xml, ...
    """
    stories_dir = idml_dir / "Stories"
    if not stories_dir.exists():
        return []

    return sorted(stories_dir.glob("Story_*.xml"))


def get_spread_files(idml_dir: Path) -> List[Path]:
    """
    Get all Spread XML files from IDML directory.

    Args:
        idml_dir: Extracted IDML directory

    Returns:
        List of Spread_*.xml file paths, sorted by name
    """
    spreads_dir = idml_dir / "Spreads"
    if not spreads_dir.exists():
        return []

    return sorted(spreads_dir.glob("Spread_*.xml"))


def cleanup_temp_dir(temp_dir: Path) -> None:
    """
    Clean up temporary IDML extraction directory.

    Args:
        temp_dir: Temporary directory to remove
    """
    if temp_dir.exists() and temp_dir.is_dir():
        shutil.rmtree(temp_dir)


def validate_idml_structure(idml_dir: Path) -> bool:
    """
    Validate basic IDML directory structure.

    Checks for required files and directories:
        - mimetype
        - designmap.xml
        - Stories/
        - Spreads/

    Args:
        idml_dir: Extracted IDML directory

    Returns:
        True if structure is valid, False otherwise

    Example:
        >>> idml_dir = unzip_idml(Path("doc.idml"))
        >>> if not validate_idml_structure(idml_dir):
        ...     raise ValueError("Invalid IDML structure")
    """
    required = ["mimetype", "designmap.xml", "Stories", "Spreads"]

    for item in required:
        path = idml_dir / item
        if not path.exists():
            return False

    # Check mimetype content
    mimetype_path = idml_dir / "mimetype"
    try:
        content = mimetype_path.read_text().strip()
        if content != "application/vnd.adobe.indesign-idml-package":
            return False
    except:
        return False

    return True


def create_idml_element(
    tag: str, attribs: Optional[dict] = None, text: Optional[str] = None
) -> ET.Element:
    """
    Create IDML XML element with proper namespace.

    Args:
        tag: Element tag name
        attribs: Optional attributes dictionary
        text: Optional text content

    Returns:
        Created Element

    Example:
        >>> rect = create_idml_element("Rectangle", {"Self": "u1a3", "Label": "img-abc"})
        >>> rect.set("ItemTransform", "1 0 0 1 100 200")
    """
    elem = ET.Element(tag, attribs or {})
    if text:
        elem.text = text
    return elem


def get_element_path(elem: ET.Element, root: ET.Element) -> str:
    """
    Get XPath-like path for element (for debugging).

    Args:
        elem: Element to get path for
        root: Root element

    Returns:
        Path string like "Story/ParagraphStyleRange/Rectangle"

    Example:
        >>> path = get_element_path(rect_elem, story_root)
        >>> print(f"Found at: {path}")
    """
    path = []
    current = elem

    # Walk up tree to root
    while current is not None and current != root:
        path.insert(0, current.tag)
        # Find parent (ElementTree doesn't have parent pointers)
        parent = _find_parent(root, current)
        current = parent

    return "/".join(path) if path else elem.tag


def _find_parent(root: ET.Element, target: ET.Element) -> Optional[ET.Element]:
    """Find parent element of target."""
    for elem in root.iter():
        for child in elem:
            if child == target:
                return elem
    return None
