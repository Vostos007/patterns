# InDesign Placed Object Metadata Schema

**Version**: 1.0
**Status**: Current
**Last Updated**: 2025-11-06

## Overview

This document defines the complete metadata schema for InDesign placed objects in KPS v2.0. The metadata is serialized to compact JSON and embedded in InDesign objects using the `extractLabel` API, enabling full traceability from PDF extraction through InDesign placement.

## Design Goals

1. **Complete Traceability**: Every placed object can be traced back to its source PDF asset
2. **Validation**: Enable verification of placement accuracy and asset properties
3. **Compact Size**: JSON must be < 1KB for InDesign compatibility
4. **Version Resilient**: Schema versioning for future compatibility
5. **Bidirectional**: Support both embedding (Python → InDesign) and extraction (InDesign → Python)

## Schema Definition

### Schema Version 1.0

Current schema with full asset metadata and placement validation.

#### Required Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `asset_id` | string | Unique asset identifier | `"img-abc123def456-p0-occ1"` |
| `asset_type` | string | Asset type enum | `"image"`, `"vector_pdf"`, `"table_snap"` |
| `original_bbox` | array[4] | Original bbox [x0, y0, x1, y1] in PDF points | `[100.5, 200.3, 250.7, 400.9]` |
| `ctm` | array[6] | Current Transformation Matrix | `[1.0, 0.0, 0.0, 1.0, 0.0, 0.0]` |
| `page_number` | integer | 0-indexed page number | `0` |
| `occurrence` | integer | Occurrence number (1-indexed) | `1` |
| `anchor_to` | string | Block ID for anchoring | `"p.materials.001"` |
| `column_id` | integer | Column index (0-indexed) | `0` |
| `normalized_bbox` | object | Normalized bbox (0-1 coords) | See below |
| `sha256` | string | Content hash (64 hex chars) | `"a1b2c3d4..."` |
| `file_path` | string | Relative path to asset file | `"output/assets/img-abc123.png"` |
| `colorspace` | string | Color space | `"RGB"`, `"CMYK"`, `"GRAY"`, `"ICC"` |
| `schema_version` | string | Schema version | `"1.0"` |
| `created_at` | string | ISO 8601 timestamp | `"2025-11-06T10:30:00.000000"` |

#### Optional Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `has_smask` | boolean | Has transparency mask | `false` |
| `has_clip` | boolean | Has clipping path | `false` |
| `fonts` | array[string] | Font names (vectors only) | `["Helvetica", "Arial"]` |
| `icc_profile_name` | string | ICC profile name | `"sRGB IEC61966-2.1"` |
| `image_dimensions` | array[2] | Image size [width, height] pixels | `[1200, 800]` |
| `expected_bbox_placed` | array[4] | Expected InDesign bbox | `[100.0, 200.0, 300.0, 400.0]` |
| `actual_bbox_placed` | array[4] | Actual InDesign bbox | `[100.5, 200.2, 300.1, 400.3]` |

### Normalized BBox Object

Represents position in column-relative coordinates (0-1 range):

```json
{
  "x": 0.05,      // Left edge (0 = column left, 1 = column right)
  "y": 0.1667,    // Top edge (0 = column top, 1 = column bottom)
  "w": 0.5,       // Width (0 = zero width, 1 = full column width)
  "h": 0.3333     // Height (0 = zero height, 1 = full column height)
}
```

