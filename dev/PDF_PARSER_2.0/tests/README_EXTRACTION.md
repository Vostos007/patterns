# KPS v2.0 Extraction & Translation Test Suite (Day 3)

> Comprehensive test coverage for PDF extraction and translation pipeline

**Created**: 2025-11-06
**Status**: Ready for Day 3 Implementation
**Coverage Target**: 80% minimum

---

## Overview

This test suite validates the Day 3 implementation of KPS v2.0:
- **Docling-based text extraction** → KPSDocument
- **PyMuPDF-based asset extraction** → AssetLedger
- **Translation segmentation** → TranslationSegments
- **OpenAI translation orchestration** → Translated documents
- **Full pipeline integration** → End-to-end validation

All tests are ready to run once the extraction and translation modules are implemented.

---

## Test File Structure

```
tests/
├── test_docling_extraction.py          # 15 tests - Docling adapter
├── test_pymupdf_extraction.py          # 17 tests - PyMuPDF asset extraction
├── test_segmentation.py                # 14 tests - Segmentation strategy
├── test_translation_orchestrator.py    # 15 tests - OpenAI orchestration
├── integration/
│   ├── test_extraction_pipeline.py     # 14 tests - Full extraction
│   └── test_translation_pipeline.py    # 10 tests - Full translation
├── conftest.py                         # Updated with 25+ PDF fixtures
└── README_EXTRACTION.md               # This file
```

**Total Test Count**: 85 tests
**Critical Tests**: 8 (newline preservation, marker survival, asset coverage)

---

## Test Categories

### 1. Unit Tests - Docling Extraction (15 tests)

**File**: `tests/test_docling_extraction.py`

| Test | Validates | Critical |
|------|-----------|----------|
| `test_extract_single_page_document` | Basic extraction works | ✓ |
| `test_extract_multi_page_document` | Multi-page handling | ✓ |
| `test_section_type_detection_russian_patterns` | Russian section headers mapped correctly | ✓ |
| `test_block_id_generation_format` | Block ID format: "type.section.###" | ✓ |
| `test_heading_hierarchy_preservation` | h1/h2/h3 hierarchy maintained | - |
| `test_reading_order_preservation` | Sequential reading order | - |
| `test_bbox_extraction_for_all_blocks` | All blocks have bbox | ✓ |
| `test_error_handling_invalid_pdf` | Invalid PDF raises error | - |
| `test_error_handling_empty_document` | Empty PDF handled gracefully | - |
| `test_error_handling_corrupted_pdf` | Corrupted PDF raises error | - |
| `test_block_content_not_empty` | Blocks have content | - |
| `test_russian_text_encoding_preserved` | Cyrillic characters preserved | ✓ |
| `test_table_block_detection` | Tables detected as BlockType.TABLE | - |
| `test_performance_10_page_extraction` | < 30s for 10 pages | ✓ |

**Coverage Focus**: Document structure, section typing, Russian text handling

---

### 2. Unit Tests - PyMuPDF Extraction (17 tests)

**File**: `tests/test_pymupdf_extraction.py`

| Test | Validates | Critical |
|------|-----------|----------|
| `test_extract_xobject_images_basic` | Image extraction with SHA256 | ✓ |
| `test_ctm_extraction_for_transforms` | CTM (transform matrix) captured | ✓ |
| `test_smask_transparency_extraction` | SMask for transparency | - |
| `test_sha256_hashing_deduplication` | Duplicate detection via SHA256 | ✓ |
| `test_multi_occurrence_tracking` | Same hash → different asset_id | ✓ |
| `test_vector_extraction_as_pdf` | Vector graphics extracted | - |
| `test_font_audit_for_vector_pdf` | Font metadata for vectors | - |
| `test_icc_profile_extraction` | ICC color profiles captured | - |
| `test_file_export_png_format` | PNG export for images | ✓ |
| `test_file_export_pdf_format_for_vectors` | PDF export for vectors | - |
| `test_asset_ledger_completeness_check` | Completeness check method | ✓ |
| `test_error_handling_corrupted_image` | Corrupted images handled | - |
| `test_error_handling_missing_resources` | Missing resources handled | - |
| `test_table_snapshot_extraction` | Table snapshots captured | - |
| `test_bbox_accuracy_for_assets` | Asset bbox coordinates valid | ✓ |
| `test_asset_id_format_validation` | Asset ID format correct | ✓ |
| `test_performance_large_pdf_extraction` | < 60s for 50+ assets | ✓ |

**Coverage Focus**: Asset extraction, deduplication, metadata, file export

---

### 3. Unit Tests - Segmentation (14 tests)

**File**: `tests/test_segmentation.py`

