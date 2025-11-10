"""IDML structure parser.

Parses IDML (InDesign Markup Language) files and provides structured access
to document components: stories, spreads, graphics, and styles.

IDML Structure Overview:
    - designmap.xml: Manifest listing all document components
    - Stories/*.xml: Text content and inline objects
    - Spreads/*.xml: Page layouts and object positioning
    - XML/BackingStory.xml: Document metadata
    - Resources/Styles.xml: Paragraph/character styles

References:
    - IDML Specification: http://wwwimages.adobe.com/www.adobe.com/content/dam/acom/en/devnet/indesign/sdk/cs6/idml/idml-specification.pdf
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
import xml.etree.ElementTree as ET

from .idml_utils import (
    unzip_idml,
    parse_xml_file,
    get_story_files,
    get_spread_files,
    validate_idml_structure,
)


@dataclass
class IDMLStory:
    """
    Represents a single Story in IDML.

    A Story contains text content with formatting and inline objects.
    Multiple text frames can be threaded to show the same story.

    Attributes:
        story_id: Story identifier (e.g., "u123")
        xml_tree: Parsed XML ElementTree
        root: Root Element (Story element)
        file_path: Path to Story_*.xml file
    """

    story_id: str
    xml_tree: ET.ElementTree
    root: ET.Element
    file_path: Path

    @property
    def self_id(self) -> str:
        """Get Self attribute of Story element."""
        return self.root.get("Self", "")

    def get_all_text(self) -> str:
        """
        Extract all text content from story.

        Returns:
            Concatenated text from all Content elements
        """
        texts = []
        for content in self.root.iter("Content"):
            if content.text:
                texts.append(content.text)
        return "".join(texts)

    def find_paragraphs(self) -> List[ET.Element]:
        """
        Find all ParagraphStyleRange elements.

        Returns:
            List of paragraph elements
        """
        return self.root.findall(".//ParagraphStyleRange")

    def find_inline_objects(self) -> List[ET.Element]:
        """
        Find all inline objects (Rectangle, TextFrame, etc.) in story.

        Returns:
            List of inline object elements
        """
        objects = []
        # Look for common inline object types
        for tag in ["Rectangle", "TextFrame", "Oval", "Polygon", "GraphicLine"]:
            objects.extend(self.root.findall(f".//{tag}"))
        return objects


@dataclass
class IDMLSpread:
    """
    Represents a single Spread in IDML.

    A Spread contains one or more pages with positioned objects.

    Attributes:
        spread_id: Spread identifier (e.g., "ub6")
        xml_tree: Parsed XML ElementTree
        root: Root Element (Spread element)
        file_path: Path to Spread_*.xml file
    """

    spread_id: str
    xml_tree: ET.ElementTree
    root: ET.Element
    file_path: Path

    @property
    def self_id(self) -> str:
        """Get Self attribute of Spread element."""
        return self.root.get("Self", "")

    def get_pages(self) -> List[ET.Element]:
        """
        Get all Page elements in spread.

        Returns:
            List of Page elements
        """
        return self.root.findall(".//Page")

    def get_all_rectangles(self) -> List[ET.Element]:
        """
        Get all Rectangle elements (often used for image frames).

        Returns:
            List of Rectangle elements
        """
        return self.root.findall(".//Rectangle")

    def get_all_text_frames(self) -> List[ET.Element]:
        """
        Get all TextFrame elements.

        Returns:
            List of TextFrame elements
        """
        return self.root.findall(".//TextFrame")


@dataclass
class IDMLDocument:
    """
    Complete parsed IDML document structure.

    Provides access to all components of an IDML file.

    Attributes:
        designmap_tree: Parsed designmap.xml (manifest)
        stories: Dictionary of story_id -> IDMLStory
        spreads: Dictionary of spread_id -> IDMLSpread
        backing_story: Optional BackingStory.xml (metadata)
        styles_tree: Optional Styles.xml (paragraph/character styles)
        temp_dir: Temporary directory where IDML was extracted
        source_path: Original IDML file path
    """

    designmap_tree: ET.ElementTree
    stories: Dict[str, IDMLStory] = field(default_factory=dict)
    spreads: Dict[str, IDMLSpread] = field(default_factory=dict)
    backing_story: Optional[ET.ElementTree] = None
    styles_tree: Optional[ET.ElementTree] = None
    temp_dir: Path = None
    source_path: Optional[Path] = None

    @property
    def designmap_root(self) -> ET.Element:
        """Get root element of designmap."""
        return self.designmap_tree.getroot()

    def get_story(self, story_id: str) -> Optional[IDMLStory]:
        """
        Get story by ID.

        Args:
            story_id: Story identifier (e.g., "u123" or "Story_u123")

        Returns:
            IDMLStory if found, None otherwise
        """
        # Handle both "u123" and "Story_u123" formats
        clean_id = story_id.replace("Story_", "")
        return self.stories.get(clean_id)

    def get_spread(self, spread_id: str) -> Optional[IDMLSpread]:
        """
        Get spread by ID.

        Args:
            spread_id: Spread identifier (e.g., "ub6" or "Spread_ub6")

        Returns:
            IDMLSpread if found, None otherwise
        """
        # Handle both "ub6" and "Spread_ub6" formats
        clean_id = spread_id.replace("Spread_", "")
        return self.spreads.get(clean_id)

    def find_story_by_content(self, search_text: str) -> List[IDMLStory]:
        """
        Find stories containing specific text.

        Args:
            search_text: Text to search for

        Returns:
            List of stories containing the text
        """
        results = []
        for story in self.stories.values():
            if search_text in story.get_all_text():
                results.append(story)
        return results

    def get_all_inline_objects(self) -> List[tuple[IDMLStory, ET.Element]]:
        """
        Get all inline objects across all stories.

        Returns:
            List of (story, element) tuples for each inline object
        """
        objects = []
        for story in self.stories.values():
            for obj in story.find_inline_objects():
                objects.append((story, obj))
        return objects


class IDMLParser:
    """
    Parser for IDML files.

    Usage:
        >>> parser = IDMLParser()
        >>> doc = parser.parse_idml(Path("document.idml"))
        >>> print(f"Found {len(doc.stories)} stories")
        >>> print(f"Found {len(doc.spreads)} spreads")
    """

    def parse_idml(
        self, idml_path: Path, cleanup_temp: bool = False
    ) -> IDMLDocument:
        """
        Parse IDML file into structured document.

        Args:
            idml_path: Path to IDML file
            cleanup_temp: If True, delete temp directory on error (default: False)
                         Note: Caller should cleanup temp_dir after done

        Returns:
            Parsed IDMLDocument

        Raises:
            FileNotFoundError: If IDML file doesn't exist
            ValueError: If IDML structure is invalid
            ET.ParseError: If XML is malformed

        Example:
            >>> parser = IDMLParser()
            >>> doc = parser.parse_idml(Path("doc.idml"))
            >>> try:
            ...     # Work with document
            ...     for story in doc.stories.values():
            ...         print(story.get_all_text())
            ... finally:
            ...     # Cleanup temp directory
            ...     from .idml_utils import cleanup_temp_dir
            ...     cleanup_temp_dir(doc.temp_dir)
        """
        if not idml_path.exists():
            raise FileNotFoundError(f"IDML file not found: {idml_path}")

        # Extract IDML to temp directory
        temp_dir = unzip_idml(idml_path)

        try:
            # Validate structure
            if not validate_idml_structure(temp_dir):
                raise ValueError(f"Invalid IDML structure in {idml_path}")

            # Parse designmap.xml (manifest)
            designmap_tree = parse_xml_file(temp_dir / "designmap.xml")

            # Parse all stories
            stories = self._parse_stories(temp_dir)

            # Parse all spreads
            spreads = self._parse_spreads(temp_dir)

            # Parse BackingStory.xml (metadata) if exists
            backing_story = None
            backing_story_path = temp_dir / "XML" / "BackingStory.xml"
            if backing_story_path.exists():
                backing_story = parse_xml_file(backing_story_path)

            # Parse Styles.xml if exists
            styles_tree = None
            styles_path = temp_dir / "Resources" / "Styles.xml"
            if styles_path.exists():
                styles_tree = parse_xml_file(styles_path)

            return IDMLDocument(
                designmap_tree=designmap_tree,
                stories=stories,
                spreads=spreads,
                backing_story=backing_story,
                styles_tree=styles_tree,
                temp_dir=temp_dir,
                source_path=idml_path,
            )

        except Exception as e:
            # Cleanup on error if requested
            if cleanup_temp:
                from .idml_utils import cleanup_temp_dir

                cleanup_temp_dir(temp_dir)
            raise

    def _parse_stories(self, idml_dir: Path) -> Dict[str, IDMLStory]:
        """
        Parse all Story XML files.

        Args:
            idml_dir: Extracted IDML directory

        Returns:
            Dictionary of story_id -> IDMLStory
        """
        stories = {}

        for story_file in get_story_files(idml_dir):
            # Extract story ID from filename: "Story_u123.xml" -> "u123"
            story_id = story_file.stem.replace("Story_", "")

            tree = parse_xml_file(story_file)
            root = tree.getroot()

            story = IDMLStory(
                story_id=story_id, xml_tree=tree, root=root, file_path=story_file
            )

            stories[story_id] = story

        return stories

    def _parse_spreads(self, idml_dir: Path) -> Dict[str, IDMLSpread]:
        """
        Parse all Spread XML files.

        Args:
            idml_dir: Extracted IDML directory

        Returns:
            Dictionary of spread_id -> IDMLSpread
        """
        spreads = {}

        for spread_file in get_spread_files(idml_dir):
            # Extract spread ID from filename: "Spread_ub6.xml" -> "ub6"
            spread_id = spread_file.stem.replace("Spread_", "")

            tree = parse_xml_file(spread_file)
            root = tree.getroot()

            spread = IDMLSpread(
                spread_id=spread_id, xml_tree=tree, root=root, file_path=spread_file
            )

            spreads[spread_id] = spread

        return spreads


def find_story_for_text_frame(
    doc: IDMLDocument, text_frame_id: str
) -> Optional[IDMLStory]:
    """
    Find the story associated with a text frame.

    Text frames reference stories via ParentStory attribute.

    Args:
        doc: Parsed IDML document
        text_frame_id: Self attribute of text frame

    Returns:
        IDMLStory if found, None otherwise

    Example:
        >>> story = find_story_for_text_frame(doc, "u1a3")
        >>> if story:
        ...     print(f"Frame {text_frame_id} uses story {story.story_id}")
    """
    # Search spreads for text frame
    for spread in doc.spreads.values():
        for text_frame in spread.get_all_text_frames():
            if text_frame.get("Self") == text_frame_id:
                # Get ParentStory reference
                parent_story = text_frame.get("ParentStory")
                if parent_story:
                    return doc.get_story(parent_story)

    return None


def find_text_frames_for_story(doc: IDMLDocument, story_id: str) -> List[ET.Element]:
    """
    Find all text frames that display a story.

    A story can be displayed in multiple threaded text frames.

    Args:
        doc: Parsed IDML document
        story_id: Story identifier

    Returns:
        List of TextFrame elements that reference this story

    Example:
        >>> frames = find_text_frames_for_story(doc, "u123")
        >>> print(f"Story displayed in {len(frames)} frames")
    """
    frames = []
    story = doc.get_story(story_id)
    if not story:
        return frames

    # Clean story ID for comparison
    clean_story_id = story.self_id

    # Search all spreads for text frames
    for spread in doc.spreads.values():
        for text_frame in spread.get_all_text_frames():
            parent_story = text_frame.get("ParentStory", "")
            # Handle both "u123" and "Story_u123" references
            clean_parent = parent_story.replace("Story_", "")
            if clean_parent == story_id or clean_parent == clean_story_id:
                frames.append(text_frame)

    return frames


def get_idml_version(doc: IDMLDocument) -> str:
    """
    Get IDML version from designmap.

    Args:
        doc: Parsed IDML document

    Returns:
        Version string (e.g., "7.5" for CS6)

    Example:
        >>> version = get_idml_version(doc)
        >>> print(f"IDML version: {version}")
    """
    root = doc.designmap_root
    return root.get("IDMLVersion", "unknown")


def get_document_properties(doc: IDMLDocument) -> dict:
    """
    Extract document properties from BackingStory.

    Args:
        doc: Parsed IDML document

    Returns:
        Dictionary of document properties

    Example:
        >>> props = get_document_properties(doc)
        >>> print(f"Title: {props.get('title', 'Untitled')}")
    """
    if not doc.backing_story:
        return {}

    properties = {}
    root = doc.backing_story.getroot()

    # Extract common properties
    for prop in root.findall(".//Property"):
        name = prop.get("name", "")
        value = prop.text or ""
        properties[name] = value

    return properties
