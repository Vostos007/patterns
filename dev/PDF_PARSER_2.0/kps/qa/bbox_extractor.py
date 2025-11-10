"""BBox extraction from output PDFs and InDesign labels.

This module provides utilities for extracting actual bounding boxes
from the output PDF to compare against expected placements.

Extraction Methods:
    1. InDesign Label Parsing: Extract from embedded JSON labels
    2. PyMuPDF Object Detection: Extract from PDF page objects
    3. Hybrid Approach: Combine both methods for verification

Author: KPS v2.0 QA Suite
Last Modified: 2025-11-06
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import fitz  # PyMuPDF

from ..core.bbox import BBox


class BBoxExtractor:
    """Extract bounding boxes from output PDFs."""

    def __init__(self):
        """Initialize bbox extractor."""
        self.debug = False

    def extract_from_indesign_labels(
        self,
        pdf_path: Path
    ) -> Dict[str, BBox]:
        """Extract bboxes from InDesign embedded labels.

        InDesign labels are embedded as XML metadata in PDF objects.
        We parse these to get the actual placement coordinates.

        Args:
            pdf_path: Path to output PDF

        Returns:
            Dict mapping asset_id -> actual BBox
        """
        doc = fitz.open(pdf_path)
        asset_bboxes = {}

        for page_num in range(len(doc)):
            page = doc[page_num]

            # Extract all annotations and metadata
            # InDesign embeds labels as custom PDF entries
            # This is a simplified implementation - actual implementation
            # would need to parse InDesign-specific metadata

            # Get page dictionary
            page_dict = page.get_text("dict")

            # Look for embedded labels in image objects
            for img_info in page.get_images(full=True):
                xref = img_info[0]

                # Try to get label from image metadata
                try:
                    # Get image object
                    obj = doc.xref_object(xref)

                    # Look for KPS label in metadata
                    if "/KPS_Label" in obj:
                        # Extract label JSON
                        label_data = self._extract_label_from_object(obj)
                        if label_data:
                            asset_id = label_data.get("asset_id")
                            bbox_data = label_data.get("bbox_placed")

                            if asset_id and bbox_data:
                                bbox = BBox(*bbox_data)
                                asset_bboxes[asset_id] = bbox
                except Exception as e:
                    if self.debug:
                        print(f"Error extracting label from xref {xref}: {e}")
                    continue

        doc.close()
        return asset_bboxes

    def extract_from_page_objects(
        self,
        pdf_path: Path
    ) -> Dict[int, List[BBox]]:
        """Extract all object bboxes from PDF, grouped by page.

        This method extracts bounding boxes directly from PDF page objects
        (images, text, graphics) without relying on embedded labels.

        Args:
            pdf_path: Path to output PDF

        Returns:
            Dict mapping page_num -> list of BBoxes
        """
        doc = fitz.open(pdf_path)
        all_bboxes = {}

        for page_num in range(len(doc)):
            page = doc[page_num]
            page_bboxes = []

            # Extract image bboxes
            image_bboxes = self._extract_image_bboxes(page)
            page_bboxes.extend(image_bboxes)

            # Extract vector graphic bboxes (if needed)
            # This is more complex and may require parsing page content stream

            all_bboxes[page_num] = page_bboxes

        doc.close()
        return all_bboxes

    def extract_from_placed_labels(
        self,
        placed_labels: List[dict]
    ) -> Dict[str, BBox]:
        """Extract bboxes from placed labels data structure.

        This is the primary method when working with InDesign JSX output
        that includes placement information in JSON format.

        Args:
            placed_labels: List of label dicts from InDesign placement

        Returns:
            Dict mapping asset_id -> actual BBox
        """
        asset_bboxes = {}

        for label in placed_labels:
            asset_id = label.get("asset_id")
            bbox_data = label.get("bbox_placed")

            if asset_id and bbox_data:
                # bbox_data is expected to be [x0, y0, x1, y1]
                if len(bbox_data) == 4:
                    bbox = BBox(*bbox_data)
                    asset_bboxes[asset_id] = bbox
                else:
                    if self.debug:
                        print(f"Invalid bbox data for {asset_id}: {bbox_data}")

        return asset_bboxes

    def extract_with_verification(
        self,
        pdf_path: Path,
        placed_labels: List[dict]
    ) -> Tuple[Dict[str, BBox], List[str]]:
        """Extract bboxes with cross-verification.

        Extracts bboxes from both placed labels and PDF objects,
        then verifies consistency.

        Args:
            pdf_path: Path to output PDF
            placed_labels: List of label dicts from InDesign

        Returns:
            Tuple of (asset_bboxes, warnings)
        """
        warnings = []

        # Primary: extract from placed labels
        label_bboxes = self.extract_from_placed_labels(placed_labels)

        # Verification: extract from PDF objects
        page_bboxes = self.extract_from_page_objects(pdf_path)

        # Count mismatches
        total_from_labels = len(label_bboxes)
        total_from_pdf = sum(len(bboxes) for bboxes in page_bboxes.values())

        if total_from_labels != total_from_pdf:
            warnings.append(
                f"Object count mismatch: {total_from_labels} from labels vs "
                f"{total_from_pdf} from PDF objects"
            )

        # Use label bboxes as primary (more accurate)
        return label_bboxes, warnings

    def _extract_image_bboxes(self, page: fitz.Page) -> List[BBox]:
        """Extract bboxes of all images on a page.

        Args:
            page: PyMuPDF Page object

        Returns:
            List of BBoxes for images
        """
        bboxes = []

        # Get all images with their transformation matrices
        image_list = page.get_images(full=True)

        for img_info in image_list:
            xref = img_info[0]

            # Get image locations (can be multiple instances)
            locations = page.get_image_rects(xref)

            for rect in locations:
                # Convert fitz.Rect to BBox
                # fitz uses (x0, y0, x1, y1) format which matches BBox
                bbox = BBox(
                    x0=rect.x0,
                    y0=rect.y0,
                    x1=rect.x1,
                    y1=rect.y1
                )
                bboxes.append(bbox)

        return bboxes

    def _extract_label_from_object(self, obj_string: str) -> Optional[dict]:
        """Extract KPS label JSON from PDF object string.

        Args:
            obj_string: PDF object as string

        Returns:
            Label dict or None if not found
        """
        # Look for KPS_Label entry
        # Format: /KPS_Label (encoded_json)

        import re

        pattern = r'/KPS_Label\s*\((.*?)\)'
        match = re.search(pattern, obj_string)

        if match:
            encoded_json = match.group(1)

            # Decode and parse JSON
            try:
                # Handle PDF string encoding
                decoded = encoded_json.encode('latin1').decode('utf-8')
                label_data = json.loads(decoded)
                return label_data
            except Exception as e:
                if self.debug:
                    print(f"Error decoding label JSON: {e}")
                return None

        return None

    def compare_bboxes(
        self,
        bbox1: BBox,
        bbox2: BBox,
        tolerance: float = 0.1
    ) -> Tuple[bool, float]:
        """Compare two bboxes for similarity.

        Args:
            bbox1: First bbox
            bbox2: Second bbox
            tolerance: Tolerance in points (default: 0.1)

        Returns:
            Tuple of (are_similar, max_difference)
        """
        differences = [
            abs(bbox1.x0 - bbox2.x0),
            abs(bbox1.y0 - bbox2.y0),
            abs(bbox1.x1 - bbox2.x1),
            abs(bbox1.y1 - bbox2.y1)
        ]

        max_diff = max(differences)
        are_similar = max_diff <= tolerance

        return are_similar, max_diff


class LabelParser:
    """Parse InDesign placement labels from various formats."""

    @staticmethod
    def parse_json_label(label_json: str) -> Optional[dict]:
        """Parse label from JSON string.

        Args:
            label_json: JSON string

        Returns:
            Parsed label dict or None
        """
        try:
            return json.loads(label_json)
        except json.JSONDecodeError:
            return None

    @staticmethod
    def parse_jsx_output(jsx_output: str) -> List[dict]:
        """Parse placement labels from JSX output.

        JSX script outputs placement information as JSON array.

        Args:
            jsx_output: JSX script stdout

        Returns:
            List of label dicts
        """
        labels = []

        # Look for JSON array in output
        import re

        # Find JSON array pattern
        pattern = r'\[[\s\S]*\]'
        match = re.search(pattern, jsx_output)

        if match:
            try:
                json_str = match.group(0)
                labels = json.loads(json_str)
            except json.JSONDecodeError as e:
                print(f"Error parsing JSX output JSON: {e}")

        return labels

    @staticmethod
    def validate_label_structure(label: dict) -> Tuple[bool, Optional[str]]:
        """Validate label has required fields.

        Args:
            label: Label dict

        Returns:
            Tuple of (is_valid, error_message)
        """
        required_fields = ["asset_id", "page_number", "bbox_placed"]

        for field in required_fields:
            if field not in label:
                return False, f"Missing required field: {field}"

        # Validate bbox_placed format
        bbox_data = label.get("bbox_placed")
        if not isinstance(bbox_data, (list, tuple)) or len(bbox_data) != 4:
            return False, f"Invalid bbox_placed format: {bbox_data}"

        return True, None


def extract_all_labels(
    placed_labels: List[dict],
    pdf_path: Optional[Path] = None,
    verify: bool = False
) -> Dict[str, BBox]:
    """Convenience function to extract all asset bboxes.

    Args:
        placed_labels: List of placement labels from InDesign
        pdf_path: Optional path to PDF for verification
        verify: If True, verify against PDF objects

    Returns:
        Dict mapping asset_id -> BBox
    """
    extractor = BBoxExtractor()

    if verify and pdf_path:
        bboxes, warnings = extractor.extract_with_verification(
            pdf_path=pdf_path,
            placed_labels=placed_labels
        )

        if warnings:
            print("Warnings during bbox extraction:")
            for warning in warnings:
                print(f"  - {warning}")

        return bboxes
    else:
        return extractor.extract_from_placed_labels(placed_labels)
