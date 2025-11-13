# Visual Explanation: PDF Overlay Solution

## The Problem

### Current Implementation Flow
```
┌─────────────────────────────────────────────────────────────┐
│ Step 1: dest_doc.insert_pdf(src_doc)                        │
│                                                              │
│ Source PDF           →        Destination PDF               │
│ ┌──────────────┐              ┌──────────────┐             │
│ │ ▲  Original  │              │ ▲  Original  │             │
│ │ │   Text     │     COPY     │ │   Text     │             │
│ │ │            │   ────────>  │ │            │             │
│ │ ▓▓▓ Images   │     ALL      │ ▓▓▓ Images   │             │
│ │ ══╪══ Lines  │   CONTENT    │ ══╪══ Lines  │             │
│ └──────────────┘              └──────────────┘             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Step 2: rebuild_page() - Paint white + Insert translated    │
│                                                              │
│ Destination PDF becomes:                                     │
│ ┌──────────────┐                                            │
│ │ ▼ Translated │  ← Layer 3: New translated text           │
│ │ ░░░░░░░░░░░░ │  ← Layer 2: White rectangles              │
│ │ ▲  Original  │  ← Layer 1: Original text (HIDDEN!)       │
│ │ │            │                                            │
│ │ ▓▓▓ Images   │  ← Layer 0: Graphics                      │
│ │ ══╪══ Lines  │                                            │
│ └──────────────┘                                            │
│                                                              │
│ ❌ PROBLEM: get_text("dict") sees Layer 1 AND Layer 3!      │
└─────────────────────────────────────────────────────────────┘
```

### Why It's a Problem

```python
# After translation, extracting text gives BOTH layers:
result = page.get_text("dict")
text_blocks = [b for b in result["blocks"] if b["type"] == 0]

# Example output (WRONG):
# Block 1: "Original Russian text"    ← From Layer 1
# Block 2: "Translated English text"  ← From Layer 3
#
# Expected: Only Block 2!
```

---

## The Solution

### Fixed Implementation Flow

```
┌─────────────────────────────────────────────────────────────┐
│ Step 1: Create empty page and copy content                  │
│                                                              │
│ Source PDF           →        Empty Dest Page               │
│ ┌──────────────┐              ┌──────────────┐             │
│ │ ▲  Original  │              │              │             │
│ │ │   Text     │              │              │             │
│ │ │            │              │              │             │
│ │ ▓▓▓ Images   │              │              │             │
│ │ ══╪══ Lines  │              │              │             │
│ └──────────────┘              └──────────────┘             │
│                                                              │
│ dest_page = dest_doc.new_page(width=..., height=...)        │
│ dest_page.show_pdf_page(dest_page.rect, src_doc, page_num)  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Step 2: Copy ALL content from source                        │
│                                                              │
│                                ┌──────────────┐             │
│                                │ ▲  Original  │             │
│         show_pdf_page()        │ │   Text     │             │
│         ────────────────>      │ │            │             │
│                                │ ▓▓▓ Images   │             │
│                                │ ══╪══ Lines  │             │
│                                └──────────────┘             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Step 3: Apply redaction to REMOVE text but KEEP graphics    │
│                                                              │
│ dest_page.add_redact_annot(dest_page.rect)                  │
│ dest_page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)│
│                                                              │
│ Before Redaction      →        After Redaction              │
│ ┌──────────────┐              ┌──────────────┐             │
│ │ ▲  Original  │              │              │             │
│ │ │   Text     │   REMOVE     │   (removed)  │             │
│ │ │            │   ──────>    │              │             │
│ │ ▓▓▓ Images   │   KEEP       │ ▓▓▓ Images   │             │
│ │ ══╪══ Lines  │   KEEP       │ ══╪══ Lines  │             │
│ └──────────────┘              └──────────────┘             │
│                                                              │
│ ✅ Result: Graphics only, NO text layers!                   │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Step 4: Add translated text to clean page                   │
│                                                              │
│                                ┌──────────────┐             │
│                                │ ▼ Translated │  ← Only text│
│         Insert translated      │              │             │
│         ────────────────>      │              │             │
│                                │ ▓▓▓ Images   │             │
│                                │ ══╪══ Lines  │             │
│                                └──────────────┘             │
│                                                              │
│ ✅ Final: Only ONE text layer (translated)!                 │
└─────────────────────────────────────────────────────────────┘
```

### Result Comparison

```
OLD APPROACH:                    NEW APPROACH:
┌──────────────────┐            ┌──────────────────┐
│  Layer 3         │            │  Layer 1         │
│  "Translated"    │            │  "Translated"    │
├──────────────────┤            ├──────────────────┤
│  Layer 2         │            │  Layer 0         │
│  White paint     │            │  Images/Graphics │
├──────────────────┤            └──────────────────┘
│  Layer 1         │
│  "Original"      │  ← PROBLEM!
├──────────────────┤
│  Layer 0         │
│  Images/Graphics │
└──────────────────┘

get_text() sees:                get_text() sees:
- Original text ❌              - Translated text ✅
- Translated text ✅
```

---

## Key PyMuPDF Methods

### 1. `show_pdf_page()` - Copy page content

