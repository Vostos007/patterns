# KPS Extraction Module

## Overview

The extraction module provides text and structure extraction from PDF knitting patterns using Docling's semantic understanding capabilities.

## Components

### DoclingExtractor

Main text extraction class that converts PDF documents into structured KPSDocument format.

**Key Features:**
- Semantic structure detection (headings, paragraphs, lists, tables)
- Automatic section type detection using pattern matching
- Reading order preservation
- Block-level granularity with unique IDs
- Multi-language support (Russian, English, French)
- OCR fallback for scanned PDFs

## Usage

### Basic Extraction

```python
from pathlib import Path
from kps.extraction import DoclingExtractor

# Create extractor with default configuration
extractor = DoclingExtractor()

# Extract document
document = extractor.extract_document(
    pdf_path=Path("patterns/bonjour-gloves.pdf"),
    slug="bonjour-gloves"
)

# Access extracted data
print(f"Title: {document.metadata.title}")
print(f"Sections: {len(document.sections)}")
print(f"Total blocks: {sum(len(s.blocks) for s in document.sections)}")
```

### Custom Configuration

```python
# Configure extraction parameters
extractor = DoclingExtractor(
    languages=["ru", "en"],  # Prioritize Russian and English
    ocr_enabled=True,        # Enable OCR for scanned pages
    page_range=(0, 20)       # Extract only first 20 pages
)

document = extractor.extract_document(pdf_path, slug)
```

### Accessing Extracted Content

```python
# Iterate through sections
for section in document.sections:
    print(f"\n{section.section_type.value}: {section.title}")

    # Access blocks
    for block in section.blocks:
        print(f"  [{block.block_type.value}] {block.block_id}")
        print(f"  {block.content[:100]}...")

        # Block metadata
        if block.bbox:
            print(f"  Position: ({block.bbox.x0}, {block.bbox.y0})")
        if block.page_number is not None:
            print(f"  Page: {block.page_number}")
```

### Searching Content

```python
# Find specific block by ID
block = document.find_block("p.materials.001")
if block:
    print(block.content)

# Get all blocks on a page
page_blocks = document.get_blocks_on_page(page_number=3)

# Get all blocks with bounding boxes (for caption detection)
blocks_with_bbox = document.get_all_blocks_with_bbox()
```

### Saving and Loading

```python
# Save to JSON
document.save_json(Path("output/extracted_document.json"))

# Load from JSON
from kps.core.document import KPSDocument
loaded_doc = KPSDocument.load_json(Path("output/extracted_document.json"))
```

## Section Type Detection

The extractor automatically detects section types using pattern matching on heading text:

### Russian Patterns

| Section Type | Patterns |
|-------------|----------|
| MATERIALS | материал, пряжа, нитки, инструмент |
| GAUGE | плотност, образец |
| SIZES | размер, обхват, длина |
| TECHNIQUES | техник, приём, метод |
| INSTRUCTIONS | инструкц, описание работ, выполнение |
| FINISHING | сборк, отделк, оформлен |
| ABBREVIATIONS | сокращен, условн.*обозначен |
| CONSTRUCTION | конструк, выкройк |

### English Patterns

Corresponding English patterns are also supported (density, gauge, size, technique, instruction, finishing, abbreviation, construction).

### Default Behavior

If no pattern matches, the section defaults to `INSTRUCTIONS` type.

## Block ID Format

Each content block receives a unique identifier following the format:

```
{type_prefix}.{section}.{number:03d}
```

### Examples

- `p.materials.001` - First paragraph in materials section
- `h.techniques.002` - Second heading in techniques section
- `tbl.sizes.001` - First table in sizes section
- `lst.instructions.005` - Fifth list in instructions section

### Type Prefixes

| Block Type | Prefix |
|-----------|--------|
| PARAGRAPH | `p` |
| HEADING | `h` |
| LIST | `lst` |
| TABLE | `tbl` |
| FIGURE | `fig` |

## Document Structure

### KPSDocument

```python
@dataclass
class KPSDocument:
    slug: str                      # Document identifier
    metadata: DocumentMetadata     # Title, author, language, etc.
    sections: List[Section]        # Ordered list of sections
```

### Section

```python
@dataclass
class Section:
    section_type: SectionType      # MATERIALS, GAUGE, SIZES, etc.
    title: str                     # Section heading text
    blocks: List[ContentBlock]     # Content blocks in reading order
```

