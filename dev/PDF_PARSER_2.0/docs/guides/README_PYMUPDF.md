# PyMuPDF Graphics Extraction - Quick Start

## Status: COMPLETE ✅

All 12 enhancements implemented for KPS v2.0 Day 3.

---

## Quick Usage

```python
from pathlib import Path
from kps.extraction.pymupdf_extractor import PyMuPDFExtractor, PyMuPDFExtractorConfig

# Configure and extract
extractor = PyMuPDFExtractor(PyMuPDFExtractorConfig(vector_dpi=300))
ledger = extractor.extract_assets(
    pdf_path=Path("pattern.pdf"),
    output_dir=Path("output/assets")
)

# Results
print(f"Extracted {len(ledger.assets)} assets from {ledger.total_pages} pages")
print(ledger.completeness_check())
```

---

## Files Created

### Implementation
- `/kps/extraction/pymupdf_extractor.py` - Main extractor (850+ lines)
- `/kps/extraction/__init__.py` - Module exports

### Documentation
- `/docs/PYMUPDF_EXTRACTION.md` - Complete usage guide
- `/docs/12_ENHANCEMENTS.md` - Enhancement reference
- `/docs/ASSET_METADATA_STRUCTURE.md` - Asset structure details
- `/PYMUPDF_IMPLEMENTATION_SUMMARY.md` - Implementation summary

### Examples
- `/examples/pymupdf_extraction_demo.py` - Standalone demo
- `/test_pymupdf_extraction.py` - Comprehensive test

---

## 12 Enhancements Summary

1. **CTM Extraction** - 6-element transform matrix
2. **SMask & Clipping** - Transparency detection
3. **Font Audit** - Vector PDF fonts
4. **SHA256 Hashing** - Content deduplication
5. **Multi-Occurrence** - Same content tracking
6. **BBox Extraction** - Anchoring coordinates
7. **Page Number** - Document structure
8. **ICC Profiles** - Color accuracy
9. **Image Dimensions** - DPI calculation
10. **File Export** - PNG/PDF/JPEG files
11. **Vector Graphics** - PDF + PNG fallback
12. **Table Extraction** - PDF/PNG snapshots

---

## Asset Types

- `IMAGE` - XObject bitmap images
- `VECTOR_PDF` - Scalable vector graphics
- `VECTOR_PNG` - Rasterized fallback
- `TABLE_SNAP` - Table snapshots (default)
- `TABLE_LIVE` - Structured table data

---

## Asset ID Format

```
{type}-{sha256[:12]}-p{page}-occ{occurrence}
```

Examples:
- `img-abc123def456-p0-occ1`
- `vec-789xyz012abc-p1-occ1`
- `tbl-456def789ghi-p3-occ1`

---

## Output Structure

```
output/
├── images/
│   └── img-{hash}-p{page}-occ{n}.{png|jpeg}
├── vectors/
│   ├── vec-{hash}-p{page}-occ{n}.pdf
│   └── vec-{hash}-p{page}-occ{n}.png
└── tables/
    ├── tbl-{hash}-p{page}-occ{n}.pdf
    └── tbl-{hash}-p{page}-occ{n}.png
```

---

## Run Demo

```bash
python examples/pymupdf_extraction_demo.py pattern.pdf
```

---

## Next Step (Day 4)

Vision model anchoring to populate `asset.anchor_to` field.

---

## Documentation Links

- [Full Usage Guide](docs/PYMUPDF_EXTRACTION.md)
- [Enhancement Details](docs/12_ENHANCEMENTS.md)
- [Asset Structure](docs/ASSET_METADATA_STRUCTURE.md)
- [Implementation Summary](PYMUPDF_IMPLEMENTATION_SUMMARY.md)
