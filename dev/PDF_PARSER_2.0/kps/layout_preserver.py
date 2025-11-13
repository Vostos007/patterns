"""Translation overlay utilities that preserve the original PDF layout."""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import List

import fitz  # PyMuPDF
from langdetect import DetectorFactory, detect

logger = logging.getLogger(__name__)

DetectorFactory.seed = 0

from argostranslate import package as argos_package
from argostranslate import translate as argos_translate

try:  # pragma: no cover - optional dependency
    import pymupdf_fonts  # noqa: F401

    HAS_PYMUPDF_FONTS = True
except Exception:  # noqa: BLE001
    HAS_PYMUPDF_FONTS = False

LANGS = ("ru", "en", "fr")


def detect_language(text: str) -> str:
    if not text.strip():
        return "en"
    try:
        lang = detect(text)
    except Exception:  # noqa: BLE001
        lang = "en"
    if lang.startswith("ru"):
        return "ru"
    if lang.startswith("fr"):
        return "fr"
    return "en"


def read_text_sample(doc: fitz.Document, max_chars: int = 2000) -> str:
    chunks: List[str] = []
    for page in doc[: min(3, len(doc))]:
        chunks.append(page.get_text("text", sort=True))
        if sum(len(c) for c in chunks) >= max_chars:
            break
    return "\n".join(chunks)[:max_chars]


def ensure_argos_model(src: str, tgt: str) -> None:
    installed = argos_translate.get_installed_languages()
    src_lang = next((lang for lang in installed if lang.code == src), None)
    tgt_lang = next((lang for lang in installed if lang.code == tgt), None)
    if src_lang and tgt_lang:
        try:
            _ = src_lang.get_translation(tgt_lang)
            return
        except Exception:  # noqa: BLE001
            pass

    argos_package.update_package_index()
    available = argos_package.get_available_packages()
    matches = [pkg for pkg in available if pkg.from_code == src and pkg.to_code == tgt]
    if not matches:
        raise RuntimeError(f"No Argos model found for {src}->{tgt}")
    argos_package.install_from_path(matches[0].download())


def translate_text(text: str, src: str, tgt: str) -> str:
    installed = argos_translate.get_installed_languages()
    src_lang = next((lang for lang in installed if lang.code == src), None)
    tgt_lang = next((lang for lang in installed if lang.code == tgt), None)
    if not (src_lang and tgt_lang):
        raise RuntimeError(f"Missing Argos languages for {src}->{tgt}")
    translation = src_lang.get_translation(tgt_lang)
    return translation.translate(text)


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip(" \t")


def choose_font_for_page(page: fitz.Page, target_lang: str = "en") -> tuple[str, fitz.Font]:
    """Pick appropriate font with Cyrillic support and return both alias and Font object.

    Args:
        page: PDF page to insert font into
        target_lang: Target language code (e.g., 'ru', 'en', 'fr')

    Returns:
        Tuple of (font_alias, Font object) for text measurement

    Raises:
        RuntimeError: If Cyrillic font is required but not available
    """
    alias = "MultiLang"
    requires_cyrillic = target_lang in ("ru", "uk", "bg", "sr", "be", "mk")

    # Method 1: Try pymupdf-fonts (best option)
    if HAS_PYMUPDF_FONTS:
        try:
            font = fitz.Font("notos")
            page.insert_font(fontname=alias, fontbuffer=font.buffer)
            logger.info(f"✅ Using NotoSans font from pymupdf-fonts for {target_lang}")
            return alias, font
        except Exception as e:  # noqa: BLE001
            logger.warning(f"pymupdf-fonts failed: {e}")

    # Method 2: Try system fonts with Cyrillic support
    system_fonts = (
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/arialuni.ttf",
    )

    for candidate in system_fonts:
        if Path(candidate).exists():
            try:
                font = fitz.Font(fontfile=candidate)
                page.insert_font(fontname=alias, fontfile=candidate)
                logger.info(f"✅ Using system font: {candidate} for {target_lang}")
                return alias, font
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Failed to load font {candidate}: {e}")
                continue

    # Method 3: Fail for Cyrillic - no fallback to Helvetica
    if requires_cyrillic:
        error_msg = (
            f"❌ No Cyrillic-compatible font found for language '{target_lang}'!\n"
            "   Install pymupdf-fonts: uv pip install pymupdf-fonts\n"
            "   Or ensure NotoSans/DejaVu/Arial Unicode fonts are available."
        )
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    # For non-Cyrillic, use built-in Helvetica (but log warning)
    logger.warning(f"⚠️  Using built-in Helvetica for {target_lang} (no custom fonts found)")
    font = fitz.Font("helv")
    return "helv", font