### ContentBlock

```python
@dataclass
class ContentBlock:
    block_id: str                  # Unique identifier
    block_type: BlockType          # PARAGRAPH, HEADING, LIST, etc.
    content: str                   # Text content
    bbox: Optional[BBox]           # Position on page (if available)
    page_number: Optional[int]     # Source page number
    reading_order: int             # Order within page
```

## Error Handling

### DoclingExtractionError

Raised when Docling extraction fails:

```python
try:
    document = extractor.extract_document(pdf_path, slug)
except DoclingExtractionError as e:
    print(f"Extraction failed: {e}")
```

### Common Errors

1. **FileNotFoundError**: PDF file doesn't exist
2. **ValueError**: PDF is empty or contains no extractable content
3. **DoclingExtractionError**: Docling processing failed

### Best Practices

```python
from pathlib import Path
from kps.extraction import DoclingExtractor, DoclingExtractionError

def safe_extract(pdf_path: Path, slug: str):
    """Safely extract document with error handling."""
    # Validate file exists
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    # Validate file size
    if pdf_path.stat().st_size == 0:
        raise ValueError(f"PDF is empty: {pdf_path}")

    try:
        extractor = DoclingExtractor()
        document = extractor.extract_document(pdf_path, slug)

        # Validate extraction
        if not document.sections:
            raise ValueError("No sections extracted")

        return document

    except DoclingExtractionError as e:
        # Log error and re-raise
        logging.error(f"Extraction failed for {pdf_path}: {e}")
        raise
```

## Configuration

### Language Priority

Languages are processed in order of priority:

```python
extractor = DoclingExtractor(languages=["ru", "en", "fr"])
# Russian has highest priority, then English, then French
```

### OCR Settings

OCR is enabled by default for scanned PDFs:

```python
# Disable OCR for digital-only PDFs (faster)
extractor = DoclingExtractor(ocr_enabled=False)
```

### Page Range Limits

Extract only specific page ranges:

```python
# Extract pages 5-15 only
extractor = DoclingExtractor(page_range=(5, 15))
```

## Integration with Pipeline

The DoclingExtractor is designed to work with the broader KPS pipeline:

```python
from kps.extraction import DoclingExtractor
from kps.anchoring import AnchoringAlgorithm
from kps.translation import TranslationOrchestrator

# 1. Extract text structure
extractor = DoclingExtractor()
document = extractor.extract_document(pdf_path, slug)

# 2. Extract assets (separate step)
from kps.extraction import PyMuPDFExtractor
asset_extractor = PyMuPDFExtractor()
asset_ledger = asset_extractor.extract_all(pdf_path)

# 3. Anchor assets to text
anchoring = AnchoringAlgorithm()
asset_ledger = anchoring.attach_anchors(document, asset_ledger)

# 4. Translate
translator = TranslationOrchestrator()
translated_docs = translator.translate(document, target_langs=["en", "fr"])
```

## Testing

Run unit tests:

```bash
pytest tests/unit/test_docling_extractor.py -v
```

Run with coverage:

```bash
pytest tests/unit/test_docling_extractor.py --cov=kps.extraction.docling_extractor
```

## Demo Script

Run the demo script to test extraction:

```bash
python examples/docling_extraction_demo.py patterns/sample.pdf --slug sample-pattern
```

With JSON output:

```bash
python examples/docling_extraction_demo.py \
    patterns/sample.pdf \
    --slug sample-pattern \
    --output output/extracted.json
```

## Limitations

1. **Docling Dependency**: Requires Docling 2.0+ to be installed
2. **PDF Quality**: Scanned PDFs may require OCR, which is slower
3. **Complex Layouts**: Multi-column layouts may affect reading order
4. **Custom Sections**: Non-standard section names may not be detected accurately

## Future Improvements

- [ ] Support for custom section detection patterns
- [ ] Improved multi-column layout handling
- [ ] Table structure extraction (not just text)
- [ ] Figure/image region detection
- [ ] Custom block ID format configuration
- [ ] Parallel processing for large PDFs

## See Also

- [KPS Master Plan](../../docs/KPS_MASTER_PLAN.md) - Overall system architecture
- [Document Models](../core/document.py) - Core data structures
- [PyMuPDF Extractor](./pymupdf_extractor.py) - Asset extraction
- [Anchoring Algorithm](../anchoring/anchor_map.py) - Asset-to-text linking
