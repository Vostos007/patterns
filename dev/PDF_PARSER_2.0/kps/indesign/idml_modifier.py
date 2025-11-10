"""IDML modification system.

Modifies IDML XML to add object labels, metadata, and anchored objects.
This is the core module for embedding KPS asset information into IDML.

Key Operations:
    1. Add labels and metadata to graphic objects
    2. Create anchored objects in story text
    3. Update object positioning and properties
    4. Maintain IDML validity

References:
    - IDML Cookbook: Object Labeling
    - InDesign Scripting: Label and metadata properties
"""

from pathlib import Path
from typing import Optional, Dict, Any
import xml.etree.ElementTree as ET
import json
import uuid

from .idml_parser import IDMLDocument, IDMLStory
from .anchoring import AnchoredObjectSettings, AnchorPoint, AnchoredPosition
from .idml_utils import find_element_by_self, write_xml_file, create_idml_element


class IDMLModifier:
    """
    Modifies IDML structure to add labels, metadata, and anchored objects.

    Usage:
        >>> modifier = IDMLModifier()
        >>> modifier.add_object_label(doc, "u1a3", "img-abc123", {"type": "image"})
        >>> modifier.create_anchored_object(
        ...     doc, "u123", 0, "assets/img.png", anchor_settings
        ... )
        >>> modifier.save_changes(doc)
    """

    def __init__(self):
        """Initialize IDML modifier."""
        self._namespace = "kps"  # Custom namespace for KPS metadata
        self._namespace_uri = "http://github.com/vostos/kps/1.0"

        # Register custom namespace
        ET.register_namespace(self._namespace, self._namespace_uri)

    def add_object_label(
        self,
        doc: IDMLDocument,
        object_ref: str,
        label: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Add label and metadata to IDML object.

        Searches all spreads and stories for object with given Self attribute,
        then adds Label attribute and optional KPS metadata.

        Args:
            doc: Parsed IDML document
            object_ref: Self attribute of object (e.g., "u1a3")
            label: Label to set (e.g., "img-abc123-p0-occ1")
            metadata: Optional metadata dictionary

        Returns:
            True if object found and modified, False otherwise

        Example:
            >>> success = modifier.add_object_label(
            ...     doc,
            ...     "u1a3",
            ...     "img-abc123-p0-occ1",
            ...     {"sha256": "abc...", "page": 0}
            ... )
            >>> print(f"Label added: {success}")
        """
        # Search spreads first (most common location for graphics)
        for spread in doc.spreads.values():
            element = find_element_by_self(spread.root, object_ref)
            if element is not None:
                self._set_label_and_metadata(element, label, metadata)
                return True

        # Search stories (for inline objects)
        for story in doc.stories.values():
            element = find_element_by_self(story.root, object_ref)
            if element is not None:
                self._set_label_and_metadata(element, label, metadata)
                return True

        return False

    def _set_label_and_metadata(
        self, element: ET.Element, label: str, metadata: Optional[Dict[str, Any]]
    ) -> None:
        """
        Set Label attribute and KPS metadata on element.

        Args:
            element: XML element to modify
            label: Label value
            metadata: Optional metadata dictionary
        """
        # Set Label attribute
        element.set("Label", label)

        # Add metadata if provided
        if metadata:
            # Store as JSON in custom namespace attribute
            metadata_json = json.dumps(metadata, ensure_ascii=False)
            metadata_attr = f"{{{self._namespace_uri}}}metadata"
            element.set(metadata_attr, metadata_json)

    def create_anchored_object(
        self,
        doc: IDMLDocument,
        story_id: str,
        insertion_point: int,
        graphic_path: str,
        anchor_settings: AnchoredObjectSettings,
        asset_id: Optional[str] = None,
        dimensions: Optional[tuple[float, float]] = None,
    ) -> Optional[str]:
        """
        Create anchored object in IDML story.

        Inserts a Rectangle with Image at specified insertion point in story text.
        The rectangle is configured as an anchored object with provided settings.

        Args:
            doc: Parsed IDML document
            story_id: Story to insert into
            insertion_point: Character position to insert at (0 = start)
            graphic_path: Path to graphic file (relative or absolute)
            anchor_settings: Anchored object configuration
            asset_id: Optional asset ID for labeling
            dimensions: Optional (width, height) in points; if None, uses 100x100

        Returns:
            Self ID of created Rectangle, or None if story not found

        Example:
            >>> from .anchoring import calculate_inline_anchor
            >>> settings = calculate_inline_anchor()
            >>> rect_id = modifier.create_anchored_object(
            ...     doc,
            ...     "u123",
            ...     0,
            ...     "assets/img-abc.png",
            ...     settings,
            ...     asset_id="img-abc123-p0-occ1",
            ...     dimensions=(200, 300)
            ... )
            >>> print(f"Created rectangle: {rect_id}")
        """
        story = doc.get_story(story_id)
        if not story:
            return None

        # Generate unique ID for rectangle
        rect_id = self._generate_unique_id(doc)

        # Default dimensions if not provided
        width, height = dimensions or (100.0, 100.0)

        # Create Rectangle element
        rectangle = self._create_rectangle_element(
            rect_id, anchor_settings, asset_id, width, height
        )

        # Create Image element inside Rectangle
        image = self._create_image_element(graphic_path, width, height)
        rectangle.append(image)

        # Insert into story at insertion point
        self._insert_into_story(story, rectangle, insertion_point)

        return rect_id

    def _generate_unique_id(self, doc: IDMLDocument) -> str:
        """
        Generate unique Self ID for new element.

        Uses UUID to ensure uniqueness across document.

        Args:
            doc: IDML document (for checking existing IDs)

        Returns:
            Unique ID string (e.g., "u1a3b5c7")
        """
        # Generate short UUID-based ID
        unique_id = f"u{uuid.uuid4().hex[:8]}"

        # Ensure uniqueness (unlikely collision, but safe)
        existing_ids = self._get_all_self_ids(doc)
        while unique_id in existing_ids:
            unique_id = f"u{uuid.uuid4().hex[:8]}"

        return unique_id

    def _get_all_self_ids(self, doc: IDMLDocument) -> set:
        """Get all Self attribute values in document."""
        ids = set()

        # Collect from stories
        for story in doc.stories.values():
            for elem in story.root.iter():
                self_id = elem.get("Self")
                if self_id:
                    ids.add(self_id)

        # Collect from spreads
        for spread in doc.spreads.values():
            for elem in spread.root.iter():
                self_id = elem.get("Self")
                if self_id:
                    ids.add(self_id)

        return ids

    def _create_rectangle_element(
        self,
        rect_id: str,
        anchor_settings: AnchoredObjectSettings,
        asset_id: Optional[str],
        width: float,
        height: float,
    ) -> ET.Element:
        """
        Create Rectangle XML element with anchored object settings.

        Args:
            rect_id: Unique Self ID
            anchor_settings: Anchoring configuration
            asset_id: Optional asset ID for Label
            width: Rectangle width in points
            height: Rectangle height in points

        Returns:
            Rectangle Element
        """
        # Base rectangle attributes
        rect_attrs = {
            "Self": rect_id,
            "ItemTransform": f"1 0 0 1 0 0",  # Identity transform
            "StrokeWeight": "0",
            "GradientFillStart": "0 0",
            "GradientFillLength": "0",
            "GradientFillAngle": "0",
            "GradientStrokeStart": "0 0",
            "GradientStrokeLength": "0",
            "GradientStrokeAngle": "0",
        }

        # Add label if provided
        if asset_id:
            rect_attrs["Label"] = asset_id

        # Create element
        rectangle = ET.Element("Rectangle", rect_attrs)

        # Add AnchoredObjectSettings as child element
        anchor_attrs = anchor_settings.to_idml_attributes()
        anchor_elem = ET.SubElement(rectangle, "AnchoredObjectSettings", anchor_attrs)

        # Add Properties element (required for valid IDML)
        props = ET.SubElement(rectangle, "Properties")

        # PathGeometry defines rectangle shape
        path_geom = ET.SubElement(props, "PathGeometry")
        geom_path_type = ET.SubElement(path_geom, "GeometryPathType")
        geom_path_type.set("PathOpen", "false")

        # PathPointArray with 4 corners
        path_point_array = ET.SubElement(geom_path_type, "PathPointArray")

        # Define 4 corners of rectangle
        corners = [
            (0, 0),  # Top-left
            (width, 0),  # Top-right
            (width, height),  # Bottom-right
            (0, height),  # Bottom-left
        ]

        for i, (x, y) in enumerate(corners):
            point = ET.SubElement(path_point_array, "PathPointType")
            point.set("Anchor", f"{x} {y}")
            point.set("LeftDirection", f"{x} {y}")
            point.set("RightDirection", f"{x} {y}")

        return rectangle

    def _create_image_element(
        self, graphic_path: str, width: float, height: float
    ) -> ET.Element:
        """
        Create Image XML element.

        Args:
            graphic_path: Path to graphic file
            width: Image width in points
            height: Image height in points

        Returns:
            Image Element
        """
        # Image element attributes
        image_attrs = {
            "Self": f"u{uuid.uuid4().hex[:8]}",
            "ItemTransform": f"1 0 0 1 0 0",
        }

        image = ET.Element("Image", image_attrs)

        # Link to graphic file
        link = ET.SubElement(image, "Link")
        link.set("Self", f"u{uuid.uuid4().hex[:8]}")
        link.set("AssetURL", f"file:///{graphic_path}")
        link.set("AssetID", "")
        link.set("LinkResourceURI", graphic_path)

        # Properties
        props = ET.SubElement(image, "Properties")

        # Profile (color management)
        profile = ET.SubElement(props, "Profile")
        profile.text = "Use Embedded Profile"

        # GraphicBounds
        bounds = ET.SubElement(props, "GraphicBounds")
        bounds.set("Left", "0")
        bounds.set("Top", "0")
        bounds.set("Right", str(width))
        bounds.set("Bottom", str(height))

        return image

    def _insert_into_story(
        self, story: IDMLStory, element: ET.Element, insertion_point: int
    ) -> None:
        """
        Insert element into story at specified insertion point.

        Strategy:
            1. Find ParagraphStyleRange at or after insertion_point
            2. Create CharacterStyleRange wrapper
            3. Insert element into CharacterStyleRange

        Args:
            story: Story to insert into
            element: Element to insert (e.g., Rectangle)
            insertion_point: Character position (0 = start)
        """
        # Find first ParagraphStyleRange
        paragraphs = story.root.findall(".//ParagraphStyleRange")

        if not paragraphs:
            # No paragraphs - create one
            paragraph = ET.SubElement(story.root, "ParagraphStyleRange")
            paragraph.set("AppliedParagraphStyle", "ParagraphStyle/$ID/NormalParagraphStyle")
        else:
            # Use first paragraph for simplicity
            # In production, calculate correct paragraph based on insertion_point
            paragraph = paragraphs[0]

        # Create CharacterStyleRange wrapper
        char_range = ET.SubElement(paragraph, "CharacterStyleRange")
        char_range.set("AppliedCharacterStyle", "CharacterStyle/$ID/[No character style]")

        # Insert element
        char_range.append(element)

    def update_object_position(
        self,
        doc: IDMLDocument,
        object_ref: str,
        x: float,
        y: float,
        width: Optional[float] = None,
        height: Optional[float] = None,
    ) -> bool:
        """
        Update position and optionally size of IDML object.

        Args:
            doc: Parsed IDML document
            object_ref: Self attribute of object
            x: New X position (in points)
            y: New Y position (in points)
            width: Optional new width
            height: Optional new height

        Returns:
            True if object found and modified, False otherwise
        """
        # Search spreads for object
        for spread in doc.spreads.values():
            element = find_element_by_self(spread.root, object_ref)
            if element is not None:
                self._update_transform(element, x, y, width, height)
                return True

        return False

    def _update_transform(
        self,
        element: ET.Element,
        x: float,
        y: float,
        width: Optional[float],
        height: Optional[float],
    ) -> None:
        """
        Update ItemTransform attribute.

        ItemTransform format: "a b c d tx ty"
        Where [a b c d] is 2x2 transform matrix, [tx ty] is translation.

        For simple positioning: "1 0 0 1 x y"
        """
        # Get current transform or use identity
        current = element.get("ItemTransform", "1 0 0 1 0 0")
        parts = current.split()

        if len(parts) >= 6:
            # Update translation (last 2 values)
            parts[4] = str(x)
            parts[5] = str(y)

            # Update scale if width/height provided
            # Note: This is simplified; production code should handle rotation
            if width is not None or height is not None:
                # Scale factors in transform matrix
                # a = x-scale, d = y-scale
                if width is not None:
                    parts[0] = str(width / 100.0)  # Normalize to scale
                if height is not None:
                    parts[3] = str(height / 100.0)

            element.set("ItemTransform", " ".join(parts))

    def save_changes(self, doc: IDMLDocument) -> None:
        """
        Save all modifications back to XML files.

        Writes modified XML trees back to their source files in temp directory.

        Args:
            doc: Modified IDML document

        Example:
            >>> modifier.add_object_label(doc, "u1a3", "img-abc")
            >>> modifier.save_changes(doc)
            >>> # Now zip_idml() to create modified IDML file
        """
        # Save designmap
        write_xml_file(doc.designmap_tree, doc.temp_dir / "designmap.xml", pretty=False)

        # Save all stories
        for story in doc.stories.values():
            write_xml_file(story.xml_tree, story.file_path, pretty=False)

        # Save all spreads
        for spread in doc.spreads.values():
            write_xml_file(spread.xml_tree, spread.file_path, pretty=False)

        # Save backing story if exists
        if doc.backing_story:
            backing_path = doc.temp_dir / "XML" / "BackingStory.xml"
            write_xml_file(doc.backing_story, backing_path, pretty=False)

        # Save styles if exists
        if doc.styles_tree:
            styles_path = doc.temp_dir / "Resources" / "Styles.xml"
            write_xml_file(doc.styles_tree, styles_path, pretty=False)


def add_metadata_to_backing_story(
    doc: IDMLDocument, metadata: Dict[str, Any]
) -> None:
    """
    Add KPS metadata to BackingStory.xml.

    BackingStory contains document-level metadata.

    Args:
        doc: IDML document
        metadata: Metadata dictionary to add

    Example:
        >>> add_metadata_to_backing_story(doc, {
        ...     "kps_version": "2.0.0",
        ...     "asset_count": 15,
        ...     "processed_date": "2025-01-06"
        ... })
    """
    if not doc.backing_story:
        # Create BackingStory if doesn't exist
        root = ET.Element("BackingStory")
        doc.backing_story = ET.ElementTree(root)

    root = doc.backing_story.getroot()

    # Add or update Properties section
    props = root.find("Properties")
    if props is None:
        props = ET.SubElement(root, "Properties")

    # Add each metadata item as Property element
    for key, value in metadata.items():
        # Check if property already exists
        existing = None
        for prop in props.findall("Property"):
            if prop.get("name") == key:
                existing = prop
                break

        if existing is not None:
            existing.text = str(value)
        else:
            prop = ET.SubElement(props, "Property")
            prop.set("name", key)
            prop.text = str(value)