def load_font_variant(is_bold: bool, is_italic: bool, target_lang: str) -> fitz.Font:
    """Load appropriate font variant based on style flags and language.
    
    Args:
        is_bold: Whether text should be bold
        is_italic: Whether text should be italic
        target_lang: Target language code
        
    Returns:
        PyMuPDF Font object with correct style
    """
    # Font selection based on language and style
    if target_lang in ("ru", "uk", "bg", "sr", "be", "mk"):
        # Cyrillic support required - use Noto Sans variants
        if HAS_PYMUPDF_FONTS:
            if is_bold and is_italic:
                return fitz.Font("notosbi")  # Noto Sans Bold Italic
            elif is_bold:
                return fitz.Font("notosbo")  # Noto Sans Bold
            elif is_italic:
                return fitz.Font("notosit")  # Noto Sans Italic
            else:
                return fitz.Font("notos")    # Noto Sans Regular
        else:
            # Fallback to regular if pymupdf-fonts not available
            logger.warning(f"⚠️  pymupdf-fonts not available, using regular font for styled text")
            return fitz.Font("notos") if HAS_PYMUPDF_FONTS else fitz.Font("helv")
    else:
        # English/French - use Helvetica variants
        if is_bold and is_italic:
            return fitz.Font("hebi")  # Helvetica Bold Italic
        elif is_bold:
            return fitz.Font("hebo")  # Helvetica Bold
        elif is_italic:
            return fitz.Font("heit")  # Helvetica Italic
        else:
            return fitz.Font("helv")  # Helvetica Regular


def insert_font_variants(page: fitz.Page, target_lang: str) -> dict:
    """Insert all font variants needed for target language into page.
    
    Pre-loads all 4 variants (regular, bold, italic, bold-italic) to avoid
    repeated insertions during text rendering.
    
    Args:
        page: PDF page to insert fonts into
        target_lang: Target language code
        
    Returns:
        dict mapping (is_bold, is_italic) → (font_alias, Font object)
    """
    font_map = {}
    
    # Define all 4 style combinations
    styles = [
        (False, False, "Regular"),
        (True, False, "Bold"),
        (False, True, "Italic"),
        (True, True, "BoldItalic")
    ]
    
    for is_bold, is_italic, style_name in styles:
        font = load_font_variant(is_bold, is_italic, target_lang)
        alias = f"Font_{style_name}"
        
        # Insert font into page
        page.insert_font(fontname=alias, fontbuffer=font.buffer)
        
        # Store mapping
        font_map[(is_bold, is_italic)] = (alias, font)
        
        logger.debug(f"  Inserted {alias}: {font.name}")
    
    return font_map



def extract_span_formatting(span: dict) -> dict:
    """Extract complete formatting information from a PyMuPDF span.
    
    Args:
        span: PyMuPDF span dictionary
        
    Returns:
        dict with: text, font, size, color (RGB tuple), is_bold, is_italic, bbox, origin
    """
    flags = span.get("flags", 0)
    color_int = span.get("color", 0)
    
    # Convert color from integer to RGB tuple
    color_rgb = (
        ((color_int >> 16) & 0xFF) / 255.0,  # Red
        ((color_int >> 8) & 0xFF) / 255.0,   # Green
        (color_int & 0xFF) / 255.0            # Blue
    )
    
    return {
        "text": span.get("text", ""),
        "font": span.get("font", "Helvetica"),
        "size": float(span.get("size", 12.0)),
        "color": color_rgb,
        "is_bold": bool(flags & 16),      # TEXT_FONT_BOLD = 16 (2^4)
        "is_italic": bool(flags & 2),     # TEXT_FONT_ITALIC = 2 (2^1)
        "is_monospaced": bool(flags & 8), # TEXT_FONT_MONOSPACED = 8 (2^3)
        "is_superscript": bool(flags & 1),# TEXT_FONT_SUPERSCRIPT = 1 (2^0)
        "bbox": span.get("bbox"),
        "origin": span.get("origin")
    }


