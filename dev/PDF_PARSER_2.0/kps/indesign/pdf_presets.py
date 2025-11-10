"""
PDF Export Preset Management System

Manages InDesign PDF export presets including built-in presets, custom presets,
YAML configuration loading, and InDesign .pdfpreset file generation.

Author: KPS v2.0 Agent 4
Date: 2025-11-06
"""

from pathlib import Path
from typing import Dict, List, Optional, Any
import yaml
import json
import logging
from datetime import datetime

from .pdf_export import (
    PDFExportSettings,
    PDFStandard,
    ColorSpace,
    CompressionType,
    ImageQuality,
    get_print_high_quality_preset,
    get_print_medium_quality_preset,
    get_screen_optimized_preset,
    get_proof_preset
)

logger = logging.getLogger(__name__)


class PDFPresetManager:
    """
    Manage InDesign PDF export presets.

    Provides access to built-in presets, loading from YAML configuration,
    and generation of InDesign .pdfpreset files.

    Example:
        >>> manager = PDFPresetManager()
        >>> preset = manager.get_preset("print_high_quality")
        >>> manager.create_preset_file(preset, Path("my_preset.pdfpreset"))
        >>>
        >>> # Load custom presets from YAML
        >>> manager.load_presets_from_yaml(Path("config/pdf_export_presets.yaml"))
        >>> custom = manager.get_preset("magazine_print")
    """

    # Built-in preset definitions
    BUILTIN_PRESETS: Dict[str, PDFExportSettings] = {
        "print_high_quality": get_print_high_quality_preset(),
        "print_medium_quality": get_print_medium_quality_preset(),
        "screen_optimized": get_screen_optimized_preset(),
        "proof": get_proof_preset(),
    }

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize preset manager.

        Args:
            config_dir: Directory to search for preset YAML files
        """
        self.config_dir = config_dir
        self._custom_presets: Dict[str, PDFExportSettings] = {}
        self._preset_metadata: Dict[str, Dict[str, Any]] = {}

        # Auto-load presets if config directory provided
        if config_dir and config_dir.exists():
            self._auto_load_presets()

    def get_preset(self, name: str) -> PDFExportSettings:
        """
        Get preset by name.

        Searches custom presets first, then built-in presets.

        Args:
            name: Preset name (e.g., "print_high_quality")

        Returns:
            PDFExportSettings instance

        Raises:
            KeyError: If preset not found
        """
        # Check custom presets first
        if name in self._custom_presets:
            logger.debug(f"Loading custom preset: {name}")
            return self._custom_presets[name]

        # Check built-in presets
        if name in self.BUILTIN_PRESETS:
            logger.debug(f"Loading built-in preset: {name}")
            return self.BUILTIN_PRESETS[name]

        # Not found
        available = list(self.list_presets().keys())
        raise KeyError(
            f"Preset '{name}' not found. Available presets: {', '.join(available)}"
        )

    def list_presets(self) -> Dict[str, str]:
        """
        List all available presets with descriptions.

        Returns:
            Dictionary mapping preset names to descriptions
        """
        presets = {}

        # Built-in presets
        for name in self.BUILTIN_PRESETS.keys():
            metadata = self._get_builtin_metadata(name)
            presets[name] = metadata.get("description", "Built-in preset")

        # Custom presets
        for name in self._custom_presets.keys():
            metadata = self._preset_metadata.get(name, {})
            presets[name] = metadata.get("description", "Custom preset")

        return presets

    def add_preset(
        self,
        name: str,
        settings: PDFExportSettings,
        description: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Add or update a custom preset.

        Args:
            name: Preset name (will override existing)
            settings: Export settings
            description: Human-readable description
            metadata: Additional metadata (author, version, etc.)
        """
        self._custom_presets[name] = settings

        # Store metadata
        meta = metadata or {}
        meta.update({
            "name": name,
            "description": description,
            "created_at": datetime.now().isoformat(),
            "type": "custom"
        })
        self._preset_metadata[name] = meta

        logger.info(f"Added custom preset: {name}")

    def remove_preset(self, name: str):
        """Remove a custom preset (cannot remove built-in presets)"""
        if name in self.BUILTIN_PRESETS:
            raise ValueError(f"Cannot remove built-in preset: {name}")

        if name in self._custom_presets:
            del self._custom_presets[name]
            self._preset_metadata.pop(name, None)
            logger.info(f"Removed custom preset: {name}")
        else:
            raise KeyError(f"Custom preset not found: {name}")

    def load_presets_from_yaml(self, yaml_path: Path) -> int:
        """
        Load presets from YAML configuration file.

        Args:
            yaml_path: Path to YAML file with preset definitions

        Returns:
            Number of presets loaded

        Example YAML format:
            presets:
              magazine_print:
                description: "High-quality magazine printing"
                settings:
                  pdf_standard: "PDF/X-4:2010"
                  color_space: "CMYK"
                  jpeg_quality: 12
                  include_bleed: true
        """
        if not yaml_path.exists():
            raise FileNotFoundError(f"YAML file not found: {yaml_path}")

        logger.info(f"Loading presets from: {yaml_path}")

        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        if not data or 'presets' not in data:
            logger.warning(f"No presets found in {yaml_path}")
            return 0

        count = 0
        for name, config in data['presets'].items():
            try:
                settings_data = config.get('settings', {})
                settings = PDFExportSettings.from_dict(settings_data)

                description = config.get('description', '')
                metadata = {
                    'source_file': str(yaml_path),
                    'author': config.get('author', 'unknown'),
                    'version': config.get('version', '1.0')
                }

                self.add_preset(name, settings, description, metadata)
                count += 1

            except Exception as e:
                logger.error(f"Failed to load preset '{name}': {e}")
                continue

        logger.info(f"Loaded {count} presets from {yaml_path}")
        return count

    def save_presets_to_yaml(self, yaml_path: Path, include_builtin: bool = False):
        """
        Save custom presets to YAML file.

        Args:
            yaml_path: Output YAML file path
            include_builtin: Whether to include built-in presets
        """
        presets_data = {}

        # Custom presets
        for name, settings in self._custom_presets.items():
            metadata = self._preset_metadata.get(name, {})
            presets_data[name] = {
                'description': metadata.get('description', ''),
                'author': metadata.get('author', 'unknown'),
                'settings': settings.to_dict()
            }

        # Optionally include built-in
        if include_builtin:
            for name, settings in self.BUILTIN_PRESETS.items():
                metadata = self._get_builtin_metadata(name)
                presets_data[name] = {
                    'description': metadata.get('description', ''),
                    'author': 'KPS v2.0',
                    'settings': settings.to_dict()
                }

        # Write YAML
        output_data = {
            'version': '1.0',
            'generated_at': datetime.now().isoformat(),
            'presets': presets_data
        }

        yaml_path.parent.mkdir(parents=True, exist_ok=True)
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(output_data, f, sort_keys=False, indent=2)

        logger.info(f"Saved {len(presets_data)} presets to {yaml_path}")

    def create_preset_file(
        self,
        settings: PDFExportSettings,
        output_path: Path,
        preset_name: Optional[str] = None
    ):
        """
        Create InDesign .pdfpreset file.

        InDesign preset files are XML-based with specific structure.
        This generates a compatible file that can be imported into InDesign.

        Args:
            settings: Export settings to save
            output_path: Output .pdfpreset file path
            preset_name: Optional preset name (defaults to filename)
        """
        if not preset_name:
            preset_name = output_path.stem

        # Generate InDesign-compatible XML preset
        preset_xml = self._generate_indesign_preset_xml(settings, preset_name)

        # Write to file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(preset_xml)

        logger.info(f"Created InDesign preset file: {output_path}")

    def export_preset_as_json(self, name: str, output_path: Path):
        """Export preset as JSON for debugging/interchange"""
        settings = self.get_preset(name)
        metadata = self._preset_metadata.get(name, self._get_builtin_metadata(name))

        export_data = {
            'name': name,
            'metadata': metadata,
            'settings': settings.to_dict(),
            'exported_at': datetime.now().isoformat()
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2)

        logger.info(f"Exported preset '{name}' to {output_path}")

    def _auto_load_presets(self):
        """Auto-load presets from config directory"""
        if not self.config_dir:
            return

        yaml_files = list(self.config_dir.glob("*.yaml")) + list(self.config_dir.glob("*.yml"))

        for yaml_file in yaml_files:
            if 'preset' in yaml_file.name.lower():
                try:
                    self.load_presets_from_yaml(yaml_file)
                except Exception as e:
                    logger.warning(f"Failed to load {yaml_file}: {e}")

    def _get_builtin_metadata(self, name: str) -> Dict[str, Any]:
        """Get metadata for built-in presets"""
        descriptions = {
            "print_high_quality": "Maximum quality print production (PDF/X-4, CMYK, no downsampling)",
            "print_medium_quality": "Standard print quality (PDF/X-4, CMYK, 300 DPI)",
            "screen_optimized": "Screen viewing optimized (RGB, 150 DPI, smaller file size)",
            "proof": "Quick proofing (medium quality, fast generation)"
        }

        return {
            "description": descriptions.get(name, "Built-in preset"),
            "author": "KPS v2.0",
            "type": "builtin",
            "version": "1.0"
        }

    def _generate_indesign_preset_xml(
        self,
        settings: PDFExportSettings,
        preset_name: str
    ) -> str:
        """
        Generate InDesign-compatible preset XML.

        InDesign preset files use a specific XML schema. This generates
        a simplified but compatible version.

        Note: This is a simplified implementation. Full InDesign preset
        files have complex nested structures. For production use,
        consider using InDesign's scripting to export actual presets.
        """
        xml_lines = [
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            '<PDFExportPreset>',
            f'  <PresetName>{preset_name}</PresetName>',
            f'  <Standard>{settings.pdf_standard.value}</Standard>',
            f'  <ColorSpace>{settings.color_space.value}</ColorSpace>',
            f'  <OutputIntent>{settings.output_intent}</OutputIntent>',
            '  <ImageSettings>',
            f'    <Compression>{settings.compression.value}</Compression>',
            f'    <Quality>{settings.image_quality.value}</Quality>',
            f'    <JPEGQuality>{settings.jpeg_quality}</JPEGQuality>',
            f'    <DownsampleImages>{str(settings.downsample_images).lower()}</DownsampleImages>',
            f'    <ColorResolution>{settings.downsample_color_to}</ColorResolution>',
            '  </ImageSettings>',
            '  <MarksAndBleeds>',
            f'    <IncludeBleed>{str(settings.include_bleed).lower()}</IncludeBleed>',
            f'    <BleedTop>{settings.bleed_top}</BleedTop>',
            f'    <BleedBottom>{settings.bleed_bottom}</BleedBottom>',
            f'    <BleedLeft>{settings.bleed_left}</BleedLeft>',
            f'    <BleedRight>{settings.bleed_right}</BleedRight>',
            f'    <CropMarks>{str(settings.crop_marks).lower()}</CropMarks>',
            f'    <RegistrationMarks>{str(settings.registration_marks).lower()}</RegistrationMarks>',
            '  </MarksAndBleeds>',
            '  <Advanced>',
            f'    <SubsetFonts>{settings.subset_fonts_threshold}</SubsetFonts>',
            f'    <OptimizePDF>{str(settings.optimize_pdf).lower()}</OptimizePDF>',
            f'    <CreateTaggedPDF>{str(settings.create_tagged_pdf).lower()}</CreateTaggedPDF>',
            '  </Advanced>',
            '</PDFExportPreset>'
        ]

        return '\n'.join(xml_lines)


