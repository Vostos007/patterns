# Marker Injection - KPS v2.0

## Overview

The marker injection system injects `[[asset_id]]` markers into ContentBlock text after assets have been anchored to blocks. These markers ensure assets stay with their associated text during translation and subsequent processing phases.

## Purpose

After the anchoring algorithm sets the `anchor_to` field for each asset, we need to inject marker references into the actual text content. This serves multiple purposes:

1. **Translation Preservation**: Markers are encoded as placeholders during translation, ensuring they survive the translation process
2. **Asset-Text Binding**: Creates explicit binding between text and visual assets
3. **InDesign Placement**: InDesign automation uses markers to position assets correctly in the translated document
4. **Version Control**: Markers make asset references visible and trackable in plain text

## Implementation

### Location

```
/Users/vostos/Dev/Hollywool patterns/dev/PDF_PARSER_2.0/kps/anchoring/markers.py
```

### Core Functions

#### `inject_markers(document: KPSDocument, ledger: AssetLedger) -> KPSDocument`

Main entry point for marker injection.

**Process:**
1. Group assets by `anchor_to` block ID
2. For each block with assets, inject markers
3. Validate completeness (every anchored asset has a marker)
4. Validate uniqueness (no duplicate markers)
5. Validate format (all markers match pattern)

**Returns:** Modified KPSDocument with markers injected

**Raises:** `MarkerInjectionError` if validation fails

#### `inject_markers_into_block(block: ContentBlock, assets: List[Asset]) -> ContentBlock`

Inject markers for multiple assets into a single block.

**Strategy:**
- Assets are sorted by y-coordinate (lower y0 = higher on page = first)
- Markers are placed at strategic positions based on block type
- Existing markers are detected and skipped (deduplication)

#### `find_injection_position(block: ContentBlock) -> int`

Determine character index for marker insertion based on block type.

**Returns:** Character index for insertion

#### `format_marker(asset_id: str) -> str`

Format an asset ID as a marker with newline.

**Example:** `format_marker("img-abc123-p0-occ1")` → `"[[img-abc123-p0-occ1]]\n"`

#### `validate_marker(marker: str) -> bool`

Validate that a marker matches the expected pattern.

**Pattern:** `[[asset_id]]` where asset_id contains only lowercase letters, numbers, hyphens, and underscores.

#### `extract_existing_markers(content: str) -> Set[str]`

Extract all existing `[[asset_id]]` markers from content.

**Returns:** Set of asset IDs (without brackets)

#### `count_markers(document: KPSDocument) -> dict`

Count markers in document for debugging and validation.

**Returns:** Dict with statistics:
- `total_markers`: Total number of markers
- `markers_by_block`: Dict of block_id → list of asset_ids
- `markers_by_section`: Dict of section_type → count

## Injection Strategies

### By Block Type

#### PARAGRAPH Blocks
```python
# Strategy: Inject at START of text (before first sentence)
# Position: index 0

# Before:
"You will need 200g of yarn."

# After:
"[[img-yarn-sample-p0-occ1]]
You will need 200g of yarn."
```

#### HEADING Blocks
```python
# Strategy: Inject AFTER heading text
# Position: len(content.rstrip()) + 1

# Before:
"Materials"

# After:
"Materials
[[vec-diagram-p1-occ1]]
"
```

#### TABLE Blocks
```python
# Strategy: Inject at START of table
# Position: index 0

# Before:
"Size | Chest | Length
S    | 90    | 60"

# After:
"[[tbl-snap-sizing-p3-occ1]]
Size | Chest | Length
S    | 90    | 60"
```

#### LIST Blocks
```python
# Strategy: Inject at START of list
# Position: index 0

# Before:
"- Yarn A
- Yarn B"

# After:
"[[img-yarn-types-p2-occ1]]
- Yarn A
- Yarn B"
```

#### FIGURE Blocks
```python
# Strategy: Marker replaces content
# Position: index 0

# Before:
""  # Empty or minimal content

# After:
"[[img-schematic-p4-occ1]]"
```

### Multiple Assets

When multiple assets are anchored to the same block:

1. **Sort by y-coordinate** (lower y0 = higher on page = first)
2. **Inject all markers** at the injection position
3. **Each marker on its own line**