def extract_block_with_formatting(block: dict) -> list:
    """Extract all spans with their formatting from a text block.
    
    Preserves the structure: block → lines → spans with full formatting metadata.
    
    Args:
        block: PyMuPDF text block dictionary
        
    Returns:
        List of line dicts, each containing bbox and list of formatted spans
    """
    formatted_lines = []
    
    for line in block.get("lines", []):
        line_spans = []
        for span in line.get("spans", []):
            fmt = extract_span_formatting(span)
            line_spans.append(fmt)
        
        formatted_lines.append({
            "bbox": line.get("bbox"),
            "spans": line_spans
        })
    
    return formatted_lines


def split_translation_by_spans(original_spans: list, translated_text: str) -> list:
    """Split translated text proportionally across original spans.

    This preserves the multi-span structure for formatting application.
    Splits on word boundaries when possible to avoid mid-word breaks.

    Args:
        original_spans: List of original formatted spans
        translated_text: The full translated text

    Returns:
        List of text fragments, one per original span
    """
    if not original_spans:
        return []

    if len(original_spans) == 1:
        return [translated_text]

    # Calculate character proportions from original spans
    original_texts = [s["text"] for s in original_spans]
    total_chars = sum(len(t) for t in original_texts)

    if total_chars == 0:
        # Equal split if no original text
        chunk_size = len(translated_text) // len(original_spans)
        return [
            translated_text[i*chunk_size:(i+1)*chunk_size]
            for i in range(len(original_spans))
        ]

    # Proportional split with word boundary respect
    proportions = [len(t) / total_chars for t in original_texts]

    text_parts = []
    start = 0
    for i, proportion in enumerate(proportions):
        if i == len(proportions) - 1:
            # Last span gets the remainder
            text_parts.append(translated_text[start:])
        else:
            # Calculate target split position
            target_chars = int(len(translated_text) * proportion)
            split_pos = start + target_chars

            # Search for word boundary within reasonable window
            # Try to find space or hyphen near target position
            search_window = 20  # characters to look ahead/behind
            search_start = max(start + 1, split_pos - search_window)
            # Add +1 to include the position right after the window (rfind excludes end position)
            search_end = min(len(translated_text), split_pos + search_window + 1)

            # Find last space/hyphen before or near target position
            best_split = -1
            for sep in [' ', '-', '\n']:
                pos = translated_text.rfind(sep, search_start, search_end)
                if pos > start and pos > best_split:
                    best_split = pos + 1  # Split after separator

            # Use word boundary if found, otherwise fall back to character split
            if best_split > start:
                split_pos = best_split

            text_parts.append(translated_text[start:split_pos])
            start = split_pos

    return text_parts

