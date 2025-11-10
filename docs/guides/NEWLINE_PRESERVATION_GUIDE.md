# Newline Preservation Quick Reference Guide

## Why Newlines Matter

In the line-level PDF translation system, **every newline character (`\n`) represents a layout boundary**. The rendering engine splits translated text by `\n` to map each line back to its original baseline position.

**If newlines are lost or added:**
- Lines merge together → Wrong baseline positions
- Extra lines created → Layout overflow
- Line count mismatch → Rendering fails

---

## Key Principles

### 1. Newlines Are Sacred

```python
# ✅ CORRECT
text = "Line 1\nLine 2\nLine 3"  # 3 lines, 2 newlines
translated = translate(text)
assert translated.count('\n') == 2  # Newlines preserved

# ❌ WRONG
text = "Line 1\nLine 2\nLine 3"
translated = "Line 1 Line 2 Line 3"  # Newlines removed!
# Result: 1 giant line instead of 3 → Layout destroyed
```

### 2. Line Count = Newline Count + 1

```python
lines = ["Line 1", "Line 2", "Line 3"]
text = "\n".join(lines)  # "Line 1\nLine 2\nLine 3"

# Math:
# 3 lines = 2 newlines + 1
# len(lines) = text.count('\n') + 1
```

### 3. Never Use rstrip()/lstrip() on Multi-line Text

```python
# ❌ WRONG - Strips newlines!
text = "Line 1\nLine 2\n"
stripped = text.rstrip()  # "Line 1\nLine 2" - Lost trailing \n!

# ✅ CORRECT - Strip only spaces
text = "Line 1 \nLine 2 \n"
stripped = text.replace(" \n", "\n")  # Preserves \n, removes spaces
```

---

## Implementation Checklist

When working with multi-line text in the pipeline:

- [ ] **Document** that function preserves newlines
- [ ] **Avoid** `rstrip()`, `lstrip()`, `strip()` on multi-line strings
- [ ] **Count** newlines before and after operations
- [ ] **Validate** newline preservation in tests
- [ ] **Warn** if newline count changes unexpectedly

---

## Code Examples

### Extracting Lines from Block

```python
# ✅ CORRECT - Preserves line structure
block = extract_pdf_blocks("doc.pdf")[0]
text = block.text  # Property joins lines with \n
lines = text.split("\n")
assert len(lines) == len(block.lines)
```

### Segmenting with Newlines

```python
# ✅ CORRECT - Preserves newlines through segmentation
segments = segment_blocks(blocks, max_chars=800)
for seg in segments:
    original_newlines = blocks[0].text.count('\n')
    segment_newlines = seg.text.count('\n')
    # Newlines preserved (may be split across segments)
```

### Translating with Newlines

```python
# ✅ CORRECT - System prompt instructs preservation
system_prompt = (
    "CRITICAL: Preserve newline characters (\\n) EXACTLY. "
    "Do not remove, add, or modify line breaks."
)

# Example for LLM
# Input:  "Line 1\nLine 2"
# Output: "Ligne 1\nLigne 2"  # ✅ Newline preserved
```

### Rendering Lines

```python
# ✅ CORRECT - Split by newlines for rendering
translated_text = "Ligne 1\nLigne 2\nLigne 3"
translated_lines = translated_text.split("\n")  # → ["Ligne 1", "Ligne 2", "Ligne 3"]

for line, translation in zip(block.lines, translated_lines):
    render_at_baseline(line.baseline_y, translation)
```

---

## Common Mistakes

### Mistake 1: Using strip() on Multi-line Text

```python
# ❌ WRONG
text = "Line 1\nLine 2\n"
cleaned = text.strip()  # Removes trailing \n!

# ✅ CORRECT
text = "Line 1\nLine 2\n"
cleaned = text  # Leave newlines intact!
```

### Mistake 2: Splitting Without Preserving Newlines

```python
# ❌ WRONG
def split_text(text, max_chars):
    parts.append(text[:max_chars].rstrip())  # Strips \n!

# ✅ CORRECT
def split_text(text, max_chars):
    chunk = text[:split_index]
    # Don't strip newlines!
    parts.append(chunk)
```

### Mistake 3: Joining Lines Without Newlines

```python
# ❌ WRONG
lines = ["Line 1", "Line 2", "Line 3"]
text = " ".join(lines)  # "Line 1 Line 2 Line 3" - No newlines!

# ✅ CORRECT
lines = ["Line 1", "Line 2", "Line 3"]
text = "\n".join(lines)  # "Line 1\nLine 2\nLine 3" - Preserved!
```

### Mistake 4: LLM "Improving" Formatting

```python
# ❌ WRONG - LLM adds extra newlines
input_text = "Line 1\nLine 2"
output_text = "Line 1\n\nLine 2"  # Added blank line!

# ✅ CORRECT - Explicit instruction
system_prompt = "CRITICAL: Preserve \\n EXACTLY. Do not add or remove line breaks."
```

---

## Testing Newline Preservation

### Unit Test Template

```python
def test_preserves_newlines():
    # Original text with known newlines
    original = "Line 1\nLine 2\nLine 3"
    original_count = original.count('\n')  # 2

    # Process through your function
    result = your_function(original)
    result_count = result.count('\n')

    # Assert preservation
    assert result_count == original_count, \
        f"Newlines not preserved: {original_count} → {result_count}"
```