```python
dest_page.show_pdf_page(
    rect,              # Where to place content (usually dest_page.rect)
    src_doc,           # Source document
    src_page_num,      # Page number to copy from
    clip=None,         # Optional: only copy this region
    rotate=0,          # Optional: rotation angle
    overlay=True       # Put on top of existing content
)
```

**Purpose**: Copy visual content from one page to another (like an image)

### 2. `add_redact_annot()` - Mark area for redaction

```python
page.add_redact_annot(
    rect,              # Area to redact (page.rect = entire page)
    text=None,         # Optional: replacement text
    fill=(1,1,1),      # Optional: fill color (white)
    text_color=None    # Optional: replacement text color
)
```

**Purpose**: Add redaction annotation (doesn't remove content yet)

### 3. `apply_redactions()` - Actually remove content

```python
page.apply_redactions(
    images=0,          # 0=keep, 1=remove, 2=remove-if-covered
    graphics=0,        # 0=keep, 1=remove (PyMuPDF 1.23.0+)
    text=1             # 0=keep, 1=remove (default)
)
```

**Purpose**: Execute all redaction annotations on page

**Constants**:
```python
fitz.PDF_REDACT_IMAGE_NONE = 0      # Keep images
fitz.PDF_REDACT_IMAGE_REMOVE = 1    # Remove images
fitz.PDF_REDACT_GRAPHICS_NONE = 0   # Keep graphics (1.23.0+)
fitz.PDF_REDACT_GRAPHICS_REMOVE = 1 # Remove graphics (1.23.0+)
```

---

## Complete Code Example

```python
import fitz

def create_translated_pdf(input_pdf: str, output_pdf: str):
    """Complete example of the solution."""

    # Open source document
    src_doc = fitz.open(input_pdf)
    dest_doc = fitz.open()  # Empty document

    for page_num in range(len(src_doc)):
        src_page = src_doc[page_num]

        # Step 1: Create empty page with same size
        dest_page = dest_doc.new_page(
            width=src_page.rect.width,
            height=src_page.rect.height
        )

        # Step 2: Copy all content from source
        dest_page.show_pdf_page(
            dest_page.rect,   # Fill entire page
            src_doc,          # From source document
            page_num          # This page number
        )

        # Step 3: Remove ALL text, keep images/graphics
        dest_page.add_redact_annot(dest_page.rect)
        dest_page.apply_redactions(
            images=fitz.PDF_REDACT_IMAGE_NONE  # Keep images (=0)
        )

        # Step 4: Add translated text
        # (Extract text from src_page, translate, insert into dest_page)
        text_dict = src_page.get_text("dict")
        for block in text_dict["blocks"]:
            if block.get("type") == 0:  # Text block
                # Get original text
                original = extract_text_from_block(block)

                # Translate it
                translated = translate(original)

                # Insert translated text
                rect = fitz.Rect(block["bbox"])
                dest_page.insert_textbox(
                    rect,
                    translated,
                    fontname="helv",
                    fontsize=11
                )

    # Save result
    dest_doc.save(output_pdf, deflate=True, garbage=3)
    dest_doc.close()
    src_doc.close()
```

---

## Benefits

| Aspect | Old Approach | New Approach |
|--------|--------------|--------------|
| Text layers | 2 (original + translated) | 1 (translated only) |
| White rectangles | Needed | Not needed |
| `get_text()` result | Both texts ❌ | One text ✅ |
| Images preserved | ✅ | ✅ |
| Vector graphics | ✅ | ✅ |
| PDF file size | Larger (hidden content) | Smaller (cleaner) |
| Searchability | Confusing (2 texts) | Clean (1 text) |
| Copy/paste | May get original | Gets translated |

---

## Testing the Fix

### Before (Current Broken Behavior)
```bash
$ python3 -c "
import fitz
doc = fitz.open('output_ru.pdf')
page = doc[0]
blocks = [b for b in page.get_text('dict')['blocks'] if b['type']==0]
print(f'Text blocks found: {len(blocks)}')
for i, b in enumerate(blocks[:4]):
    print(f'Block {i}: {len(b.get(\"lines\", []))} lines')
"

# Output:
# Text blocks found: 24  ← WRONG! Should be ~12
# Block 0: 2 lines       ← Original Russian
# Block 1: 2 lines       ← Translated English
# Block 2: 1 line        ← Original Russian
# Block 3: 1 line        ← Translated English
```

### After (Fixed Behavior)
```bash
$ python3 -c "
import fitz
doc = fitz.open('output_ru_FIXED.pdf')
page = doc[0]
blocks = [b for b in page.get_text('dict')['blocks'] if b['type']==0]
print(f'Text blocks found: {len(blocks)}')
for i, b in enumerate(blocks[:2]):
    text = extract_block_text(b)
    print(f'Block {i}: {text[:30]}...')
"

# Output:
# Text blocks found: 12  ← CORRECT!
# Block 0: Translated English only...
# Block 1: Translated English only...
```

---

## Summary

**Problem**: White rectangles hide but don't remove original text

**Solution**: Use redaction annotations to truly remove text while preserving images/graphics

**Key insight**: PyMuPDF's `apply_redactions()` can selectively remove content types:
- Remove: Text ✅
- Keep: Images ✅
- Keep: Vector graphics (lines, shapes, logos) ✅

**Result**: Clean PDF with only translated text, making `get_text()` work correctly