def block_text(block: dict) -> str:
    """Extract text from block, preserving table column structure.

    Key insight: Table cells have the same Y-coordinate but significantly
    different X-coordinates. We preserve each cell as a separate line.
    """
    lines = block.get("lines", [])
    if not lines:
        return ""

    # Check if this looks like a table (multiple lines with same Y but different X)
    is_table = False
    if len(lines) > 1:
        # Get Y and X coordinates of all lines
        coords = []
        for line in lines:
            bbox = line.get("bbox", [0, 0, 0, 0])
            y_mid = (bbox[1] + bbox[3]) / 2
            x_start = bbox[0]
            coords.append((y_mid, x_start))

        # Check if all Y-coords are the same (within tolerance)
        y_coords = [c[0] for c in coords]
        x_coords = [c[1] for c in coords]

        y_variance = max(y_coords) - min(y_coords)
        x_variance = max(x_coords) - min(x_coords)

        # Table signature: Same Y (variance < 2pt), Different X (variance > 50pt)
        if y_variance < 2.0 and x_variance > 50.0:
            is_table = True

    # If it's a table, keep each cell as a separate line
    if is_table:
        text_lines = []
        for line in lines:
            fragments = [span.get("text", "") for span in line.get("spans", [])]
            line_text = "".join(fragments)
            text_lines.append(line_text)
        return "\n".join(text_lines)

    # Otherwise, use original logic (group by Y-coordinate)
    text_lines = []
    prev_y = None
    current_row = []

    for line in lines:
        fragments = [span.get("text", "") for span in line.get("spans", [])]
        line_text = "".join(fragments)

        # Get Y-coordinate (use midpoint for robustness)
        bbox = line.get("bbox", [0, 0, 0, 0])
        y_mid = (bbox[1] + bbox[3]) / 2

        # Check if this line is on the same horizontal row as previous
        if prev_y is not None and abs(y_mid - prev_y) < 2.0:  # Tolerance of 2pt
            # Same row - add to current row with space separator
            current_row.append(line_text)
        else:
            # New row - save previous row and start new one
            if current_row:
                text_lines.append("  ".join(current_row))  # Join horizontal fragments with double space
            current_row = [line_text]

        prev_y = y_mid

    # Don't forget the last row
    if current_row:
        text_lines.append("  ".join(current_row))

    return "\n".join(text_lines)


def average_font_size(block: dict) -> float:
    sizes: List[float] = []
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            try:
                sizes.append(float(span.get("size", 0)))
            except (TypeError, ValueError):
                continue
    if not sizes:
        return 11.0
    avg = sum(sizes) / len(sizes)
    return min(18.0, max(7.0, avg))


def insert_textbox_smart(
    page: fitz.Page,
    rect: fitz.Rect,
    text: str,
    fontname: str,
    font: fitz.Font,
    base_fontsize: float,
    min_fontsize: float = 7.0,
    line_height_factor: float = 2.0,  # PyMuPDF needs 2.0x fontsize minimum!
) -> float:
    """Insert text with pre-calculated fontsize to avoid duplicate blocks.

    Calculates optimal font size BEFORE inserting using Font.text_length(),
    then inserts text ONCE. This prevents the duplicate text block issue.

    Args:
        page: PDF page to insert text into
        rect: Rectangle to fit text into
        text: Text to insert
        fontname: Font name/alias to use
        font: Font object for text measurement
        base_fontsize: Initial/preferred font size
        min_fontsize: Minimum acceptable font size (advisory, not enforced)
        line_height_factor: Line height multiplier (2.0 = PyMuPDF minimum requirement)

    Returns:
        Actual fontsize used for insertion
    """
    logger.debug(f"🔍 insert_textbox_smart called:")
    logger.debug(f"   Original text: {text[:100]}...")
    logger.debug(f"   Rect: {rect.width:.1f} x {rect.height:.1f}")
    logger.debug(f"   Fontname: {fontname}, Base fontsize: {base_fontsize:.1f}")
    
    # Clean and prepare text
    text_before = text
    text = clean_text(text)
    logger.debug(f"   After clean_text: {text[:100]}..." if text else "   After clean_text: EMPTY")
    
    if not text or not text.strip():
        logger.warning("⚠️  Empty text after cleaning - skipping insertion!")
        return base_fontsize
    
    lines = text.split("\n") if text else [""]

    # Calculate constraints
    rect_width = rect.width
    rect_height = rect.height

    # 1. Calculate fontsize by width (check each line)
    fs_by_width = base_fontsize
    for line in lines:
        if not line.strip():
            continue
        # Measure width at fontsize=1, then scale
        try:
            w_unit = font.text_length(line, fontsize=1)
            logger.debug(f"   Line width at fs=1: {w_unit:.2f} for '{line[:30]}...'")
            if w_unit > 0:
                fs_line = rect_width / w_unit
                fs_by_width = min(fs_by_width, fs_line)
        except Exception as e:
            logger.debug(f"Failed to measure line width: {e}")
            continue

    # Add safety margin for width
    fs_by_width *= 0.95
    logger.debug(f"   fs_by_width: {fs_by_width:.1f}")

    # 2. Calculate fontsize by height (PyMuPDF needs 2.0x fontsize minimum!)
    num_lines = max(1, len(lines))
    fs_by_height = rect_height / (num_lines * line_height_factor)
    logger.debug(f"   fs_by_height: {fs_by_height:.1f} ({num_lines} lines * {line_height_factor}x = {num_lines * line_height_factor:.1f}x height needed)")

    # 3. Take minimum of all constraints
    fs = min(base_fontsize, fs_by_width, fs_by_height)
    
    # DON'T enforce minimum fontsize - let it be tiny if needed!
    # Otherwise PyMuPDF fails insertion entirely if text won't fit
    if fs < min_fontsize:
        logger.debug(f"   Calculated fontsize {fs:.2f}pt < advisory min {min_fontsize}pt, using anyway")
    
    logger.debug(f"   Final fontsize: {fs:.2f}pt")

    # 4. Insert text ONCE with calculated fontsize
    logger.debug(f"   Calling insert_textbox NOW...")
    leftover = page.insert_textbox(
        rect,
        text,
        fontname=fontname,
        fontsize=fs,
        align=fitz.TEXT_ALIGN_LEFT,
        color=(0, 0, 0),
    )
    
    logger.debug(f"   insert_textbox returned, leftover: {repr(leftover)}")

    # Log if text still doesn't fit (but don't re-insert!)
    if leftover:
        if leftover < 0:
            logger.error(
                f"❌ insert_textbox FAILED (negative return: {leftover})!\n"
                f"   Rect: {rect.width:.1f} x {rect.height:.1f} pt\n"
                f"   Fontsize: {fs:.2f}pt, Lines: {num_lines}, Text length: {len(text)} chars"
            )
        else:
            logger.warning(
                f"⚠️  Text doesn't fit at fontsize {fs:.2f}pt!\n"
                f"   Rect: {rect.width:.1f} x {rect.height:.1f} pt\n"
                f"   Lines: {num_lines}, Text length: {len(text)} chars\n"
                f"   (Accepted truncation - no duplicate insertion)"
            )

    return fs


