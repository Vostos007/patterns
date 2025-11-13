# Table Column Alignment Fix - Research & Plan

## Problem Statement

**Issue**: Table headers in translated PDFs are bunched together instead of being aligned in proper columns.

**Evidence from CSR Report PDF**:
- Original English PDF: Table headers properly aligned in 4 distinct columns
  - "Available beginning" @ X=102.1
  - "Available ending" @ X=232.1  
  - "Withheld beginning" @ X=331.6
  - "Withheld ending" @ X=478.3

- Translated Russian PDF: Headers bunched together (not aligned)
  - All text appears to flow continuously without column positioning

**Root Cause**: Current implementation treats table text as continuous strings, losing column structure and X-coordinate positioning.

## Current Implementation Analysis

### 1. How Tables Are Currently Processed

**In `layout_preserver.py` - `rebuild_page()` function**:

```python
# Line 747-749: Extract text blocks from original page
page_dict = orig_page.get_text("dict", sort=True)
text_blocks = [block for block in page_dict.get("blocks", []) if block.get("type") == 0]
```

**Two modes of text insertion**:

#### A. Formatting Preservation Mode (`preserve_formatting=True`):
- Uses `insert_formatted_block()` (line 777-783)
- Calls `insert_text()` with X,Y positioning
- **Issue**: Joins horizontal text fragments with spaces (line 362 in `block_text()`)
- **Result**: Table columns get merged into continuous text

#### B. Simple Mode (`preserve_formatting=False`):
- Uses `insert_textbox_smart()` (line 811-818)
- Inserts text into entire block bbox
- **Issue**: Text flows within rect without column awareness
- **Result**: Table structure is lost

### 2. PyMuPDF Table Structure Discovery

**Analysis of CSR PDF reveals**:

```
Block 2: Table Header (4 lines, same Y=202.2)
  Line 0: X=102.1 "Available beginning"
  Line 1: X=232.1 "Available ending"
  Line 2: X=331.6 "Withheld beginning"
  Line 3: X=478.3 "Withheld ending"

Block 3: Table Row 1 (5 lines, same Y=219.8)
  Line 0: X=45.0  "EUR"
  Line 1: X=168.8 "12.18"
  Line 2: X=289.9 "0.00"
  Line 3: X=401.1 "0.00"
  Line 4: X=534.4 "0.00"
```

**Key Insight**: PyMuPDF extracts table cells as separate "lines" with the SAME Y-coordinate but different X-origins.

### 3. Docling Table Structure

**From JSON analysis** (`csr-report-jan-1-2025-to-jul-30-2025-1---page1_v013.json`):

```json
{
  "table_cells": [
    {
      "bbox": {"l": 102.07, "t": 203.01, "r": 188.76, "b": 212.00},
      "start_col_offset_idx": 1,
      "end_col_offset_idx": 2,
      "text": "Available beginning",
      "column_header": true
    },
    {
      "bbox": {"l": 232.12, "t": 203.01, "r": 305.47, "b": 212.00},
      "start_col_offset_idx": 2,
      "end_col_offset_idx": 3,
      "text": "Available ending",
      "column_header": true
    }
    // ... more cells
  ]
}
```

**Docling provides**:
- Cell-level bounding boxes with exact X,Y coordinates
- Column indices (`start_col_offset_idx`, `end_col_offset_idx`)
- Row/column spanning information
- Header/data cell classification

## Root Cause Deep Dive

### Problem in `block_text()` function (line 336-371)

```python
# Line 355-362: Groups lines by Y-coordinate
if prev_y is not None and abs(y_mid - prev_y) < 2.0:  # Same row
    current_row.append(line_text)
else:
    if current_row:
        text_lines.append("  ".join(current_row))  # ⚠️ JOINS WITH SPACES!
```

**What happens**:
1. Table headers (Y=202.2): "Available beginning", "Available ending", etc.
2. Detected as same horizontal row (correct!)
3. Joined with spaces: "Available beginning  Available ending  Withheld beginning  Withheld ending"
4. Loses original X-coordinates (102.1, 232.1, 331.6, 478.3)

### Problem in `insert_formatted_block()` (line 530-605)

```python
# Line 572-573: Starts at line's left edge
current_x = line_bbox[0]
baseline_y = line_bbox[3] - 2.0

# Line 600-602: Updates X position after each span
text_width = font.text_length(text_part, fontsize=fontsize)
current_x += text_width
```

**Issue**: 
- Uses continuous X positioning (current_x += width)
- Doesn't respect original span X-coordinates
- Table cells flow like paragraph text instead of jumping to column positions

## Available Data Sources

### Option 1: PyMuPDF Span Origins
**Access**: `span.get("origin")` - (X, Y) tuple for text baseline start
**Pros**: Already extracted, no additional API calls
**Cons**: Working with already-extracted text blocks