```python
# Assets:
# - img-back-panel-p2-occ1 (y0=80)
# - img-front-panel-p2-occ1 (y0=150)

# Result:
"[[img-back-panel-p2-occ1]]
[[img-front-panel-p2-occ1]]
Follow the construction diagram."
```

## Marker Format

### Pattern

```regex
\[\[([a-z0-9\-_]+)\]\]
```

### Asset ID Format

```
{type}-{hash}-p{page}-occ{occurrence}
```

**Components:**
- `type`: Asset type prefix (img, vec, tbl-snap, tbl-live)
- `hash`: First 8-12 characters of SHA256 hash
- `page`: Zero-indexed page number
- `occurrence`: 1-indexed occurrence number (for duplicate content)

**Examples:**
- `[[img-abc123-p0-occ1]]` - Image on page 0, first occurrence
- `[[vec-xyz789-p1-occ2]]` - Vector on page 1, second occurrence
- `[[tbl-snap-def456-p5-occ1]]` - Table snapshot on page 5

### Newline Handling

Each marker MUST be on its own line:

```python
# Correct:
"[[img-abc-p0-occ1]]\nText content"

# Incorrect (inline):
"[[img-abc-p0-occ1]] Text content"
```

This ensures proper translation handling and InDesign parsing.

## Validation

### Completeness Check

Every anchored asset must have exactly one marker in the document.

```python
# Get all anchored assets
anchored_asset_ids = {asset.asset_id for asset in ledger.assets if asset.anchor_to}

# Get all markers in document
all_markers_in_document = set()
for section in document.sections:
    for block in section.blocks:
        all_markers_in_document.update(extract_existing_markers(block.content))

# Validate
missing = anchored_asset_ids - all_markers_in_document
if missing:
    raise MarkerInjectionError(f"Assets missing markers: {missing}")
```

### Uniqueness Check

No marker should appear in multiple blocks.

```python
# Track seen markers
all_markers = set()

for section in document.sections:
    for block in section.blocks:
        markers = extract_existing_markers(block.content)

        # Check for duplicates
        duplicates = all_markers.intersection(markers)
        if duplicates:
            raise MarkerInjectionError(f"Duplicate markers: {duplicates}")

        all_markers.update(markers)
```

### Format Validation

All markers must match the expected pattern.

```python
for section in document.sections:
    for block in section.blocks:
        for match in ASSET_MARKER_PATTERN.finditer(block.content):
            marker = match.group(0)
            if not validate_marker(marker):
                raise MarkerInjectionError(f"Invalid marker format: {marker}")
```

### Orphan Detection

No markers should exist without corresponding anchored assets.

```python
extra_markers = all_markers_in_document - anchored_asset_ids
if extra_markers:
    raise MarkerInjectionError(f"Unknown markers: {extra_markers}")
```

## Edge Cases

### Existing Markers

If a marker already exists in the content (from a previous run), it's not re-injected.

```python
existing_markers = extract_existing_markers(block.content)
assets_to_inject = [
    asset for asset in sorted_assets
    if asset.asset_id not in existing_markers
]
```

### Empty Content Blocks

Empty blocks receive only the marker(s).

```python
# Before: content=""
# After: content="[[img-xyz-p1-occ1]]"
```

### Figure Blocks