def _paint_over_block(page: fitz.Page, rect: fitz.Rect, expand: float = 1.0) -> None:
    """Paint a white rectangle over the block area to hide original text.

    This is a clean overlay approach that avoids redaction artifacts.

    Args:
        page: The PDF page to paint on
        rect: Rectangle to paint over (block bbox)
        expand: Padding to expand the rect (ensures full coverage of text)
    """
    # Expand rect slightly to ensure full coverage of original text
    paint_rect = fitz.Rect(rect)
    paint_rect.x0 -= expand
    paint_rect.y0 -= expand
    paint_rect.x1 += expand
    paint_rect.y1 += expand

    # Clip to page boundaries
    paint_rect = paint_rect & page.rect

    if not paint_rect.is_empty:
        # Draw white rectangle with no border
        page.draw_rect(paint_rect, fill=(1, 1, 1), width=0, overlay=True)




def insert_formatted_block(
    page: fitz.Page,
    formatted_lines: list,
    translated_text: str,
    font_map: dict,
    target_lang: str
) -> None:
    """Insert translated text with preserved formatting using insert_text().
    
    This function maintains:
    - Original font sizes
    - Bold/italic styles  
    - Text colors
    - Positioning (bbox-based)
    
    Note: Uses insert_text() instead of TextWriter to support colors.
    
    Args:
        page: PDF page to insert text into
        formatted_lines: List of lines with formatting metadata from original
        translated_text: The translated text to insert
        font_map: Mapping of (is_bold, is_italic) → (font_alias, Font object)
        target_lang: Target language for font selection
    """
    # Split translated text into lines (preserve newlines)
    translated_lines = translated_text.split("\n")
    
    for line_idx, line_data in enumerate(formatted_lines):
        if line_idx >= len(translated_lines):
            break
        
        translated_line = translated_lines[line_idx]
        if not translated_line.strip():
            continue
        
        original_spans = line_data["spans"]
        line_bbox = line_data["bbox"]
        
        # Split translated line proportionally across spans
        text_parts = split_translation_by_spans(original_spans, translated_line)

        # Baseline Y-coordinate for this line
        baseline_y = line_bbox[3] - 2.0  # Baseline is near bottom of bbox

        for span_idx, (text_part, orig_span) in enumerate(zip(text_parts, original_spans)):
            if not text_part.strip():
                continue

            # Get appropriate font variant
            is_bold = orig_span["is_bold"]
            is_italic = orig_span["is_italic"]
            font_alias, font = font_map.get((is_bold, is_italic), font_map[(False, False)])

            # Use original fontsize (no auto-calculation!)
            fontsize = orig_span["size"]

            # Use original color
            color = orig_span["color"]

            # 🔑 KEY FIX: Use original X-coordinate to preserve table column alignment
            # Instead of accumulating position, use exact X from original span
            original_x = orig_span["origin"][0] if orig_span.get("origin") else line_bbox[0]

            # ✨ NEW: Calculate available width for this column to prevent overflow
            if span_idx < len(original_spans) - 1:
                # Not last span: width = distance to next column start
                next_span = original_spans[span_idx + 1]
                next_x = next_span["origin"][0] if next_span.get("origin") else line_bbox[2]
                available_width = next_x - original_x - 5.0  # 5px safety margin
            else:
                # Last span: use original bbox width (conservative estimate)
                span_bbox = orig_span.get("bbox")
                if span_bbox and len(span_bbox) >= 4:
                    available_width = span_bbox[2] - span_bbox[0]
                else:
                    available_width = 1000.0  # Fallback: no constraint

            # ✨ NEW: Scale fontsize if translated text exceeds available column width
            try:
                text_width = font.text_length(text_part, fontsize=fontsize)

                if text_width > available_width and available_width > 10.0:
                    # Calculate scale factor to fit text in available width
                    scale_factor = available_width / text_width
                    original_fontsize = fontsize
                    fontsize = fontsize * scale_factor * 0.95  # 5% safety margin
                    fontsize = max(7.0, fontsize)  # Enforce minimum 7pt for readability

                    logger.debug(
                        f"      Span {span_idx}: Scaled fontsize {original_fontsize:.1f}pt → {fontsize:.1f}pt "
                        f"(text: {text_width:.1f}px > available: {available_width:.1f}px)"
                    )
            except Exception as e:
                logger.debug(f"      Warning: Failed to measure text width: {e}")

            # Insert text with exact formatting, exact positioning, AND width constraint
            page.insert_text(
                (original_x, baseline_y),
                text_part,
                fontname=font_alias,
                fontsize=fontsize,  # ✨ May be reduced from original to fit column
                color=color,
                overlay=True  # Draw on top of existing content
            )
    
    logger.debug(f"  ✅ Inserted block with full formatting preservation")