### Option 2: Docling Table Cell Metadata
**Access**: Via `DoclingExtractor.last_block_map` and table item data
**Pros**: 
- Semantic understanding of tables
- Column indices for proper alignment
- Cell bbox with exact positions
**Cons**: Requires linking Docling blocks to PyMuPDF blocks

### Option 3: PyMuPDF Table Detection
**Access**: `page.find_tables()` - built-in table detection
**Pros**: Purpose-built for tables
**Cons**: May not detect all table formats, requires integration

## Proposed Solutions

### Solution 1: Fix `insert_formatted_block()` - Use Original Span X-Coordinates

**Changes**:
1. Modify `insert_formatted_block()` to use `orig_span["origin"][0]` instead of `current_x`
2. Stop accumulating X positions (remove `current_x += text_width`)
3. Use exact X-coordinates from original PDF

**Implementation**:
```python
def insert_formatted_block(...):
    for span_idx, (text_part, orig_span) in enumerate(zip(text_parts, original_spans)):
        # Use EXACT original X-coordinate
        original_x = orig_span["origin"][0]  # ✅ Preserve column position
        baseline_y = line_bbox[3] - 2.0
        
        page.insert_text(
            (original_x, baseline_y),  # ✅ Use original position
            text_part,
            fontname=font_alias,
            fontsize=fontsize,
            color=color,
            overlay=True
        )
        # ❌ DON'T update current_x - let each span use its own position
```

**Pros**:
- Simple fix (10-15 lines)
- Works with existing formatting preservation
- Uses data already extracted

**Cons**:
- Assumes translated text fits in original column width
- May overflow if translation is much longer

### Solution 2: Detect Table Blocks and Use Special Handling

**Changes**:
1. Detect table blocks (multiple lines with same Y)
2. Create specialized `insert_table_block()` function
3. Calculate column positions from original spans
4. Insert translated text at column X-coordinates

**Implementation**:
```python
def is_table_block(block: dict) -> bool:
    """Detect if block is a table (multiple lines with same Y)."""
    lines = block.get("lines", [])
    if len(lines) < 2:
        return False
    
    # Check if multiple lines share the same Y-coordinate
    y_coords = [line["bbox"][1] for line in lines]
    unique_y = set(round(y, 1) for y in y_coords)
    return len(unique_y) < len(lines) * 0.5  # At least 50% share Y

def insert_table_block(page, block, translated_cells, font_map, target_lang):
    """Insert table with preserved column alignment."""
    lines = block.get("lines", [])
    
    # Group lines by Y-coordinate (rows)
    rows = {}
    for line in lines:
        y = round(line["bbox"][1], 1)
        if y not in rows:
            rows[y] = []
        rows[y].append(line)
    
    # For each row, insert cells at original X positions
    for y, row_lines in sorted(rows.items()):
        for line in row_lines:
            for span in line["spans"]:
                original_x = span["origin"][0]
                baseline_y = line["bbox"][3] - 2.0
                
                # Get translated text for this cell
                # (requires mapping original to translation)
                
                page.insert_text(
                    (original_x, baseline_y),
                    translated_cell_text,
                    ...
                )
```

**Pros**:
- Explicit table handling
- Can add column width calculation
- Clear separation of concerns

**Cons**:
- More complex (50+ lines)
- Requires translation mapping to cells
- May need column width detection

### Solution 3: Integrate Docling Table Metadata

**Changes**:
1. Extract table blocks from Docling's `table_cells`
2. Use `start_col_offset_idx` to determine column positions
3. Calculate column X-coordinates from cell bboxes
4. Insert translated text at column-aligned positions

**Implementation**:
```python
def extract_table_columns(docling_table_item) -> List[float]:
    """Extract column X-positions from Docling table cells."""
    cells = docling_table_item.get("data", {}).get("table_cells", [])
    
    # Group cells by column index
    columns = {}
    for cell in cells:
        col_idx = cell["start_col_offset_idx"]
        if col_idx not in columns:
            columns[col_idx] = []
        columns[col_idx].append(cell["bbox"]["l"])  # Left edge
    
    # Get median X position for each column
    col_positions = {}
    for col_idx, x_coords in columns.items():
        col_positions[col_idx] = sorted(x_coords)[len(x_coords) // 2]
    
    return col_positions

def insert_table_with_docling_metadata(page, docling_table, translations, ...):
    """Use Docling's semantic table structure for precise positioning."""
    col_positions = extract_table_columns(docling_table)
    cells = docling_table.get("data", {}).get("table_cells", [])
    
    for cell in cells:
        col_idx = cell["start_col_offset_idx"]
        x = col_positions[col_idx]
        y = cell["bbox"]["t"] + (cell["bbox"]["b"] - cell["bbox"]["t"]) * 0.8
        
        # Get translated text for this cell
        original_text = cell["text"]
        translated_text = get_translation(original_text, translations)
        
        page.insert_text((x, y), translated_text, ...)
```

