"""IDML export workflow.

High-level export system that coordinates IDML parsing, modification,
and re-packaging with anchored objects from KPS asset ledger.

This is the main entry point for IDML export operations.

Workflow:
    1. Parse source IDML
    2. Load asset ledger and document structure
    3. For each asset with anchor_to:
        a. Find target block in document
        b. Calculate anchor settings from column/bbox
        c. Create anchored object in IDML
        d. Add asset label and metadata
    4. Save modifications
    5. Re-package as IDML
    6. Validate output

Usage:
    >>> exporter = IDMLExporter()
    >>> exporter.export_with_anchored_objects(
    ...     source_idml=Path("template.idml"),
    ...     output_idml=Path("output.idml"),
    ...     manifest=asset_ledger,
    ...     document=kps_document,
    ...     columns=page_columns
    ... )
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import logging

from ..core.assets import AssetLedger, Asset
from ..core.document import KPSDocument, ContentBlock
from ..anchoring.columns import Column, find_asset_column
from .idml_parser import IDMLParser, IDMLDocument, find_text_frames_for_story
from .idml_modifier import IDMLModifier, add_metadata_to_backing_story
from .idml_utils import zip_idml, cleanup_temp_dir
from .anchoring import calculate_anchor_settings

logger = logging.getLogger(__name__)


class IDMLExporter:
    """
    High-level IDML export system.

    Coordinates parsing, modification, and packaging of IDML with anchored objects.

    Usage:
        >>> exporter = IDMLExporter()
        >>> success = exporter.export_with_anchored_objects(
        ...     source_idml=Path("template.idml"),
        ...     output_idml=Path("output.idml"),
        ...     manifest=ledger,
        ...     document=doc,
        ...     columns=cols
        ... )
        >>> if success:
        ...     print("Export complete!")
    """

    def __init__(self):
        """Initialize IDML exporter."""
        self.parser = IDMLParser()
        self.modifier = IDMLModifier()

    def export_with_anchored_objects(
        self,
        source_idml: Path,
        output_idml: Path,
        manifest: AssetLedger,
        document: KPSDocument,
        columns: Dict[int, List[Column]],
        cleanup: bool = True,
    ) -> bool:
        """
        Complete export workflow with anchored objects.

        Takes source IDML template and embeds KPS assets as anchored objects
        based on manifest and document structure.

        Args:
            source_idml: Path to source IDML template
            output_idml: Path for output IDML file
            manifest: Asset ledger with anchoring information
            document: KPS document structure
            columns: Dictionary of page_number -> List[Column]
            cleanup: If True, cleanup temp directories (default: True)

        Returns:
            True if export successful, False otherwise

        Example:
            >>> from ..core.assets import AssetLedger
            >>> from ..core.document import KPSDocument
            >>> from ..anchoring.columns import detect_columns
            >>>
            >>> ledger = AssetLedger.load_json(Path("assets.json"))
            >>> doc = KPSDocument.load_json(Path("document.json"))
            >>> columns = {0: detect_columns(doc.get_blocks_on_page(0))}
            >>>
            >>> exporter = IDMLExporter()
            >>> success = exporter.export_with_anchored_objects(
            ...     Path("template.idml"),
            ...     Path("output.idml"),
            ...     ledger,
            ...     doc,
            ...     columns
            ... )
        """
        logger.info(f"Starting IDML export: {source_idml} -> {output_idml}")

        try:
            # 1. Parse source IDML
            logger.info("Parsing source IDML...")
            idml_doc = self.parser.parse_idml(source_idml)
            logger.info(
                f"Parsed: {len(idml_doc.stories)} stories, {len(idml_doc.spreads)} spreads"
            )

            # 2. Process assets with anchoring
            logger.info(f"Processing {len(manifest.assets)} assets...")
            processed = 0
            skipped = 0

            for asset in manifest.assets:
                if not asset.anchor_to:
                    skipped += 1
                    continue

                success = self._process_asset(
                    idml_doc, asset, document, columns
                )

                if success:
                    processed += 1
                else:
                    logger.warning(
                        f"Failed to process asset {asset.asset_id} "
                        f"(anchor_to: {asset.anchor_to})"
                    )

            logger.info(
                f"Processed {processed} assets, skipped {skipped} (no anchor_to)"
            )

            # 3. Add document-level metadata
            logger.info("Adding document metadata...")
            metadata = {
                "kps_version": "2.0.0",
                "kps_source_pdf": str(manifest.source_pdf),
                "kps_asset_count": str(len(manifest.assets)),
                "kps_processed_count": str(processed),
                "kps_document_slug": document.slug,
            }
            add_metadata_to_backing_story(idml_doc, metadata)

            # 4. Save modifications
            logger.info("Saving modifications...")
            self.modifier.save_changes(idml_doc)

            # 5. Re-package as IDML
            logger.info("Packaging IDML...")
            zip_idml(idml_doc.temp_dir, output_idml)

            # 6. Cleanup
            if cleanup:
                logger.info("Cleaning up temp directory...")
                cleanup_temp_dir(idml_doc.temp_dir)

            logger.info(f"Export complete: {output_idml}")
            return True

        except Exception as e:
            logger.error(f"Export failed: {e}", exc_info=True)
            return False

    def _process_asset(
        self,
        idml_doc: IDMLDocument,
        asset: Asset,
        document: KPSDocument,
        columns: Dict[int, List[Column]],
    ) -> bool:
        """
        Process single asset: find block, calculate anchor, create anchored object.

        Args:
            idml_doc: Parsed IDML document
            asset: Asset to process
            document: KPS document structure
            columns: Page columns

        Returns:
            True if processed successfully, False otherwise
        """
        # Find target block
        block = document.find_block(asset.anchor_to)
        if not block:
            logger.warning(f"Block not found: {asset.anchor_to}")
            return False

        # Get column for asset
        page_columns = columns.get(asset.page_number)
        if not page_columns:
            logger.warning(f"No columns for page {asset.page_number}")
            return False

        column = find_asset_column(asset.bbox, page_columns)
        if not column:
            logger.warning(
                f"Asset {asset.asset_id} not in any column on page {asset.page_number}"
            )
            return False

        # Calculate anchor settings
        anchor_settings = calculate_anchor_settings(asset.bbox, column)

        # Find story ID for block
        # In production, map block.block_id to IDML story ID
        # For now, use first story as fallback
        story_id = self._find_story_for_block(idml_doc, block)
        if not story_id:
            logger.warning(f"No story found for block {block.block_id}")
            return False

        # Calculate insertion point
        # In production, find exact character position based on block content
        insertion_point = self._calculate_insertion_point(idml_doc, story_id, block)

        # Get asset dimensions
        dimensions = None
        if asset.image_width and asset.image_height:
            # Convert pixels to points (assuming 72 DPI)
            # In production, use actual DPI or scale appropriately
            dimensions = (
                asset.bbox.width,
                asset.bbox.height,
            )

        # Create anchored object
        logger.debug(
            f"Creating anchored object for {asset.asset_id} in story {story_id}"
        )
        rect_id = self.modifier.create_anchored_object(
            idml_doc,
            story_id,
            insertion_point,
            str(asset.file_path),
            anchor_settings,
            asset_id=asset.asset_id,
            dimensions=dimensions,
        )

        if not rect_id:
            return False

        # Add metadata
        metadata = self._asset_to_metadata(asset)
        self.modifier.add_object_label(idml_doc, rect_id, asset.asset_id, metadata)

        return True

    def _find_story_for_block(
        self, idml_doc: IDMLDocument, block: ContentBlock
    ) -> Optional[str]:
        """
        Find IDML story ID for content block.

        In production implementation, this would:
            1. Map block.block_id to IDML story reference
            2. Use text matching to find story
            3. Use page/position to determine story

        For now, returns first story as fallback.

        Args:
            idml_doc: IDML document
            block: Content block to find story for

        Returns:
            Story ID or None
        """
        # Strategy 1: Search for block content in stories
        matching_stories = idml_doc.find_story_by_content(block.content[:50])
        if matching_stories:
            return matching_stories[0].story_id

        # Fallback: Use first story
        if idml_doc.stories:
            first_story = list(idml_doc.stories.values())[0]
            logger.debug(
                f"Using first story {first_story.story_id} for block {block.block_id}"
            )
            return first_story.story_id

        return None

    def _calculate_insertion_point(
        self, idml_doc: IDMLDocument, story_id: str, block: ContentBlock
    ) -> int:
        """
        Calculate character insertion point in story for anchored object.

        In production, this would:
            1. Find exact position based on block.reading_order
            2. Search for marker text
            3. Calculate from block position

        For now, returns 0 (start of story).

        Args:
            idml_doc: IDML document
            story_id: Story to insert into
            block: Content block being anchored to

        Returns:
            Character position (0-indexed)
        """
        # Production implementation would be more sophisticated
        # For example, search for marker text or use block position

        # Fallback: Insert at start
        return 0

    def _asset_to_metadata(self, asset: Asset) -> Dict[str, Any]:
        """
        Convert Asset to metadata dictionary for IDML embedding.

        Args:
            asset: Asset to convert

        Returns:
            Metadata dictionary
        """
        return {
            "asset_id": asset.asset_id,
            "asset_type": asset.asset_type.value,
            "sha256": asset.sha256,
            "page_number": asset.page_number,
            "occurrence": asset.occurrence,
            "anchor_to": asset.anchor_to,
            "bbox": {
                "x0": asset.bbox.x0,
                "y0": asset.bbox.y0,
                "x1": asset.bbox.x1,
                "y1": asset.bbox.y1,
            },
            "colorspace": asset.colorspace.value if asset.colorspace else None,
            "has_smask": asset.has_smask,
            "has_clip": asset.has_clip,
            "caption_text": asset.caption_text,
        }

    def export_labels_only(
        self,
        source_idml: Path,
        output_idml: Path,
        manifest: AssetLedger,
        cleanup: bool = True,
    ) -> bool:
        """
        Export IDML with asset labels only (no anchored objects).

        Simpler workflow that adds labels to existing objects without
        creating new anchored objects.

        Args:
            source_idml: Source IDML file
            output_idml: Output IDML file
            manifest: Asset ledger
            cleanup: Cleanup temp directories

        Returns:
            True if successful

        Example:
            >>> # Add labels to existing graphics without creating new ones
            >>> success = exporter.export_labels_only(
            ...     Path("template.idml"),
            ...     Path("labeled.idml"),
            ...     ledger
            ... )
        """
        logger.info(f"Starting labels-only export: {source_idml} -> {output_idml}")

        try:
            # Parse IDML
            idml_doc = self.parser.parse_idml(source_idml)

            # Add labels to assets
            labeled = 0
            for asset in manifest.assets:
                # In production, map asset to IDML object ID
                # For now, use asset_id as object reference (assumes they match)
                metadata = self._asset_to_metadata(asset)
                success = self.modifier.add_object_label(
                    idml_doc, asset.asset_id, asset.asset_id, metadata
                )
                if success:
                    labeled += 1

            logger.info(f"Labeled {labeled}/{len(manifest.assets)} assets")

            # Save and package
            self.modifier.save_changes(idml_doc)
            zip_idml(idml_doc.temp_dir, output_idml)

            if cleanup:
                cleanup_temp_dir(idml_doc.temp_dir)

            logger.info(f"Labels-only export complete: {output_idml}")
            return True

        except Exception as e:
            logger.error(f"Labels-only export failed: {e}", exc_info=True)
            return False


def quick_export(
    source_idml: Path,
    output_idml: Path,
    assets_json: Path,
    document_json: Path,
    columns_by_page: Optional[Dict[int, List[Column]]] = None,
) -> bool:
    """
    Quick export function for command-line usage.

    Args:
        source_idml: Source IDML template
        output_idml: Output IDML file
        assets_json: Path to asset ledger JSON
        document_json: Path to KPS document JSON
        columns_by_page: Optional pre-computed columns; if None, auto-detects

    Returns:
        True if successful

    Example:
        >>> from pathlib import Path
        >>> success = quick_export(
        ...     Path("template.idml"),
        ...     Path("output.idml"),
        ...     Path("assets.json"),
        ...     Path("document.json")
        ... )
    """
    from ..core.assets import AssetLedger
    from ..core.document import KPSDocument
    from ..anchoring.columns import detect_columns

    # Load data
    manifest = AssetLedger.load_json(assets_json)
    document = KPSDocument.load_json(document_json)

    # Auto-detect columns if not provided
    if columns_by_page is None:
        logger.info("Auto-detecting columns...")
        columns_by_page = {}
        for page in range(manifest.total_pages):
            blocks = document.get_blocks_on_page(page)
            if blocks:
                try:
                    columns_by_page[page] = detect_columns(blocks)
                except ValueError:
                    logger.warning(f"Could not detect columns for page {page}")
                    columns_by_page[page] = []

    # Export
    exporter = IDMLExporter()
    return exporter.export_with_anchored_objects(
        source_idml, output_idml, manifest, document, columns_by_page
    )