def extract_table_graphics(page: fitz.Page, table_bbox: fitz.Rect | None = None) -> list:
    """Extract vector graphics (lines/rectangles) from page.
    
    These are typically table borders, underlines, or other decorative elements.
    
    Args:
        page: PDF page to extract graphics from
        table_bbox: Optional bbox to filter graphics (only within this area)
        
    Returns:
        List of drawing dictionaries with type, rect, color, width
    """
    drawings = page.get_drawings()
    graphics = []
    
    for drawing in drawings:
        draw_rect = fitz.Rect(drawing.get("rect", (0, 0, 0, 0)))
        
        # Filter by bbox if specified
        if table_bbox and not draw_rect.intersects(table_bbox):
            continue
        
        graphics.append({
            "type": drawing.get("type"),        # 'l' for line, 'r' for rect, etc.
            "rect": drawing.get("rect"),
            "color": drawing.get("color"),      # RGB tuple
            "width": drawing.get("width", 1.0), # Line width
            "fill": drawing.get("fill"),        # Fill color (if any)
            "items": drawing.get("items", [])   # Path items for complex shapes
        })
    
    return graphics


def redraw_table_borders(page: fitz.Page, graphics: list) -> None:
    """Redraw table borders and vector graphics on page.
    
    This restores borders that were removed during text redaction.
    
    Args:
        page: PDF page to draw on
        graphics: List of graphics from extract_table_graphics()
    """
    if not graphics:
        return
    
    shape = page.new_shape()
    
    for graphic in graphics:
        graphic_type = graphic.get("type")
        rect_data = graphic.get("rect")
        color = graphic.get("color")
        width = graphic.get("width", 1.0)
        fill = graphic.get("fill")
        items = graphic.get("items", [])
        
        if not rect_data:
            continue
        
        rect = fitz.Rect(rect_data)
        
        # Draw based on type
        if graphic_type == "r":  # Rectangle
            shape.draw_rect(
                rect,
                color=color,
                fill=fill,
                width=width
            )
        elif graphic_type == "l":  # Line
            # For lines, use items to get endpoints
            if items and len(items) >= 2:
                p1 = items[0][1] if isinstance(items[0], tuple) else items[0]
                p2 = items[1][1] if isinstance(items[1], tuple) else items[1]
                shape.draw_line(p1, p2, color=color, width=width)
            else:
                # Fallback: draw line from rect corners
                shape.draw_line(
                    (rect.x0, rect.y0),
                    (rect.x1, rect.y1),
                    color=color,
                    width=width
                )
        elif graphic_type == "c":  # Curve
            # Draw curve using items path
            if items:
                # Start path
                for i, item in enumerate(items):
                    if i == 0:
                        shape.drawCont = []  # Start new path
                    # Add path segments
                    # (Simplified - full implementation would handle bezier curves)
        
    # Commit all drawings
    shape.commit()
    
    logger.debug(f"  ✅ Redrawn {len(graphics)} graphics elements (table borders/lines)")

