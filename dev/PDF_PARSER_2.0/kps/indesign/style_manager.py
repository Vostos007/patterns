"""
InDesign Style Manager for KPS v2.0.

This module manages InDesign paragraph and character styles, applying them
to document content based on content type and configuration.

Features:
- Load style definitions from YAML
- Apply styles to IDML content
- Create style XML for IDML export
- Map content types to styles
- Handle language-specific formatting
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import yaml


@dataclass
class ParagraphStyleDefinition:
    """Definition of a paragraph style."""

    name: str
    based_on: str = "[No Paragraph Style]"
    font_family: str = "Source Serif 4"
    font_style: str = "Regular"
    size: float = 11.0
    leading: float = 14.0
    tracking: float = 0.0
    color: str = "Black"
    alignment: str = "LeftAlign"
    first_line_indent: float = 0.0
    left_indent: float = 0.0
    right_indent: float = 0.0
    space_before: float = 0.0
    space_after: float = 0.0
    keep_with_next: bool = False
    hyphenation: bool = True
    composer: str = "Adobe Paragraph Composer"
    case: str = "Normal"

    # Bullets/numbering
    bullet_character: Optional[str] = None
    numbering_format: Optional[str] = None
    numbering_style: Optional[str] = None

    # Background
    background_color: Optional[str] = None


@dataclass
class CharacterStyleDefinition:
    """Definition of a character style."""

    name: str
    based_on: str = "[None]"
    font_family: Optional[str] = None
    font_style: Optional[str] = None
    size: Optional[str] = None  # Can be "90%" or absolute number
    color: Optional[str] = None
    tracking: Optional[float] = None
    underline: bool = False
    strikethrough: bool = False
    no_break: bool = False
    case: Optional[str] = None


@dataclass
class ObjectStyleDefinition:
    """Definition of an object style (for images, frames)."""

    name: str
    anchored_position: str = "Anchored"
    anchor_point: str = "TopLeftAnchor"
    horizontal_alignment: str = "CenterAlign"
    horizontal_reference: str = "ColumnEdge"
    vertical_reference: str = "LineBaseline"
    anchor_x_offset: float = 0.0
    anchor_y_offset: float = 0.0
    space_before: str = "None"
    space_after: str = "None"
    max_width: Optional[str] = None
    text_wrap: str = "None"
    text_wrap_offset: float = 0.0
    stroke_weight: float = 0.0
    stroke_color: Optional[str] = None
    fill_color: Optional[str] = None


class StyleManager:
    """
    Manages InDesign styles for KPS documents.

    This class loads style definitions from YAML configuration and provides
    methods to apply styles to IDML content.

    Example:
        >>> manager = StyleManager.from_yaml("master-template-styles.yaml")
        >>>
        >>> # Get style for heading
        >>> heading_style = manager.get_paragraph_style("Heading1")
        >>>
        >>> # Apply style to content
        >>> style_ref = manager.get_style_for_content("section_title")
        >>> print(style_ref)  # "ParagraphStyle/Heading1"
        >>>
        >>> # Generate IDML Styles.xml
        >>> styles_xml = manager.generate_styles_xml()
    """

    def __init__(self):
        """Initialize style manager with empty style collections."""
        self.paragraph_styles: Dict[str, ParagraphStyleDefinition] = {}
        self.character_styles: Dict[str, CharacterStyleDefinition] = {}
        self.object_styles: Dict[str, ObjectStyleDefinition] = {}
        self.content_mapping: Dict[str, str] = {}
        self.colors: Dict[str, Dict] = {}
        self.document_settings: Dict = {}
        self.language_settings: Dict[str, Dict] = {}

    @classmethod
    def from_yaml(cls, yaml_path: Path) -> StyleManager:
        """
        Load style definitions from YAML file.

        Args:
            yaml_path: Path to YAML style definition file

        Returns:
            Configured StyleManager instance

        Raises:
            FileNotFoundError: If YAML file doesn't exist
            yaml.YAMLError: If YAML is invalid
        """
        manager = cls()

        with open(yaml_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        # Load paragraph styles
        for name, props in config.get("paragraph_styles", {}).items():
            style = ParagraphStyleDefinition(name=name, **props)
            manager.paragraph_styles[name] = style

        # Load character styles
        for name, props in config.get("character_styles", {}).items():
            style = CharacterStyleDefinition(name=name, **props)
            manager.character_styles[name] = style

        # Load object styles
        for name, props in config.get("object_styles", {}).items():
            style = ObjectStyleDefinition(name=name, **props)
            manager.object_styles[name] = style

        # Load content mapping
        manager.content_mapping = config.get("content_mapping", {})

        # Load colors
        manager.colors = config.get("colors", {})

        # Load document settings
        manager.document_settings = config.get("document", {})

        # Load language settings
        manager.language_settings = config.get("language_settings", {})

        return manager

    def get_paragraph_style(self, style_name: str) -> Optional[ParagraphStyleDefinition]:
        """
        Get paragraph style definition by name.

        Args:
            style_name: Name of style (e.g., "Heading1")

        Returns:
            ParagraphStyleDefinition or None if not found
        """
        return self.paragraph_styles.get(style_name)

    def get_character_style(self, style_name: str) -> Optional[CharacterStyleDefinition]:
        """
        Get character style definition by name.

        Args:
            style_name: Name of style (e.g., "Emphasis")

        Returns:
            CharacterStyleDefinition or None if not found
        """
        return self.character_styles.get(style_name)

    def get_object_style(self, style_name: str) -> Optional[ObjectStyleDefinition]:
        """
        Get object style definition by name.

        Args:
            style_name: Name of style (e.g., "FigureInline")

        Returns:
            ObjectStyleDefinition or None if not found
        """
        return self.object_styles.get(style_name)

    def get_style_for_content(
        self, content_type: str, style_type: str = "paragraph"
    ) -> Optional[str]:
        """
        Get InDesign style reference for content type.

        Args:
            content_type: Content type (e.g., "section_title", "emphasis")
            style_type: "paragraph" or "character"

        Returns:
            InDesign style reference string (e.g., "ParagraphStyle/Heading1")
            or None if not found

        Example:
            >>> manager.get_style_for_content("section_title")
            "ParagraphStyle/Heading1"
            >>> manager.get_style_for_content("emphasis", "character")
            "CharacterStyle/Emphasis"
        """
        style_name = self.content_mapping.get(content_type)
        if not style_name:
            return None

        # Check if it's a paragraph or character style
        if style_name in self.paragraph_styles:
            return f"ParagraphStyle/{style_name}"
        elif style_name in self.character_styles:
            return f"CharacterStyle/{style_name}"
        else:
            return None

    def get_language_settings(self, language_code: str) -> Dict:
        """
        Get language-specific settings.

        Args:
            language_code: Language code (e.g., "ru", "en", "fr")

        Returns:
            Dictionary with language settings (hyphenation, composer, quotes)
        """
        return self.language_settings.get(language_code, {})

    def generate_styles_xml(self) -> ET.Element:
        """
        Generate IDML Styles.xml content.

        Creates XML structure with all defined paragraph and character styles
        that can be inserted into IDML Resources/Styles.xml.

        Returns:
            ElementTree Element representing Styles.xml root

        Example:
            >>> manager = StyleManager.from_yaml("styles.yaml")
            >>> styles_root = manager.generate_styles_xml()
            >>> tree = ET.ElementTree(styles_root)
            >>> tree.write("Styles.xml", encoding="utf-8", xml_declaration=True)
        """
        root = ET.Element("idPkg:Styles")
        root.set("xmlns:idPkg", "http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging")
        root.set("DOMVersion", "19.0")

        # Add RootParagraphStyleGroup
        para_group = ET.SubElement(root, "RootParagraphStyleGroup")
        para_group.set("Self", "pandsg")

        # Add paragraph styles
        for style_name, style_def in self.paragraph_styles.items():
            style_elem = self._create_paragraph_style_element(style_def)
            para_group.append(style_elem)

        # Add RootCharacterStyleGroup
        char_group = ET.SubElement(root, "RootCharacterStyleGroup")
        char_group.set("Self", "nandcsg")

        # Add character styles
        for style_name, style_def in self.character_styles.items():
            style_elem = self._create_character_style_element(style_def)
            char_group.append(style_elem)

        # Add color swatches
        if self.colors:
            for color_name, color_def in self.colors.items():
                swatch = self._create_color_swatch(color_name, color_def)
                root.append(swatch)

        return root

    def _create_paragraph_style_element(
        self, style: ParagraphStyleDefinition
    ) -> ET.Element:
        """Create IDML XML element for paragraph style."""
        elem = ET.Element("ParagraphStyle")
        elem.set("Self", f"ParagraphStyle/{style.name}")
        elem.set("Name", style.name)

        # Based on
        if style.based_on != "[No Paragraph Style]":
            elem.set("BasedOn", f"ParagraphStyle/{style.based_on}")

        # Font properties
        props = ET.SubElement(elem, "Properties")

        font_elem = ET.SubElement(props, "AppliedFont")
        font_elem.set("type", "string")
        font_elem.text = style.font_family

        # Point size
        size_elem = ET.SubElement(props, "PointSize")
        size_elem.set("type", "unit")
        size_elem.text = str(style.size)

        # Leading
        leading_elem = ET.SubElement(props, "Leading")
        leading_elem.set("type", "unit")
        leading_elem.text = str(style.leading)

        # Tracking
        if style.tracking != 0:
            tracking_elem = ET.SubElement(props, "Tracking")
            tracking_elem.set("type", "unit")
            tracking_elem.text = str(style.tracking)

        # Alignment
        align_elem = ET.SubElement(props, "Justification")
        align_elem.set("type", "enumeration")
        align_elem.text = style.alignment

        # Space before/after
        if style.space_before > 0:
            sb_elem = ET.SubElement(props, "SpaceBefore")
            sb_elem.set("type", "unit")
            sb_elem.text = str(style.space_before)

        if style.space_after > 0:
            sa_elem = ET.SubElement(props, "SpaceAfter")
            sa_elem.set("type", "unit")
            sa_elem.text = str(style.space_after)

        # Indents
        if style.first_line_indent != 0:
            fli_elem = ET.SubElement(props, "FirstLineIndent")
            fli_elem.set("type", "unit")
            fli_elem.text = str(style.first_line_indent)

        if style.left_indent != 0:
            li_elem = ET.SubElement(props, "LeftIndent")
            li_elem.set("type", "unit")
            li_elem.text = str(style.left_indent)

        # Hyphenation
        hyph_elem = ET.SubElement(props, "Hyphenation")
        hyph_elem.set("type", "boolean")
        hyph_elem.text = "true" if style.hyphenation else "false"

        return elem

    def _create_character_style_element(
        self, style: CharacterStyleDefinition
    ) -> ET.Element:
        """Create IDML XML element for character style."""
        elem = ET.Element("CharacterStyle")
        elem.set("Self", f"CharacterStyle/{style.name}")
        elem.set("Name", style.name)

        props = ET.SubElement(elem, "Properties")

        # Font family
        if style.font_family:
            font_elem = ET.SubElement(props, "AppliedFont")
            font_elem.set("type", "string")
            font_elem.text = style.font_family

        # Font style
        if style.font_style:
            fs_elem = ET.SubElement(props, "FontStyle")
            fs_elem.set("type", "string")
            fs_elem.text = style.font_style

        # Size
        if style.size:
            size_elem = ET.SubElement(props, "PointSize")
            size_elem.set("type", "unit")
            size_elem.text = str(style.size)

        # Color
        if style.color:
            color_elem = ET.SubElement(props, "FillColor")
            color_elem.set("type", "string")
            color_elem.text = f"Color/{style.color}"

        # Underline
        if style.underline:
            ul_elem = ET.SubElement(props, "Underline")
            ul_elem.set("type", "boolean")
            ul_elem.text = "true"

        return elem

    def _create_color_swatch(self, name: str, definition: Dict) -> ET.Element:
        """Create IDML XML element for color swatch."""
        elem = ET.Element("Color")
        elem.set("Self", f"Color/{name}")
        elem.set("Name", name)
        elem.set("Model", definition.get("model", "CMYK"))
        elem.set("Space", definition.get("type", "Process"))

        # Color values
        if definition["model"] == "CMYK":
            values = definition["values"]
            elem.set("ColorValue", f"{values[0]} {values[1]} {values[2]} {values[3]}")

        return elem

    def apply_style_to_block(
        self, block_type: str, language: str = "en"
    ) -> Dict[str, str]:
        """
        Get style attributes to apply to a content block.

        Args:
            block_type: Type of block (e.g., "section_title", "paragraph")
            language: Language code for language-specific settings

        Returns:
            Dictionary with style attributes

        Example:
            >>> manager.apply_style_to_block("section_title", "ru")
            {
                "AppliedParagraphStyle": "ParagraphStyle/Heading1",
                "HyphenationDictionary": "Russian",
                "Composer": "Adobe World-Ready Paragraph Composer"
            }
        """
        attrs = {}

        # Get style reference
        style_ref = self.get_style_for_content(block_type)
        if style_ref:
            attrs["AppliedParagraphStyle"] = style_ref

        # Add language-specific settings
        lang_settings = self.get_language_settings(language)
        if lang_settings:
            if "hyphenation_dictionary" in lang_settings:
                attrs["HyphenationDictionary"] = lang_settings["hyphenation_dictionary"]
            if "composer" in lang_settings:
                attrs["Composer"] = lang_settings["composer"]

        return attrs


__all__ = [
    "StyleManager",
    "ParagraphStyleDefinition",
    "CharacterStyleDefinition",
    "ObjectStyleDefinition",
]
