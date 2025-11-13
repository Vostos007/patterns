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


def block_text(block: dict) -> str:
    """Extract text from block, joining horizontal lines with space, vertical with newline."""
    lines = block.get("lines", [])
    if not lines:
        return ""
    
    # Group lines by Y-coordinate to detect horizontal vs vertical layout
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


def rebuild_page(orig_page: fitz.Page, dest_page: fitz.Page, src_lang: str, tgt_lang: str) -> None:
    """Clean rebuild: remove ALL text from dest_page and insert translated text.

    Uses page-level redaction to remove the entire text layer:
    1. Apply single redaction to entire page (removes text, keeps images/graphics)
    2. Extract text blocks from original page
    3. Insert translated text to clean page

    No span-level redactions = no artifacts!
    """
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

    # Pick font once for the entire page (returns alias and Font object)
    font_alias, font = choose_font_for_page(dest_page, target_lang=tgt_lang)

    # STEP 3: Insert translated text to clean page (ONE insertion per block!)
    logger.info(f"Processing {len(text_blocks)} text blocks for translation")
    
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
        logger.debug(f"    Original: {original_text[:50]}...")
        logger.debug(f"    Translated: {translated[:50]}...")

        # Insert translated text ONCE with pre-calculated fontsize
        insert_textbox_smart(
            dest_page,
            rect,
            translated,
            font_alias,
            font,  # Pass Font object for measurement
            average_font_size(block),
        )
        
        # Count blocks after this insertion to debug
        blocks_now = [b for b in dest_page.get_text("dict", sort=True).get("blocks", []) if b.get("type") == 0]
        logger.debug(f"    Blocks after insertion: {len(blocks_now)}")
        blocks_inserted += 1

    # Count final blocks to verify no duplication
    final_blocks = [b for b in dest_page.get_text("dict", sort=True).get("blocks", []) if b.get("type") == 0]
    logger.info(f"Attempted {blocks_inserted} insertions")
    logger.info(f"Final text blocks on page: {len(final_blocks)} (expected: {len(text_blocks)})")
    if len(final_blocks) != len(text_blocks):
        logger.error(f"⚠️  MISMATCH: Expected {len(text_blocks)} blocks, got {len(final_blocks)}!")


def process_pdf(
    input_path: Path,
    output_dir: Path,
    target_langs: list[str] | None = None,
) -> list[Path]:
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
                rebuild_page(src_page, dest_page, src_lang, tgt)

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