def rebuild_page(orig_page: fitz.Page, dest_page: fitz.Page, src_lang: str, tgt_lang: str, preserve_formatting: bool = False) -> None:
    """Clean rebuild: remove ALL text from dest_page and insert translated text.

    Uses page-level redaction to remove the entire text layer:
    1. Extract vector graphics (table borders) from dest_page BEFORE redaction
    2. Apply single redaction to entire page (removes text, keeps images/graphics)
    3. Extract text blocks from original page
    4. Insert translated text to clean page
    5. Redraw table borders

    Args:
        orig_page: Original page to extract text from
        dest_page: Destination page to insert translated text into
        src_lang: Source language code
        tgt_lang: Target language code
        preserve_formatting: If True, preserve fonts, colors, bold/italic (slower)
    
    No span-level redactions = no artifacts!
    """
    # STEP 0: Extract vector graphics BEFORE redaction
    logger.debug("Extracting vector graphics (table borders)...")
    table_graphics = extract_table_graphics(dest_page)
    logger.debug(f"  Found {len(table_graphics)} graphics elements")
    
    # STEP 1: Remove ALL text from dest_page using page-level redaction
    dest_page.add_redact_annot(dest_page.rect)
    dest_page.apply_redactions(
        images=fitz.PDF_REDACT_IMAGE_NONE,      # Keep images
        graphics=fitz.PDF_REDACT_LINE_ART_NONE  # Keep vector graphics/lines
    )

    # Verify redaction worked (should be 0 text blocks)
    blocks_after_redaction = [b for b in dest_page.get_text("dict", sort=True).get("blocks", []) if b.get("type") == 0]
    if blocks_after_redaction:
        logger.warning(
            f"⚠️  {len(blocks_after_redaction)} residual text blocks remain after redaction! "
            f"This may cause overlaps."
        )
    else:
        logger.debug("✅ Page cleaned successfully - 0 text blocks after redaction")

    # STEP 2: Extract text blocks from original page
    page_dict = orig_page.get_text("dict", sort=True)
    text_blocks = [block for block in page_dict.get("blocks", []) if block.get("type") == 0]

    if preserve_formatting:
        # NEW: Formatting-preserving mode with insert_text()
        logger.info(f"Processing {len(text_blocks)} blocks with formatting preservation")
        
        # Pre-load all font variants
        font_map = insert_font_variants(dest_page, tgt_lang)
        
        for block_idx, block in enumerate(text_blocks):
            original_text = block_text(block)
            if not original_text.strip():
                logger.debug(f"  Block {block_idx}: Empty, skipping")
                continue
            
            try:
                translated = translate_text(original_text, src_lang, tgt_lang)
            except Exception:
                translated = original_text
            
            translated = clean_text(translated)
            
            # Extract formatted spans from original
            formatted_lines = extract_block_with_formatting(block)
            
            logger.debug(f"  Block {block_idx}: Inserting with formatting preservation")
            
            # Insert with full formatting
            insert_formatted_block(
                dest_page,
                formatted_lines,
                translated,
                font_map,
                tgt_lang
            )
        
    else:
        # OLD: Simple mode with insert_textbox_smart (0 overlaps, but loses formatting)
        font_alias, font = choose_font_for_page(dest_page, target_lang=tgt_lang)
        logger.info(f"Processing {len(text_blocks)} text blocks for translation (simple mode)")
        
        blocks_inserted = 0
        for block_idx, block in enumerate(text_blocks):
            original_text = block_text(block)
            if not original_text.strip():
                logger.debug(f"  Block {block_idx}: Empty, skipping")
                continue

            try:
                translated = translate_text(original_text, src_lang, tgt_lang)
            except Exception:
                translated = original_text
            translated = clean_text(translated)

            rect = fitz.Rect(block["bbox"]) & dest_page.rect
            if rect.is_empty:
                logger.debug(f"  Block {block_idx}: Empty rect, skipping")
                continue

            logger.debug(f"  Block {block_idx}: Inserting translated text at rect {rect}")

            # Insert translated text ONCE with pre-calculated fontsize
            insert_textbox_smart(
                dest_page,
                rect,
                translated,
                font_alias,
                font,
                average_font_size(block),
            )
            blocks_inserted += 1
    
    # STEP 3: Redraw table borders that were removed
    if table_graphics:
        logger.debug("Redrawing table borders...")
        redraw_table_borders(dest_page, table_graphics)

    # Count final blocks
    final_blocks = [b for b in dest_page.get_text("dict", sort=True).get("blocks", []) if b.get("type") == 0]
    logger.info(f"Final text blocks on page: {len(final_blocks)} (expected: ~{len(text_blocks)})")
    
    if preserve_formatting:
        logger.info("✅ Formatting preservation complete (fonts, sizes, colors)")