**Pros**:
- Uses semantic understanding
- Most accurate column detection
- Can handle complex tables (merged cells, etc.)

**Cons**:
- Requires linking KPS blocks to Docling items
- More complex integration (100+ lines)
- Dependency on Docling structure

## Recommended Approach

### **SOLUTION 1: Fix `insert_formatted_block()` with Original X-Coordinates**

**Rationale**:
1. **Minimal change**: ~15 lines of code modification
2. **Fixes root cause**: Preserves original X-coordinates
3. **Works immediately**: Uses existing extraction pipeline
4. **Side benefits**: Improves ALL multi-column layouts (not just tables)

**Implementation Steps**:

1. **Modify `insert_formatted_block()` (line 530-605)**:
   ```python
   # CHANGE: Use original X-coordinate instead of accumulated position
   for span_idx, (text_part, orig_span) in enumerate(zip(text_parts, original_spans)):
       if not text_part.strip():
           continue
       
       # ✅ USE ORIGINAL X-COORDINATE
       original_x = orig_span["origin"][0]
       baseline_y = line_bbox[3] - 2.0
       
       # Get appropriate font variant
       is_bold = orig_span["is_bold"]
       is_italic = orig_span["is_italic"]
       font_alias, font = font_map.get((is_bold, is_italic), font_map[(False, False)])
       
       fontsize = orig_span["size"]
       color = orig_span["color"]
       
       # ✅ INSERT AT ORIGINAL POSITION
       page.insert_text(
           (original_x, baseline_y),  # Use original X!
           text_part,
           fontname=font_alias,
           fontsize=fontsize,
           color=color,
           overlay=True
       )
       
       # ❌ REMOVE: current_x += text_width
       # Let each span use its own original position
   ```

2. **Handle translation overflow** (if text is too long):
   ```python
   # Optional: Scale down fontsize if translation is wider than column
   text_width = font.text_length(text_part, fontsize=fontsize)
   available_width = orig_span["bbox"][2] - orig_span["bbox"][0]
   
   if text_width > available_width:
       fontsize *= (available_width / text_width) * 0.95  # 5% margin
   ```

3. **Add logging** to verify column preservation:
   ```python
   logger.debug(
       f"    Span {span_idx}: X={original_x:.1f} "
       f"(orig: {orig_span['origin'][0]:.1f}), "
       f"text='{text_part[:20]}'"
   )
   ```

**Testing Plan**:
1. Run on CSR PDF: `runtime/input/CSR Report Jan 1 2025 to Jul 30 2025 (1) - page1.pdf`
2. Verify table headers are aligned in 4 columns
3. Check that table data rows maintain column structure
4. Test with multi-column layouts (non-tables)

**Success Criteria**:
- [ ] "Available beginning" at X ≈ 102
- [ ] "Available ending" at X ≈ 232
- [ ] "Withheld beginning" at X ≈ 332
- [ ] "Withheld ending" at X ≈ 478
- [ ] EUR row values aligned under headers
- [ ] USD row values aligned under headers

## Future Enhancements

If Solution 1 doesn't handle all cases:

1. **Add table detection** (Solution 2 elements):
   - Detect table blocks via Y-coordinate clustering
   - Special handling for tables vs paragraphs

2. **Column width awareness**:
   - Calculate column boundaries from original spans
   - Truncate/wrap text that exceeds column width

3. **Integrate Docling metadata** (Solution 3):
   - Use `table_cells` for semantic understanding
   - Handle merged cells and complex layouts

## Files to Modify

1. **`kps/layout_preserver.py`**:
   - `insert_formatted_block()` (line 530-605)
   - Optional: Add `insert_table_block()` for future enhancement

2. **Tests to add/update**:
   - `tests/integration/test_csr_table_regression.py` - verify column alignment
   - Add visual verification test (compare X-coordinates)

## Risk Assessment

**Low Risk**:
- Change is isolated to single function
- Affects only formatting preservation mode
- Easy to revert if issues arise

**Potential Issues**:
- Translated text may exceed column width
  - **Mitigation**: Add fontsize scaling (see step 2 above)
- Some layouts may have intentional X-shifts
  - **Mitigation**: Test on diverse PDFs, add flag if needed

## Next Steps

1. ✅ **Research Complete**: Document created
2. ⏭️ **Implementation**: Modify `insert_formatted_block()`
3. ⏭️ **Testing**: Run CSR PDF through modified pipeline
4. ⏭️ **Validation**: Visual comparison of output vs original
5. ⏭️ **Iteration**: Add overflow handling if needed

---

**Document Status**: Research Complete, Ready for Implementation
**Created**: 2025-11-13
**Last Updated**: 2025-11-13