### Integration Test Template

```python
def test_end_to_end_newlines():
    # Extract
    blocks = extract_pdf_blocks("test.pdf")
    line_count = len(blocks[0].lines)
    newline_count = line_count - 1

    # Segment
    segments = segment_blocks(blocks)
    assert segments[0].text.count('\n') == newline_count

    # Translate (mock)
    translated = segments[0].text  # Identity

    # Render
    lines = translated.split("\n")
    assert len(lines) == line_count
```

---

## Debugging Newline Issues

### Symptom: Layout Drift

**Problem:** Translated text doesn't align with original positions

**Check:**
```python
# Count newlines in original vs translated
original_newlines = original_text.count('\n')
translated_newlines = translated_text.count('\n')
print(f"Original: {original_newlines}, Translated: {translated_newlines}")
# If different → Newlines lost/added
```

### Symptom: Line Count Mismatch

**Problem:** `render_pdf()` warns about line count mismatch

**Check:**
```python
# Verify segmentation preserves newlines
block_text = block.text
segment_text = segments[0].text
print(f"Block newlines: {block_text.count(chr(10))}")
print(f"Segment newlines: {segment_text.count(chr(10))}")
```

### Symptom: Text Merged Together

**Problem:** Multiple lines render as one

**Check:**
```python
# Verify split logic
translated = "Line1\nLine2\nLine3"
lines = translated.split("\n")
print(f"Lines: {len(lines)}")  # Should be 3
print(f"Lines: {lines}")        # Should be ["Line1", "Line2", "Line3"]
```

---

## Best Practices

### 1. Document Newline Behavior

```python
def process_text(text: str) -> str:
    """Process text while preserving newline characters.

    IMPORTANT: This function preserves \n exactly as received.
    Each newline represents a layout boundary.
    """
```

### 2. Validate Newline Counts

```python
def validate_newlines(original: str, processed: str) -> bool:
    """Check if newline count is preserved."""
    original_count = original.count('\n')
    processed_count = processed.count('\n')
    if original_count != processed_count:
        print(f"Warning: Newline count changed: {original_count} → {processed_count}")
        return False
    return True
```

### 3. Use Explicit Newline Variables

```python
# ✅ CLEAR
NEWLINE = '\n'
text = NEWLINE.join(lines)

# vs

# ❌ UNCLEAR
text = "\n".join(lines)  # What does \n mean here?
```

### 4. Add Newline Assertions

```python
# Before translation
original_newlines = text.count('\n')

# After translation
translated_newlines = translated.count('\n')
assert translated_newlines == original_newlines, "Newlines not preserved!"
```

---

## Tools & Utilities

### Newline Counter

```python
def count_newlines(text: str) -> int:
    """Count newline characters in text."""
    return text.count('\n')

# Usage
print(f"Newlines: {count_newlines('Line1\nLine2\nLine3')}")  # 2
```

### Newline Validator

```python
def validate_newline_preservation(original: str, processed: str) -> None:
    """Validate that newlines are preserved."""
    orig_count = original.count('\n')
    proc_count = processed.count('\n')

    if orig_count != proc_count:
        raise ValueError(
            f"Newline count mismatch: {orig_count} → {proc_count}\n"
            f"Original: {repr(original[:100])}\n"
            f"Processed: {repr(processed[:100])}"
        )
```

### Newline Visualizer

```python
def visualize_newlines(text: str) -> str:
    """Replace newlines with visible marker for debugging."""
    return text.replace('\n', '↵\n')

# Usage
text = "Line1\nLine2\nLine3"
print(visualize_newlines(text))
# Output:
# Line1↵
# Line2↵
# Line3
```

---

## Quick Reference Table

| Operation | ✅ Preserves Newlines | ❌ Removes Newlines |
|-----------|----------------------|---------------------|
| `text.split('\n')` | ✅ Yes | N/A |
| `'\n'.join(lines)` | ✅ Yes | N/A |
| `text.strip()` | N/A | ❌ Yes (at boundaries) |
| `text.rstrip()` | N/A | ❌ Yes (trailing) |
| `text.lstrip()` | N/A | ❌ Yes (leading) |
| `text.replace(' \n', '\n')` | ✅ Yes | N/A |
| `text[:n]` (slicing) | ✅ Yes | N/A |
| `text.count('\n')` | ✅ Yes (counting) | N/A |

---

## Summary

1. **Newlines = Layout Boundaries**: Each `\n` maps to a line in the PDF
2. **Count Must Match**: Original newlines = Translated newlines
3. **Avoid strip()**: Use space-only stripping instead
4. **Validate Always**: Check newline counts before/after operations
5. **Document Behavior**: Make newline preservation explicit
6. **Test Thoroughly**: Include newline tests in every function

---

## Related Files

- **Implementation:** `/dev/PDF_parser/src/pdf_pipeline/extractor.py`
- **Translation:** `/dev/PDF_parser/src/pdf_pipeline/translator.py`
- **Rendering:** `/dev/PDF_parser/src/pdf_pipeline/pdf_renderer.py`
- **Tests:** `/dev/PDF_parser/test_newline_preservation.py`

---

*Last Updated: 2025-11-05*
*Version: 1.0*