def process_pdf(
    input_path: Path,
    output_dir: Path,
    target_langs: list[str] | None = None,
    preserve_formatting: bool = True,
) -> list[Path]:
    """Process PDF with layout preservation.
    
    Args:
        input_path: Path to input PDF
        output_dir: Directory to save translated PDFs
        target_langs: List of target language codes
        preserve_formatting: If True, preserve fonts, colors, bold/italic
        
    Returns:
        List of paths to generated PDFs
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    src_doc = fitz.open(input_path)
    try:
        sample_text = read_text_sample(src_doc)
        src_lang = detect_language(sample_text)
        targets = (
            [lang for lang in target_langs if lang != src_lang]
            if target_langs
            else [lang for lang in LANGS if lang != src_lang]
        )
        if not targets:
            raise ValueError("No target languages specified for layout preserver")

        produced: list[Path] = []

        for tgt in targets:
            ensure_argos_model(src_lang, tgt)
            dest_doc = fitz.open()  # Create empty document

            # Create pages individually using show_pdf_page (cleaner than insert_pdf)
            for page_index in range(src_doc.page_count):
                src_page = src_doc.load_page(page_index)

                # Create new blank page with same dimensions
                dest_page = dest_doc.new_page(
                    width=src_page.rect.width,
                    height=src_page.rect.height
                )

                # Import page content as clean graphic layer
                dest_page.show_pdf_page(
                    dest_page.rect,  # Target rect
                    src_doc,          # Source document
                    page_index        # Source page number
                )

                # Apply redaction and insert translated text
                rebuild_page(src_page, dest_page, src_lang, tgt, preserve_formatting=preserve_formatting)

            out_path = output_dir / f"{input_path.stem}_{tgt}.pdf"
            dest_doc.save(out_path, deflate=True, garbage=3)
            dest_doc.close()
            produced.append(out_path)

        return produced
    finally:
        src_doc.close()


def _get_font_for_block(block: dict) -> str:
    """Get appropriate font for text block based on content."""
    # Default font name for layout preservation
    return "LayoutSans"
