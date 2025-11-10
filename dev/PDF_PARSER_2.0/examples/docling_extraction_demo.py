"""Demo script for Docling-based text extraction.

This script demonstrates how to use the DoclingExtractor to extract
structured text from a PDF pattern file.

Usage:
    python examples/docling_extraction_demo.py <pdf_path> [--slug <slug>]

Example:
    python examples/docling_extraction_demo.py patterns/bonjour-gloves.pdf --slug bonjour-gloves
"""

import argparse
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from kps.extraction import DoclingExtractor
from kps.core.document import SectionType, BlockType


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def main():
    """Run extraction demo."""
    parser = argparse.ArgumentParser(description="Extract text from PDF using Docling")
    parser.add_argument("pdf_path", type=Path, help="Path to PDF file")
    parser.add_argument(
        "--slug",
        type=str,
        default=None,
        help="Document slug (default: filename without extension)",
    )
    parser.add_argument(
        "--no-ocr",
        action="store_true",
        help="Disable OCR fallback",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSON file path (optional)",
    )

    args = parser.parse_args()

    # Validate PDF exists
    if not args.pdf_path.exists():
        logger.error(f"PDF file not found: {args.pdf_path}")
        sys.exit(1)

    # Determine slug
    slug = args.slug or args.pdf_path.stem

    logger.info("=" * 80)
    logger.info("Docling Extraction Demo")
    logger.info("=" * 80)
    logger.info(f"PDF: {args.pdf_path}")
    logger.info(f"Slug: {slug}")
    logger.info(f"OCR: {'disabled' if args.no_ocr else 'enabled'}")
    logger.info("=" * 80)

    try:
        # Create extractor
        extractor = DoclingExtractor(
            languages=["ru", "en", "fr"],
            ocr_enabled=not args.no_ocr,
        )

        # Extract document
        logger.info("\nExtracting document...")
        document = extractor.extract_document(args.pdf_path, slug)

        # Display results
        logger.info("\n" + "=" * 80)
        logger.info("EXTRACTION RESULTS")
        logger.info("=" * 80)

        # Metadata
        logger.info("\nMETADATA:")
        logger.info(f"  Title: {document.metadata.title}")
        logger.info(f"  Author: {document.metadata.author or 'N/A'}")
        logger.info(f"  Language: {document.metadata.language}")
        logger.info(f"  Version: {document.metadata.version}")

        # Statistics
        total_blocks = sum(len(s.blocks) for s in document.sections)
        logger.info(f"\nSTATISTICS:")
        logger.info(f"  Total sections: {len(document.sections)}")
        logger.info(f"  Total blocks: {total_blocks}")

        # Section breakdown
        logger.info(f"\nSECTION BREAKDOWN:")
        for i, section in enumerate(document.sections, 1):
            logger.info(f"\n  {i}. {section.section_type.value.upper()}")
            logger.info(f"     Title: {section.title}")
            logger.info(f"     Blocks: {len(section.blocks)}")

            # Block type counts
            block_counts = {}
            for block in section.blocks:
                block_type = block.block_type.value
                block_counts[block_type] = block_counts.get(block_type, 0) + 1

            logger.info(f"     Block types: {block_counts}")

            # Show first few blocks
            logger.info(f"     First blocks:")
            for j, block in enumerate(section.blocks[:3], 1):
                content_preview = block.content[:60].replace("\n", " ")
                if len(block.content) > 60:
                    content_preview += "..."
                logger.info(
                    f"       {j}. [{block.block_type.value}] "
                    f"{block.block_id}: {content_preview}"
                )

            if len(section.blocks) > 3:
                logger.info(f"       ... and {len(section.blocks) - 3} more blocks")

        # Section type distribution
        logger.info(f"\nSECTION TYPE DISTRIBUTION:")
        section_type_counts = {}
        for section in document.sections:
            section_type = section.section_type.value
            section_type_counts[section_type] = (
                section_type_counts.get(section_type, 0) + 1
            )

        for section_type, count in sorted(section_type_counts.items()):
            logger.info(f"  {section_type}: {count}")

        # Block type distribution
        logger.info(f"\nBLOCK TYPE DISTRIBUTION:")
        block_type_counts = {}
        for section in document.sections:
            for block in section.blocks:
                block_type = block.block_type.value
                block_type_counts[block_type] = block_type_counts.get(block_type, 0) + 1

        for block_type, count in sorted(block_type_counts.items()):
            logger.info(f"  {block_type}: {count}")

        # Sample content from first section
        if document.sections:
            first_section = document.sections[0]
            logger.info(f"\nSAMPLE CONTENT (First section: {first_section.title}):")
            logger.info("-" * 80)
            sample_text = first_section.get_all_text()[:500]
            logger.info(sample_text)
            if len(first_section.get_all_text()) > 500:
                logger.info("...")
            logger.info("-" * 80)

        # Save to JSON if requested
        if args.output:
            logger.info(f"\nSaving to {args.output}...")
            document.save_json(args.output)
            logger.info(f"Saved successfully!")

        logger.info("\n" + "=" * 80)
        logger.info("Extraction completed successfully!")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"\nExtraction failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