| Test | Validates | Critical |
|------|-----------|----------|
| `test_one_segment_per_block_strategy` | One segment per block | ✓ |
| `test_placeholder_encoding_urls` | URLs encoded as placeholders | ✓ |
| `test_placeholder_encoding_emails` | Emails encoded | ✓ |
| `test_placeholder_encoding_numbers` | Numbers with separators encoded | - |
| `test_placeholder_encoding_asset_markers` | [[asset_id]] markers protected | ✓✓✓ |
| `test_newline_preservation_critical` | Newlines preserved through encoding | ✓✓✓ |
| `test_segment_id_format` | Segment ID: "block_id.seg0" | ✓ |
| `test_merge_after_translation` | Merge reconstructs structure | ✓ |
| `test_edge_case_empty_blocks` | Empty blocks handled | - |
| `test_edge_case_blocks_with_only_markers` | Marker-only blocks handled | - |
| `test_validation_segment_count_matches_block_count` | Count validation | ✓ |
| `test_placeholder_encoding_mixed_content` | Mixed placeholders handled | - |
| `test_segment_preserves_block_metadata` | Metadata preserved | - |
| `test_newline_preservation_with_markers` | Newlines + markers together | ✓✓✓ |

**Coverage Focus**: Segmentation strategy, placeholder encoding, newline preservation

---

### 4. Unit Tests - Translation Orchestrator (15 tests)

**File**: `tests/test_translation_orchestrator.py`

Uses mocked OpenAI API for deterministic testing.

| Test | Validates | Critical |
|------|-----------|----------|
| `test_language_detection` | Auto-detect source language | - |
| `test_translate_batch_single_language` | Batch translation to EN | ✓ |
| `test_translate_batch_multiple_languages` | Translation to EN + FR | - |
| `test_placeholder_preservation_in_translation` | Placeholders survive translation | ✓✓✓ |
| `test_newline_preservation_in_translation` | Newlines preserved in API call | ✓✓✓ |
| `test_glossary_context_injection` | Glossary context in prompt | ✓ |
| `test_batch_splitting_50_segments` | Batch splitting logic | - |
| `test_retry_logic_on_api_failure` | Retry with backoff | - |
| `test_token_counting_and_cost_estimation` | Token/cost tracking | - |
| `test_progress_callback_mechanism` | Progress callbacks | - |
| `test_error_handling_api_timeout` | Timeout handled | - |
| `test_error_handling_invalid_api_key` | Auth errors handled | - |
| `test_segment_count_mismatch_fallback` | Fallback on count mismatch | - |
| `test_asset_marker_preservation_end_to_end` | Markers survive full flow | ✓✓✓ |
| `test_empty_segments_handling` | Empty input handled | - |

**Coverage Focus**: API integration, placeholder preservation, error handling

---

### 5. Integration Tests - Extraction Pipeline (14 tests)

**File**: `tests/integration/test_extraction_pipeline.py`

Tests Day 2 + Day 3 integration.

| Test | Validates | Critical |
|------|-----------|----------|
| `test_full_extraction_text_and_assets` | PDF → Document + Ledger | ✓✓✓ |
| `test_extraction_with_asset_anchoring` | Extraction + anchoring | ✓✓✓ |
| `test_extraction_with_marker_injection` | Extraction + anchoring + markers | ✓✓✓ |
| `test_newline_preservation_end_to_end` | Newlines through extraction | ✓✓✓ |
| `test_100_percent_asset_coverage` | All assets anchored + marked | ✓✓✓ |
| `test_asset_marker_integrity` | Marker format validation | ✓✓✓ |
| `test_multi_column_layout_extraction` | Multi-column handling | - |
| `test_table_extraction_and_anchoring` | Tables extracted + anchored | - |
| `test_russian_text_encoding_preservation` | Russian text preserved | ✓ |
| `test_performance_10_page_extraction_pipeline` | < 30s for full pipeline | ✓ |
| `test_bbox_coordinate_consistency` | BBox coordinates consistent | - |
| `test_json_serialization_roundtrip` | Save/load JSON | - |
| `test_error_recovery_partial_extraction` | Partial corruption handled | - |

**Coverage Focus**: Full extraction pipeline, Day 2 integration, performance

---

### 6. Integration Tests - Translation Pipeline (10 tests)

**File**: `tests/integration/test_translation_pipeline.py`

Tests full translation workflow with mocked OpenAI.