Figure blocks (which don't have text content) have their content replaced by the marker.

```python
if block.block_type == BlockType.FIGURE:
    block.content = marker_text.rstrip("\n")
```

### Unanchored Assets

Assets without `anchor_to` set are skipped during marker injection.

```python
for asset in ledger.assets:
    if not asset.anchor_to:
        continue  # Skip unanchored assets
```

## Integration with Translation

### Placeholder Encoding

During translation, markers are encoded as XML placeholders:

```python
# Before translation:
"[[img-abc123-p0-occ1]]\nВам понадобится 200г пряжи."

# Encoded for translation:
'<ph id="ASSET_IMG-ABC123-P0-OCC1" />\nВам понадобится 200г пряжи.'

# After translation:
'<ph id="ASSET_IMG-ABC123-P0-OCC1" />\nYou will need 200g of yarn.'

# Decoded:
"[[img-abc123-p0-occ1]]\nYou will need 200g of yarn."
```

See `kps/core/placeholders.py` for encoding/decoding implementation.

## Usage Example

```python
from kps.anchoring import inject_markers, count_markers
from kps.core.document import KPSDocument
from kps.core.assets import AssetLedger

# Load document and ledger (after anchoring phase)
document = KPSDocument.load_json("output/bonjour-gloves.kps.json")
ledger = AssetLedger.load_json("output/bonjour-gloves.assets.json")

# Inject markers
try:
    modified_document = inject_markers(document, ledger)

    # Get statistics
    stats = count_markers(modified_document)
    print(f"Total markers: {stats['total_markers']}")
    print(f"By section: {stats['markers_by_section']}")

    # Save modified document
    modified_document.save_json("output/bonjour-gloves.with-markers.kps.json")

except MarkerInjectionError as e:
    print(f"Marker injection failed: {e}")
```

## Testing

Comprehensive tests are available in:

```
/Users/vostos/Dev/Hollywool patterns/dev/PDF_PARSER_2.0/tests/test_marker_injection.py
```

**Test Coverage:**
- Marker formatting and validation
- Injection position logic for all block types
- Existing marker extraction
- Single and multiple asset injection
- Full document injection
- Validation error cases
- Marker counting utilities

## Demonstration

Run the demonstration script to see marker injection in action:

```bash
python3 examples/simple_marker_demo.py
```

This shows:
- Injection strategies for each block type
- Multiple asset ordering
- Validation features
- Edge case handling
- Complete examples

## Error Messages

### Assets Missing Markers

```
MarkerInjectionError: Assets missing markers: {'img-abc-p0-occ1', 'vec-xyz-p1-occ1'}
```

**Cause:** Some anchored assets don't have markers in the document.

**Solution:** Check that all anchored assets have valid `block_id` in `anchor_to` field.

### Duplicate Markers

```
MarkerInjectionError: Duplicate markers found: {'img-abc-p0-occ1'}
```

**Cause:** Same marker appears in multiple blocks.

**Solution:** Ensure each asset is anchored to only one block.

### Invalid Marker Format

```
MarkerInjectionError: Invalid marker format for asset img-ABC-p0-occ1: [[img-ABC-p0-occ1]]
```

**Cause:** Marker contains uppercase letters or invalid characters.

**Solution:** Ensure all asset IDs use lowercase letters, numbers, hyphens, and underscores only.

### Unknown Markers

```
MarkerInjectionError: Unknown markers found: {'img-orphan-p0-occ1'}
```

**Cause:** Marker exists in document but no anchored asset matches it.

**Solution:** Remove orphan markers or add corresponding assets to the ledger.

## Performance

### Complexity

- **Time:** O(n) where n = total number of blocks + assets
- **Space:** O(m) where m = total number of markers

### Optimization Tips

1. **Batch Processing**: Process all sections in a single pass
2. **Early Validation**: Validate markers during injection, not as separate pass
3. **Set Operations**: Use sets for fast marker lookup and deduplication

## Future Enhancements

### Planned Features

1. **Marker Comments**: Optional human-readable comments in markers
   ```python
   [[img-abc-p0-occ1 | Yarn close-up photo]]
   ```

2. **Conditional Markers**: Markers with metadata for conditional asset inclusion
   ```python
   [[img-abc-p0-occ1 | size=large, optional=true]]
   ```

3. **Marker Reordering**: Support for manual marker reordering via configuration

4. **Marker Templates**: Customizable marker format per project

## Related Documentation

- **Anchoring Algorithm**: See `docs/ANCHORING_ALGORITHM.md`
- **Placeholder Encoding**: See `kps/core/placeholders.py`
- **Translation Pipeline**: See `docs/TRANSLATION_PIPELINE.md`
- **Master Plan**: See `docs/KPS_MASTER_PLAN.md`

## Summary

The marker injection system is a critical component of KPS v2.0 that bridges the gap between asset extraction/anchoring and translation/DTP phases. By injecting explicit `[[asset_id]]` markers into text content, we ensure:

1. Assets survive translation with their text
2. InDesign can place assets correctly
3. Asset references are visible and version-controllable
4. The pipeline maintains data integrity through validation

The implementation is production-ready with comprehensive validation, edge case handling, and thorough testing.
