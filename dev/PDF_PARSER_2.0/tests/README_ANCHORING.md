# Anchoring System Test Strategy

**KPS v2.0 - Day 2 Implementation Test Suite**

This document describes the comprehensive test strategy for the KPS v2.0 anchoring system, which is critical for achieving the ≥98% geometry preservation requirement.

## Table of Contents

1. [Overview](#overview)
2. [Test Architecture](#test-architecture)
3. [Test Coverage](#test-coverage)
4. [Running Tests](#running-tests)
5. [Test Data Fixtures](#test-data-fixtures)
6. [Validation Requirements](#validation-requirements)
7. [Troubleshooting](#troubleshooting)

---

## Overview

### Purpose

The anchoring system tests validate three critical components:

1. **Column Detection** (`kps/anchoring/columns.py`)
   - Identifies vertical column regions in multi-column layouts
   - Uses DBSCAN clustering (epsilon=30pt, min_points=3)
   - Handles 1-3 column layouts

2. **Asset Anchoring** (`kps/anchoring/anchor.py`)
   - Assigns each asset to a content block
   - Respects column boundaries (same-column constraint)
   - Uses vertical overlap and distance metrics

3. **Marker Injection** (`kps/anchoring/markers.py`)
   - Inserts `[[asset_id]]` markers into content blocks
   - Maintains reading order for multiple assets per block
   - Preserves existing content and formatting

### Quality Requirements

From `KPS_MASTER_PLAN.md`:

- **100% Completeness**: Every asset must be anchored and marked
- **≥98% Geometry**: Positioning within ±2pt or 1% tolerance
- **Fail-Closed**: Any validation failure stops the build
- **Round-Trip**: Inject → extract → verify workflow must succeed

---

## Test Architecture

### Test Organization

```
tests/
├── conftest.py                          # Shared fixtures
├── test_column_detection.py             # Unit tests for column detection
├── test_asset_anchoring.py              # Unit tests for asset anchoring
├── test_marker_injection.py             # Unit tests for marker injection
└── integration/
    └── test_anchoring_pipeline.py       # Integration tests for full pipeline
```

### Test Levels

#### Unit Tests

- **Scope**: Individual functions and classes
- **Isolation**: Mocked dependencies
- **Speed**: Fast (< 1s per test)
- **Purpose**: Validate algorithm correctness

#### Integration Tests

- **Scope**: Complete anchoring pipeline
- **Isolation**: Real components, mock I/O
- **Speed**: Medium (1-5s per test)
- **Purpose**: Validate component interaction

#### E2E Tests (Future)

- **Scope**: Full PDF processing workflow
- **Isolation**: Real files and InDesign
- **Speed**: Slow (> 10s per test)
- **Purpose**: Validate production readiness

---

## Test Coverage

### Column Detection Tests

**File**: `tests/test_column_detection.py`

#### Test Cases

1. **Single Column Layout**
   - `test_single_column_layout_detection`
   - Validates: 1 column detected, all blocks assigned

2. **Two Column Layout with 30pt Gap**
   - `test_two_column_layout_with_30pt_gap`
   - Validates: 2 columns, correct gap detection, block assignment

3. **Three Column Layout**
   - `test_three_column_layout_detection`
   - Validates: 3 columns, independent boundaries

4. **Edge Cases**
   - `test_blocks_spanning_columns`: Blocks that cross column boundaries
   - `test_empty_blocks_list`: Empty input handling
   - `test_blocks_without_bbox`: Blocks missing position data

5. **DBSCAN Parameters**
   - `test_dbscan_parameters`: Verify epsilon=30, min_points=3
   - `test_column_bounds_calculation`: Accurate boundary calculation

6. **Validation**
   - `test_all_blocks_assigned_to_column`: 100% assignment coverage
   - `test_reading_order_preserved_within_column`: Order maintained

#### Coverage Target

- **Line Coverage**: 90%+
- **Branch Coverage**: 85%+
- **Edge Cases**: All identified cases covered

---

### Asset Anchoring Tests

**File**: `tests/test_asset_anchoring.py`

#### Test Cases

1. **Basic Anchoring**
   - `test_basic_anchoring_asset_above_block`: Asset above target block
   - `test_anchoring_asset_below_block`: Fallback when no block above

2. **Column Awareness**
   - `test_same_column_constraint`: Never cross column boundaries
   - `test_asset_at_column_boundary`: Handle edge cases

3. **Distance Metrics**
   - `test_nearest_block_selection`: Minimize vertical distance
   - `test_vertical_overlap_detection`: Prefer overlapping blocks

4. **Geometry Preservation**
   - `test_normalized_coordinate_calculation`: Convert to 0-1 scale
   - `test_geometry_preservation_tolerance`: ±2pt or 1% validation

5. **Block Type Handling**
   - `test_anchor_to_different_block_types`: PARAGRAPH, HEADING, TABLE

6. **Edge Cases**
   - `test_no_blocks_in_same_column`: Orphaned assets
   - `test_multiple_assets_to_same_block`: Multiple anchors per block

7. **Validation**
   - `test_all_assets_have_anchor_to_set`: 100% coverage requirement

#### Coverage Target

- **Line Coverage**: 90%+
- **Branch Coverage**: 85%+
- **Critical Paths**: 100% (anchoring algorithm)

---

### Marker Injection Tests

**File**: `tests/test_marker_injection.py`

**Note**: These tests already exist and are comprehensive.

#### Test Cases

1. **Block Type Injection**
   - PARAGRAPH blocks: Inject at start
   - HEADING blocks: Inject after heading
   - TABLE blocks: Inject at start
   - LIST blocks: Inject at start

2. **Multiple Assets**
   - Order by y-coordinate (top to bottom)
   - Deduplication: prevent duplicate markers

3. **Marker Format**
   - Validation: `[[type-hash-p{page}-occ{n}]]`
   - Pattern matching tests

4. **Edge Cases**
   - Empty content blocks
   - Special characters (Russian, French, symbols)
   - Existing markers (round-trip)

5. **Validation**
   - Count matches: marker count == asset count
   - Coverage: all assets have markers

#### Coverage Target

- **Line Coverage**: 95%+
- **Branch Coverage**: 90%+
- **Format Validation**: 100%

---

### Integration Pipeline Tests

**File**: `tests/integration/test_anchoring_pipeline.py`

#### Test Cases

1. **Full Pipeline**
   - `test_full_pipeline_two_column_layout`: Complete workflow
   - `test_pipeline_with_realistic_multicolumn_data`: Realistic scenario

2. **Validation**
   - `test_validation_100_percent_asset_coverage`: All assets marked
   - `test_geometry_preservation_98_percent_tolerance`: Geometry check

3. **Round-Trip**
   - `test_round_trip_inject_extract_verify`: Serialize → deserialize

4. **Error Handling**
   - `test_pipeline_error_handling_no_blocks`: Empty document
   - `test_pipeline_error_handling_assets_without_anchors`: Invalid anchors

5. **Performance**
   - `test_pipeline_performance_large_document`: 100 blocks, 50 assets

#### Coverage Target

- **Integration Paths**: 100% of critical workflows
- **Error Paths**: All identified failure modes
- **Performance**: Baseline established

---

## Running Tests

### Run All Tests

```bash
cd /Users/vostos/Dev/Hollywool\ patterns/dev/PDF_PARSER_2.0
pytest tests/ -v
```

### Run Specific Test Suites

```bash
# Column detection only
pytest tests/test_column_detection.py -v

# Asset anchoring only
pytest tests/test_asset_anchoring.py -v

# Marker injection only
pytest tests/test_marker_injection.py -v

# Integration tests only
pytest tests/integration/test_anchoring_pipeline.py -v
```

### Run with Coverage

```bash
pytest tests/ --cov=kps.anchoring --cov-report=html --cov-report=term
```

Coverage report will be in `htmlcov/index.html`.

### Run Specific Test

```bash
pytest tests/test_column_detection.py::TestColumnDetection::test_two_column_layout_with_30pt_gap -v
```

### Run Tests Matching Pattern

```bash
pytest tests/ -k "column" -v       # All tests with "column" in name
pytest tests/ -k "geometry" -v     # All geometry-related tests
```

---

## Test Data Fixtures

### Provided in `tests/conftest.py`

#### Bounding Boxes

- `sample_bbox`: Generic bbox (100, 200, 300, 400)
- `sample_column_bounds`: Column boundaries (50, 100, 250, 700)

#### Content Blocks

- `single_column_layout_blocks`: 3 blocks in single column
- `two_column_layout_blocks`: 6 blocks across 2 columns (30pt gap)
- `three_column_layout_blocks`: 3 blocks across 3 columns

#### Assets

- `sample_asset_left_column`: Image in left column
- `sample_asset_right_column`: Image in right column
- `sample_asset_between_blocks`: Image between two blocks
- `sample_asset_column_boundary`: Image at column gap (edge case)

#### Documents

- `sample_kps_document`: Complete KPSDocument with sections
- `sample_asset_ledger`: AssetLedger with 2 assets

#### Utilities

- `temp_output_dir`: Temporary directory for test output
- `dbscan_params`: DBSCAN configuration (epsilon=30, min_points=3)
- `marker_pattern`: Asset marker regex pattern

### Creating Custom Fixtures

```python
@pytest.fixture
def custom_layout() -> list[ContentBlock]:
    """Custom layout for specific test scenario."""
    return [
        ContentBlock(
            block_id="p.custom.001",
            block_type=BlockType.PARAGRAPH,
            content="Custom content",
            bbox=BBox(50, 100, 250, 150),
            page_number=0,
            reading_order=0,
        ),
        # Add more blocks...
    ]
```

---

## Validation Requirements

### Test Pass Criteria

#### Column Detection

- ✅ Detect correct number of columns (1-3)
- ✅ All blocks assigned to exactly one column
- ✅ Column boundaries calculated correctly
- ✅ Reading order preserved within columns
- ✅ DBSCAN parameters match spec (epsilon=30, min_points=3)

#### Asset Anchoring

- ✅ 100% of assets anchored to valid blocks
- ✅ Same-column constraint enforced
- ✅ Nearest-block selection correct
- ✅ Normalized coordinates calculated accurately
- ✅ Geometry tolerance: ±2pt or 1%

#### Marker Injection

- ✅ All anchored assets have markers
- ✅ Marker format valid: `[[type-hash-p{page}-occ{n}]]`
- ✅ Marker count matches asset count
- ✅ No duplicate markers
- ✅ Content preservation (no data loss)

#### Integration Pipeline

- ✅ Full workflow completes without errors
- ✅ 100% asset coverage achieved
- ✅ ≥98% geometry preservation (in final QA)
- ✅ Round-trip validation passes
- ✅ Performance: < 5s for 100 blocks + 50 assets

---

## Troubleshooting

### Common Test Failures

#### ImportError: No module named 'kps.anchoring.anchor'

**Cause**: The `anchor.py` module is not implemented yet.

**Solution**:
- Comment out `test_asset_anchoring.py` tests temporarily
- OR implement `kps/anchoring/anchor.py` based on the test specifications

#### AssertionError: Expected 2 columns, found 1

**Cause**: DBSCAN parameters may not match the test data.

**Solution**:
- Check block x-coordinates in test fixtures
- Verify column gap is > epsilon (30pt)
- Adjust epsilon if needed (document reason)

#### Marker format validation fails

**Cause**: Marker pattern doesn't match expected format.

**Solution**:
- Check `ASSET_MARKER_PATTERN` in conftest.py
- Verify marker format: `[[{type}-{hash}-p{page}-occ{n}]]`
- Ensure lowercase, 8-char hash prefix

#### Integration test timeout

**Cause**: Performance issue or infinite loop.

**Solution**:
- Profile the code with `pytest --durations=10`
- Check for inefficient algorithms (O(n²))
- Add performance logging

### Debugging Tests

#### Verbose Output

```bash
pytest tests/ -v -s          # -s shows print statements
```

#### Debug with pdb

```bash
pytest tests/ --pdb           # Drop into debugger on failure
```

#### Run Single Test with Debug

```python
# In test file
import pdb; pdb.set_trace()  # Add breakpoint
```

#### View Fixture Values

```bash
pytest tests/ -v --fixtures  # List all available fixtures
```

---

## Test Maintenance

### Adding New Tests

1. **Identify test scenario** from requirements or bug reports
2. **Create fixture** if new test data needed (in `conftest.py`)
3. **Write test** following naming convention: `test_{feature}_{scenario}`
4. **Add docstring** explaining what is validated
5. **Run test** and verify it passes
6. **Update this README** with new test case

### Test Naming Convention

```python
def test_{component}_{scenario}_{expected_behavior}():
    """
    Test {component} {scenario}.

    Expected behavior:
    - {Expectation 1}
    - {Expectation 2}
    """
```

**Examples**:
- `test_column_detection_two_column_layout_detects_two_columns`
- `test_asset_anchoring_same_column_constraint_never_crosses_boundary`
- `test_marker_injection_multiple_assets_orders_by_position`

---

## References

- **Master Plan**: `docs/KPS_MASTER_PLAN.md`
- **Column Detection Spec**: Section "Column Detection" (Enhancement #4)
- **Anchoring Algorithm**: Section "Anchoring Algorithm"
- **Geometry Validation**: Section "Geometry Check" (Enhancement #9)

---

**Document Version**: 1.0.0
**Last Updated**: 2025-11-06
**Status**: Ready for Implementation Testing