| Test | Validates | Critical |
|------|-----------|----------|
| `test_full_pipeline_extract_to_translated` | Complete pipeline | ✓✓✓ |
| `test_newline_preservation_end_to_end_critical` | Newlines through translation | ✓✓✓ |
| `test_asset_marker_preservation_critical` | Markers through translation | ✓✓✓ |
| `test_placeholder_preservation_urls_emails_numbers` | All placeholders preserved | ✓ |
| `test_glossary_term_application` | Glossary terms applied | ✓ |
| `test_multi_language_output` | EN + FR outputs | - |
| `test_batch_processing_100_plus_segments` | Large document handling | - |
| `test_cost_tracking_accuracy` | Cost tracking | - |
| `test_performance_full_pipeline_60_seconds` | < 60s for 10-page translation | ✓ |

**Coverage Focus**: End-to-end translation, critical feature preservation

---

## Critical Tests (Must Pass)

These 8 tests validate the most critical requirements:

### 1. Newline Preservation (3 tests)

```python
# Unit level
test_segmentation.py::test_newline_preservation_critical
test_segmentation.py::test_newline_preservation_with_markers

# Integration level
test_translation_pipeline.py::test_newline_preservation_end_to_end_critical
```

**Requirement**: Original newline count = final newline count (±tolerance)

---

### 2. Asset Marker Preservation (3 tests)

```python
# Unit level
test_translation_orchestrator.py::test_asset_marker_preservation_end_to_end

# Integration level
test_extraction_pipeline.py::test_extraction_with_marker_injection
test_translation_pipeline.py::test_asset_marker_preservation_critical
```

**Requirement**: All [[asset_id]] markers survive translation

---

### 3. 100% Asset Coverage (2 tests)

```python
test_extraction_pipeline.py::test_100_percent_asset_coverage
test_extraction_pipeline.py::test_asset_marker_integrity
```

**Requirement**:
- All assets have anchor_to set
- All anchored assets have markers in document
- No orphaned markers

---

## Running Tests

### Run All Tests

```bash
pytest tests/ -v
```

### Run by Category

```bash
# Unit tests only
pytest tests/test_*.py -v

# Integration tests only
pytest tests/integration/ -v

# Specific module
pytest tests/test_docling_extraction.py -v
```

### Run Critical Tests Only

```bash
pytest tests/ -v -k "critical"
```

### Run with Coverage

```bash
pytest tests/ --cov=kps.extraction --cov=kps.translation --cov-report=html
```

### Skip Slow Tests

```bash
pytest tests/ -v -m "not slow"
```

---

## Test Fixtures

All fixtures defined in `tests/conftest.py`:

### PDF Test Files (25 fixtures)

- `simple_pdf_path` - Single-page basic PDF
- `multi_page_pdf_path` - 3+ pages
- `russian_pattern_pdf_path` - Russian knitting pattern
- `two_column_pdf_path` - 2-column layout
- `pdf_with_images_path` - Multiple images
- `pdf_with_rotated_images_path` - Transformed images
- `pdf_with_transparency_path` - Images with SMask
- `pdf_with_duplicate_images_path` - Duplicate content
- `pdf_with_vector_graphics_path` - Vector drawings
- `pdf_with_tables_path` - Tables
- `ten_page_pdf_path` - 10-page document
- `large_pdf_with_many_assets_path` - 50+ assets
- `invalid_pdf_path` - Invalid file
- `corrupted_pdf_path` - Corrupted PDF
- ...and more (see conftest.py)

**Note**: Test PDFs should be created in `tests/fixtures/` directory. Tests will skip if PDF is missing.

---

## Creating Test PDFs

For CI/CD and local testing, minimal test PDFs should be created:

### Option 1: Use Existing Samples

Copy sample PDFs from project:

```bash
cp "Шаблон KPS.zip" tests/fixtures/
# Extract and rename for tests
```

### Option 2: Generate Minimal PDFs

Use `reportlab` or `pypdf` to generate minimal test PDFs:

```python
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

def create_simple_test_pdf(path):
    c = canvas.Canvas(str(path), pagesize=A4)
    c.drawString(100, 700, "Test PDF")
    c.drawString(100, 650, "Материалы")  # Russian section
    c.save()
```

### Option 3: Commit Test PDFs

For reliability, commit small test PDFs to repository:

```bash
git add tests/fixtures/*.pdf
git commit -m "Add test PDFs for extraction tests"
```

---

## Mocking Strategy

### OpenAI API Mocking

All translation tests use `unittest.mock.patch`:

```python
@patch('kps.translation.orchestrator.openai')
def test_translation(mock_openai):
    # Mock language detection
    detect_mock = Mock()
    detect_mock.choices = [Mock(message=Mock(content="ru"))]

    # Mock translation
    translate_mock = Mock()
    translate_mock.choices = [Mock(message=Mock(content="Translated"))]

    mock_openai.chat.completions.create.side_effect = [
        detect_mock, translate_mock
    ]
```

### Docling Mocking (Optional)

For faster tests, Docling can be mocked:

```python
@patch('kps.extraction.docling_extractor.DoclingDocument')
def test_extraction(mock_docling):
    # Return mock document structure
    pass
```

---

## Test Data Requirements

### Minimal Test Document

Each test PDF should contain:

1. **Text Extraction Tests**:
   - Russian section headers (Материалы, Техники, Инструкция)
   - Paragraphs with Cyrillic text
   - Headings (h1, h2, h3)
   - At least 1 table

2. **Asset Extraction Tests**:
   - 3+ images (JPEG/PNG)
   - 1 vector graphic
   - 1 transparent image (PNG with alpha)
   - 1 image appearing twice (duplicate test)

3. **Layout Tests**:
   - Single-column pages
   - 2-column pages
   - 3-column pages (optional)

---

## Performance Benchmarks

| Operation | Target | Test |
|-----------|--------|------|
| Extract 1-page PDF (text) | < 5s | `test_extract_single_page_document` |
| Extract 10-page PDF (text) | < 30s | `test_performance_10_page_extraction` |
| Extract assets (50 assets) | < 60s | `test_performance_large_pdf_extraction` |
| Full extraction pipeline (10 pages) | < 30s | `test_performance_10_page_extraction_pipeline` |
| Full translation pipeline (10 pages) | < 60s | `test_performance_full_pipeline_60_seconds` |

---

## Coverage Goals

| Module | Target Coverage | Priority |
|--------|----------------|----------|
| `kps.extraction.docling_extractor` | 85% | High |
| `kps.extraction.pymupdf_extractor` | 85% | High |
| `kps.extraction.segmenter` | 90% | Critical |
| `kps.translation.orchestrator` | 80% | High |
| `kps.core.placeholders` | 95% | Critical |

**Overall Target**: 80% minimum

---

## Test Markers

Pytest markers used:

```python
@pytest.mark.unit        # Unit tests (fast)
@pytest.mark.integration # Integration tests (slower)
@pytest.mark.slow        # Slow tests (>5s)
```

Configure in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
markers = [
    "unit: Unit tests",
    "integration: Integration tests",
    "slow: Slow tests (>5s)",
]
```

---

## Troubleshooting

### Tests Skipped (Missing PDF)

**Issue**: `pytest.skip("Test PDF not found")`

**Solution**: Create test PDFs in `tests/fixtures/` or set `PYTEST_SKIP_MISSING_PDFS=false`

---

### OpenAI API Key Error (Integration)

**Issue**: Tests fail with "API key not set"

**Solution**: Mocks should prevent API calls. Ensure `@patch('kps.translation.orchestrator.openai')` is present.

---

### Newline Count Mismatch

**Issue**: `test_newline_preservation_critical` fails

**Solution**:
1. Check placeholder encoding preserves `\n`
2. Check translation mock returns same newline count
3. Validate merge doesn't introduce extra newlines

---

### Asset Marker Missing

**Issue**: `test_asset_marker_preservation_critical` fails

**Solution**:
1. Verify marker injection works: `test_extraction_with_marker_injection`
2. Check placeholder encoding: `test_placeholder_encoding_asset_markers`
3. Validate decode restores markers: `decode_placeholders(encoded, mapping)`

---

## Next Steps

1. **Implement Extraction Modules**:
   - `kps/extraction/docling_extractor.py`
   - `kps/extraction/pymupdf_extractor.py`
   - `kps/extraction/segmenter.py`

2. **Create Test PDFs**:
   - Minimal test PDFs in `tests/fixtures/`
   - Document PDF requirements

3. **Run Tests**:
   ```bash
   pytest tests/ -v
   ```

4. **Fix Failures**:
   - Address critical tests first
   - Achieve 80% coverage

5. **CI/CD Integration**:
   - Add to GitHub Actions
   - Require critical tests to pass

---

## Definition of Done

Day 3 testing is complete when:

- [ ] All 85 tests pass
- [ ] All 8 critical tests pass (100% success rate)
- [ ] Test coverage ≥80% for extraction modules
- [ ] Test coverage ≥80% for translation modules
- [ ] Performance benchmarks met (< 30s extraction, < 60s translation)
- [ ] No regressions in Day 2 tests (anchoring, markers)
- [ ] Documentation updated with test results

---

## References

- **Master Plan**: `/docs/KPS_MASTER_PLAN.md`
- **Marker Injection**: `/MARKER_INJECTION_IMPLEMENTATION.md`
- **Anchoring Tests**: `/tests/README_ANCHORING.md`
- **Core Models**: `/kps/core/document.py`, `/kps/core/assets.py`
- **Placeholders**: `/kps/core/placeholders.py`

---

**Last Updated**: 2025-11-06
**Maintainer**: KPS v2.0 QA Team