**Constraints**:
- All values must be in range [0, 1]
- `x + w <= 1.0` (doesn't extend beyond column right edge)
- `y + h <= 1.0` (doesn't extend beyond column bottom edge)

## Complete Example

### Minimal Image Asset

```json
{
  "asset_id": "img-abc123def456-p0-occ1",
  "asset_type": "image",
  "original_bbox": [100.5, 200.3, 250.7, 400.9],
  "ctm": [1.0, 0.0, 0.0, 1.0, 0.0, 0.0],
  "page_number": 0,
  "occurrence": 1,
  "anchor_to": "p.materials.001",
  "column_id": 0,
  "normalized_bbox": {
    "x": 0.05,
    "y": 0.1667,
    "w": 0.5,
    "h": 0.3333
  },
  "sha256": "a1b2c3d4e5f6789012345678901234567890123456789012345678901234abcd",
  "file_path": "output/assets/img-abc123def456-p0-occ1.png",
  "has_smask": false,
  "has_clip": false,
  "colorspace": "RGB",
  "image_dimensions": [1200, 800],
  "schema_version": "1.0",
  "created_at": "2025-11-06T10:30:00.000000"
}
```

### Vector Asset with Fonts

```json
{
  "asset_id": "vec-xyz789-p1-occ1",
  "asset_type": "vector_pdf",
  "original_bbox": [50.0, 100.0, 250.0, 300.0],
  "ctm": [1.5, 0.0, 0.0, 1.5, 10.0, 20.0],
  "page_number": 1,
  "occurrence": 1,
  "anchor_to": "p.techniques.005",
  "column_id": 1,
  "normalized_bbox": {
    "x": 0.1,
    "y": 0.2,
    "w": 0.6,
    "h": 0.4
  },
  "sha256": "9876543210fedcba9876543210fedcba9876543210fedcba9876543210fedcba",
  "file_path": "output/assets/vec-xyz789-p1-occ1.pdf",
  "has_smask": true,
  "has_clip": true,
  "fonts": ["Helvetica", "Arial"],
  "colorspace": "CMYK",
  "schema_version": "1.0",
  "created_at": "2025-11-06T10:31:00.000000"
}
```

### Asset with Placement Validation

```json
{
  "asset_id": "img-test123-p2-occ1",
  "asset_type": "image",
  "original_bbox": [150.0, 220.0, 350.0, 400.0],
  "ctm": [1.0, 0.0, 0.0, 1.0, 0.0, 0.0],
  "page_number": 2,
  "occurrence": 1,
  "anchor_to": "p.instructions.012",
  "column_id": 0,
  "normalized_bbox": {
    "x": 0.125,
    "y": 0.2,
    "w": 0.5,
    "h": 0.3
  },
  "sha256": "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
  "file_path": "output/assets/img-test123-p2-occ1.png",
  "colorspace": "RGB",
  "image_dimensions": [1200, 800],
  "expected_bbox_placed": [140.0, 220.0, 340.0, 400.0],
  "actual_bbox_placed": [140.2, 220.1, 340.3, 400.2],
  "schema_version": "1.0",
  "created_at": "2025-11-06T10:32:00.000000"
}
```

## Data Types

### BBox Array Format

BBox is represented as 4-element array: `[x0, y0, x1, y1]`

- `x0`: Left edge (in points)
- `y0`: Bottom edge (in points, PDF coordinate system)
- `x1`: Right edge (in points)
- `y1`: Top edge (in points)

**Constraints**:
- `x1 > x0` (positive width)
- `y1 > y0` (positive height)
- All values are finite (not NaN/Inf)

### CTM Array Format

Current Transformation Matrix: `[a, b, c, d, e, f]`

Transformation equation:
```
x' = a*x + c*y + e
y' = b*x + d*y + f
```

**Constraints**:
- Determinant `(a*d - b*c) != 0` (non-singular)
- Scale factors reasonable: 0.001 <= scale <= 100
- Translation values: |e|, |f| < 10000 pt
- All values finite (not NaN/Inf)

### Asset Type Values

| Value | Description | File Extension |
|-------|-------------|----------------|
| `"image"` | Raster image (JPEG, PNG) | `.png` |
| `"vector_pdf"` | Vector PDF fragment | `.pdf` |
| `"vector_png"` | Rasterized vector | `.png` |
| `"table_live"` | Extracted table structure | `.json` |
| `"table_snap"` | Table snapshot | `.pdf`, `.png` |

### Color Space Values

| Value | Description |
|-------|-------------|
| `"RGB"` | RGB color space |
| `"CMYK"` | CMYK color space |
| `"GRAY"` | Grayscale |
| `"ICC"` | ICC profile-based color |

## Validation Rules

### Required Field Validation

All required fields must be present and non-empty:

```python
required_fields = [
    "asset_id", "asset_type", "original_bbox", "ctm",
    "page_number", "occurrence", "anchor_to", "column_id",
    "normalized_bbox", "sha256", "file_path", "colorspace",
    "schema_version", "created_at"
]
```

### Coordinate Validation

**Normalized Coordinates**:
- All values in [0, 1] range
- No extension beyond column: `x + w <= 1.0`, `y + h <= 1.0`

**BBox Consistency**:
- Reconstructed bbox from normalized coords matches original
- Tolerance: ±2pt absolute OR ±1% relative

**Placement Accuracy**:
- `|expected - actual| <= 2.0 pt` for each coordinate
- Aspect ratio preserved within ±5%

### CTM Validation

- Length exactly 6 elements
- Non-singular: `|det| >= 1e-10`
- Reasonable scales: `0.001 <= scale <= 100`
- Finite values: no NaN or Inf

### String Validation

- `asset_id`: non-empty
- `sha256`: exactly 64 hex characters
- `file_path`: non-empty
- `anchor_to`: non-empty, format `"type.section.###"`
- `asset_type`: one of valid values
- `colorspace`: one of valid values

### Integer Validation

- `page_number >= 0`
- `occurrence >= 1`
- `column_id >= 0`
- `image_dimensions[0] > 0` and `[1] > 0` (if present)

## Size Optimization

### Target Size

- **Target**: < 1KB per metadata object
- **Typical**: 600-900 bytes
- **Maximum**: InDesign extractLabel limit (implementation dependent)

### Optimization Techniques

1. **Compact JSON**: No whitespace, short separators
2. **Optional Field Omission**: Empty optional fields not serialized
3. **Boolean Defaults**: `has_smask=false`, `has_clip=false` can be omitted
4. **Empty Array Omission**: Empty `fonts` array not serialized

### Size Examples

| Asset Type | Typical Size | Notes |
|------------|--------------|-------|
| Simple image | ~650 bytes | No fonts, no transparency |
| Vector with fonts | ~850 bytes | 2-3 font names |
| With placement data | ~950 bytes | Includes expected/actual bboxes |

## Usage Patterns

### Pattern 1: Creation from Asset

```python
from kps.indesign.metadata import PlacedObjectMetadata
from kps.core import Asset, NormalizedBBox

metadata = PlacedObjectMetadata.from_asset(
    asset=my_asset,
    column_id=0,
    normalized_bbox=NormalizedBBox(0.1, 0.2, 0.5, 0.3),
    anchor_to="p.materials.001"
)
```

### Pattern 2: Serialization for InDesign

```python
# Serialize for InDesign extractLabel
json_str = metadata.to_json()

# In ExtendScript (InDesign JSX):
# myPlacedItem.extractLabel = "kps_metadata:" + jsonStr;
```

### Pattern 3: Extraction from InDesign

```python
# After extracting from InDesign extractLabel
json_str = extract_label_value.replace("kps_metadata:", "")
metadata = PlacedObjectMetadata.from_json(json_str)
```

### Pattern 4: Validation

```python
# Validate metadata integrity
errors = metadata.validate()
if errors:
    for error in errors:
        print(f"ERROR: {error}")
else:
    print("Metadata is valid")
```

### Pattern 5: Placement Verification

```python
# After InDesign placement
actual_bbox = extract_geometric_bounds_from_indesign()
metadata.update_actual_bbox(actual_bbox)

# Calculate placement error
error_pt = metadata.placement_error()
if error_pt and error_pt > 2.0:
    print(f"WARNING: Placement error {error_pt:.2f} pt")
```

### Pattern 6: Batch Operations

```python
from kps.indesign.serialization import serialize_batch, deserialize_batch

# Save multiple metadata objects
serialize_batch(metadata_list, Path("placement_manifest.json"))

# Load back
metadata_list = deserialize_batch(Path("placement_manifest.json"))
```

## Schema Evolution

### Version History

- **1.0** (Current): Initial schema with full asset metadata

### Future Considerations

**Version 1.1** (Proposed):
- Add `rotation_angle` field for rotated placements
- Add `effects` array for InDesign effects (shadow, glow, etc.)
- Add `layer_name` for layer assignment
- Add `dpi_effective` calculated DPI at placement size

**Version 2.0** (Future):
- Multi-asset groups (linked assets)
- Asset dependencies (asset A requires asset B)
- Conditional placement rules
- Interactive element metadata

### Migration Strategy

When adding new schema versions:

1. Update `METADATA_SCHEMA_VERSIONS` dict in `serialization.py`
2. Implement migration function: `_migrate_X_Y_to_X_Z()`
3. Add migration to chain in `_build_migration_chain()`
4. Update this documentation
5. Add tests for migration in `test_indesign_metadata.py`

## Error Handling

### Deserialization Errors

| Error Type | Cause | Handling |
|------------|-------|----------|
| `ValueError: Invalid JSON` | Malformed JSON | Log error, skip object |
| `KeyError: 'field_name'` | Missing required field | Log error, skip object |
| `ValueError: sha256 must be 64 hex characters` | Invalid SHA256 | Log error, reject metadata |
| Schema version mismatch | Old version | Attempt migration, fallback to skip |

### Validation Errors

Validation returns list of error messages:
- Empty list = valid
- Non-empty list = specific errors

Handle validation errors by:
1. Log all errors for debugging
2. Reject metadata if critical errors (invalid coordinates, singular CTM)
3. Warn on non-critical errors (low DPI, aspect ratio deviation)

## Best Practices

### DO:
- ✓ Validate metadata before serialization
- ✓ Check JSON size before embedding in InDesign
- ✓ Include `expected_bbox_placed` for verification
- ✓ Use `verify_roundtrip()` during development
- ✓ Log all validation errors
- ✓ Include schema version in all metadata

### DON'T:
- ✗ Skip validation to save time
- ✗ Embed >1KB JSON in InDesign (may fail)
- ✗ Modify metadata after validation
- ✗ Use relative file paths (use full paths or repo-relative)
- ✗ Forget to update `created_at` timestamp
- ✗ Assume schema version compatibility without checking

## Testing Requirements

### Unit Tests

See `tests/test_indesign_metadata.py` for complete test suite:

- ✓ Metadata creation from Asset objects
- ✓ JSON serialization/deserialization roundtrip
- ✓ Schema validation (all fields)
- ✓ Coordinate validation (0-1 range)
- ✓ CTM validation (non-singular, reasonable values)
- ✓ BBox consistency checking
- ✓ Placement accuracy verification
- ✓ Batch operations
- ✓ Error handling for invalid data

### Integration Tests

- ✓ Complete workflow: Asset → Metadata → JSON → InDesign → Extraction → Validation
- ✓ Multi-asset batch processing
- ✓ Schema version migration (when implemented)

### Coverage Target

- **Critical paths**: 100% coverage
- **Overall**: >95% coverage

## Appendix A: Field Reference

Complete alphabetical field reference:

| Field | Required | Type | Range/Format | Example |
|-------|----------|------|--------------|---------|
| `actual_bbox_placed` | No | array[4] | [x0, y0, x1, y1] | `[100.5, 200.2, 300.1, 400.3]` |
| `anchor_to` | Yes | string | Block ID | `"p.materials.001"` |
| `asset_id` | Yes | string | Asset identifier | `"img-abc123-p0-occ1"` |
| `asset_type` | Yes | string | Enum | `"image"` |
| `colorspace` | Yes | string | Enum | `"RGB"` |
| `column_id` | Yes | integer | >= 0 | `0` |
| `created_at` | Yes | string | ISO 8601 | `"2025-11-06T10:30:00.000000"` |
| `ctm` | Yes | array[6] | [a,b,c,d,e,f] | `[1.0, 0.0, 0.0, 1.0, 0.0, 0.0]` |
| `expected_bbox_placed` | No | array[4] | [x0, y0, x1, y1] | `[140.0, 220.0, 340.0, 400.0]` |
| `file_path` | Yes | string | Relative path | `"output/assets/img-123.png"` |
| `fonts` | No | array[string] | Font names | `["Helvetica", "Arial"]` |
| `has_clip` | No | boolean | true/false | `false` |
| `has_smask` | No | boolean | true/false | `false` |
| `icc_profile_name` | No | string | Profile name | `"sRGB IEC61966-2.1"` |
| `image_dimensions` | No | array[2] | [width, height] | `[1200, 800]` |
| `normalized_bbox` | Yes | object | See schema | `{"x": 0.1, "y": 0.2, "w": 0.5, "h": 0.3}` |
| `occurrence` | Yes | integer | >= 1 | `1` |
| `original_bbox` | Yes | array[4] | [x0, y0, x1, y1] | `[100.5, 200.3, 250.7, 400.9]` |
| `page_number` | Yes | integer | >= 0 | `0` |
| `schema_version` | Yes | string | Version | `"1.0"` |
| `sha256` | Yes | string | 64 hex chars | `"a1b2c3d4..."` |

## Appendix B: Validation Tolerance Values

| Validation | Tolerance | Rationale |
|------------|-----------|-----------|
| Placement position | ±2.0 pt | InDesign rounding precision |
| BBox consistency | ±2.0 pt or ±1% | Floating point accumulation |
| Aspect ratio | ±5% | Acceptable distortion threshold |
| CTM determinant | >= 1e-10 | Numerical precision limit |
| CTM scale | 0.001 - 100 | Reasonable scaling range |
| DPI minimum | 200 DPI | Print quality threshold |
| DPI maximum | 600 DPI | Diminishing returns above this |

## Appendix C: Size Calculation

JSON size depends on:

1. **Fixed overhead**: ~400 bytes (schema, IDs, timestamps)
2. **Asset properties**: ~100 bytes (colorspace, dimensions, flags)
3. **Coordinates**: ~200 bytes (original_bbox, normalized_bbox, CTM)
4. **Optional fields**:
   - Fonts: ~15 bytes per font name
   - Placement bboxes: ~80 bytes for both
   - ICC profile name: ~30 bytes

**Formula**:
```
Size ≈ 400 + 100 + 200 + (15 × num_fonts) + optional_fields
```

**Example**:
- Simple image: 400 + 100 + 200 = 700 bytes
- Vector with 3 fonts: 700 + 45 = 745 bytes
- With placement validation: 745 + 80 = 825 bytes

---

**Document Version**: 1.0
**Maintained By**: KPS Development Team
**Contact**: See project README for contact information