class PresetValidator:
    """Validate preset definitions and settings"""

    @staticmethod
    def validate_preset_file(preset_path: Path) -> List[str]:
        """
        Validate a preset file (YAML or XML).

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        if not preset_path.exists():
            errors.append(f"File not found: {preset_path}")
            return errors

        if preset_path.suffix in ['.yaml', '.yml']:
            errors.extend(PresetValidator._validate_yaml(preset_path))
        elif preset_path.suffix == '.pdfpreset':
            errors.extend(PresetValidator._validate_xml(preset_path))
        else:
            errors.append(f"Unknown preset file type: {preset_path.suffix}")

        return errors

    @staticmethod
    def _validate_yaml(yaml_path: Path) -> List[str]:
        """Validate YAML preset file"""
        errors = []

        try:
            with open(yaml_path, 'r') as f:
                data = yaml.safe_load(f)

            if not isinstance(data, dict):
                errors.append("YAML root must be a dictionary")
                return errors

            if 'presets' not in data:
                errors.append("Missing 'presets' key in YAML")
                return errors

            # Validate each preset
            for name, config in data['presets'].items():
                if not isinstance(config, dict):
                    errors.append(f"Preset '{name}' must be a dictionary")
                    continue

                if 'settings' not in config:
                    errors.append(f"Preset '{name}' missing 'settings' section")
                    continue

                # Try to parse settings
                try:
                    settings = PDFExportSettings.from_dict(config['settings'])
                    validation_errors = settings.validate()
                    if validation_errors:
                        errors.extend([f"{name}: {e}" for e in validation_errors])
                except Exception as e:
                    errors.append(f"Preset '{name}' settings invalid: {e}")

        except yaml.YAMLError as e:
            errors.append(f"YAML parsing error: {e}")
        except Exception as e:
            errors.append(f"Validation error: {e}")

        return errors

    @staticmethod
    def _validate_xml(xml_path: Path) -> List[str]:
        """Validate XML preset file (basic check)"""
        errors = []

        try:
            with open(xml_path, 'r') as f:
                content = f.read()

            # Basic XML structure check
            if '<?xml' not in content:
                errors.append("Missing XML declaration")

            if '<PDFExportPreset>' not in content:
                errors.append("Missing PDFExportPreset root element")

            # Could use xml.etree.ElementTree for deeper validation
            # but keeping it simple for now

        except Exception as e:
            errors.append(f"XML validation error: {e}")

        return errors


if __name__ == "__main__":
    # Demo usage
    print("PDF Preset Manager Demo")
    print("=" * 50)

    # Create manager
    manager = PDFPresetManager()

    # List built-in presets
    print("\nAvailable Presets:")
    for name, description in manager.list_presets().items():
        print(f"  {name}: {description}")

    # Get a preset
    print("\nLoading 'print_high_quality' preset:")
    preset = manager.get_preset("print_high_quality")
    print(f"  Standard: {preset.pdf_standard.value}")
    print(f"  Color: {preset.color_space.value}")
    print(f"  Quality: {preset.jpeg_quality}/12")

    # Create custom preset
    print("\nCreating custom preset:")
    custom = PDFExportSettings(
        pdf_standard=PDFStandard.PDF_X_4_2010,
        color_space=ColorSpace.CMYK,
        jpeg_quality=11,
        include_bleed=True
    )
    manager.add_preset("my_custom", custom, "My custom preset")
    print(f"  Added 'my_custom' preset")

    # Save to YAML
    yaml_path = Path("demo_presets.yaml")
    manager.save_presets_to_yaml(yaml_path, include_builtin=True)
    print(f"\n✓ Saved presets to {yaml_path}")

    # Create .pdfpreset file
    preset_file = Path("demo_preset.pdfpreset")
    manager.create_preset_file(preset, preset_file, "Demo Preset")
    print(f"✓ Created InDesign preset file: {preset_file}")
