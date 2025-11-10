# KPS v2.0 - Knitting Pattern System

> Production-ready PDF localization pipeline with **100% guarantee** of visual asset preservation

## Quick Start

```bash
# 1. Setup
cd PDF_PARSER_2.0
poetry install

# 2. Extract document
poetry run kps extract \
  --pdf "documents/pattern.pdf" \
  --slug "pattern-name" \
  --out-dir "work/pattern" \
  --detect-captions \
  --vector-as-pdf

# 3. Translate
poetry run kps translate \
  --source "work/pattern/kps.json" \
  --manifest "work/pattern/manifest.json" \
  --lang en fr \
  --glossary knitting \
  --out "output/pattern"

# 4. QA Check (fail-closed)
poetry run kps preflight \
  --src "documents/pattern.pdf" \
  --tgt "output/pattern/FR/pattern_FR.pdf" \
  --manifest "work/pattern/manifest.json"
```

## What Makes KPS v2.0 Unique

### 100% Asset Preservation Guarantee

**Dual Extraction**:
- **Docling** for text/structure
- **PyMuPDF** for ALL graphics (images, vectors, tables)

**Asset Ledger** (source of truth):
- SHA256 hash for each asset
- CTM (transform matrix) for exact geometry
- SMask/Clip support for transparency
- Fonts audit for vector PDFs

**Fail-Closed QA**:
- ✅ Completeness: manifest ↔ placed = 100%
- ✅ Geometry: ≥98% in tolerance (±2pt or 1%)
- ✅ Visual: ≤2% pixel diff by asset masks
- ✅ DPI: All ≥300 dpi effective
- ✅ Colorspace: ICC profiles embedded

**Any QA failure → Build stops**

## Project Status

**Current Phase**: Setup & Documentation
**Next**: Day 1 - Core Models + Extraction

See `docs/KPS_MASTER_PLAN.md` for complete plan

## Architecture

```
PDF → Dual Extraction → Anchoring → Translation → InDesign → QA → PDF/X-4
      (Docling+PyMuPDF)  [[markers]]  (OpenAI)    (JSX)     (3-stage)
```

## Key Features

1. **Column-aware anchoring** - No cross-column placement errors
2. **Object Labels** - JSON metadata on every placed asset
3. **FR typography** - U+202F narrow NBSP (not U+00A0)
4. **PDF/X-4 Preserve Numbers** - CMYK colors unchanged
5. **Normalized geometry** - Comparison in column coordinates
6. **Visual diff by masks** - Only compare asset regions
7. **DPI validation** - Effective DPI calculated post-placement
8. **Full audit trail** - Complete provenance tracking

## Documentation

- **Master Plan**: `docs/KPS_MASTER_PLAN.md` (this is THE reference document)
- **User Guide**: `docs/USER_GUIDE.md` (coming soon)
- **API Reference**: `docs/API_REFERENCE.md` (coming soon)
- **Troubleshooting**: `docs/TROUBLESHOOTING.md` (coming soon)

## Integration with Existing Projects

### From PDF_parser
- ✅ Placeholder system (direct copy)
- ✅ Glossary selector (direct copy)
- ✅ Translation orchestrator (adapted: async, configurable)
- ✅ Newline preservation logic

### From KPS.zip
- ✅ InDesign master template
- ✅ Paragraph/Character/Object styles
- ✅ JSX scripts (enhanced with labels + U+202F + Preserve Numbers)
- ✅ Glossaries (knitting, sewing)

## Dependencies

```toml
[tool.poetry.dependencies]
python = "^3.11"
docling = ">=2.0.0"
pymupdf = ">=1.23.0"
openai = ">=1.0.0"
typer = {extras = ["all"], version = ">=0.12.0"}
pydantic = ">=2.0.0"
pyyaml = ">=6.0"
pillow = ">=10.0.0"
camelot-py = {extras = ["cv"], version = ">=0.11.0"}
pdfplumber = ">=0.10.0"
```

## Timeline

- **Day 1-2**: Core + Enhanced Extraction
- **Day 3**: Anchoring + Markers
- **Day 4**: Translation Pipeline
- **Day 5**: InDesign Integration
- **Day 6**: QA Suite + Tests

**Goal**: Production-ready in 6 days

## License

(To be determined)

## Contributors

(To be added)

---

**For complete details, see `docs/KPS_MASTER_PLAN.md`**
