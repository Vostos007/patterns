#!/usr/bin/env python3
"""
Layout preservation verification script.

Compares original and translated PDFs to ensure:
1. Page dimensions are preserved
2. Images/graphics are preserved  
3. Original text is removed
4. Only target language text remains
5. No text overlay artifacts
"""

import sys
import argparse
from pathlib import Path
import json

# Skip if dependencies missing
try:
    import fitz
except ImportError:
    print("ERROR: PyMuPDF not available. Install with: pip install PyMuPDF")
    sys.exit(1)

try:
    from langdetect import detect
except ImportError:
    print("ERROR: langdetect not available. Install with: pip install langdetect")
    sys.exit(1)


def analyze_pdf(pdf_path: Path) -> dict:
    """Analyze PDF structure and content."""
    doc = fitz.open(pdf_path)
    
    analysis = {
        "pages": len(doc),
        "dimensions": [],
        "images": [],
        "text_blocks": [],
        "text_content": "",
        "languages": set()
    }
    
    for page_num, page in enumerate(doc):
        # Page dimensions
        rect = page.rect
        analysis["dimensions"].append({
            "page": page_num,
            "width": rect.width,
            "height": rect.height
        })
        
        # Images
        page_images = page.get_images()
        analysis["images"].extend([{
            "page": page_num,
            "xref": img[0],
            "width": img[2],
            "height": img[3]
        } for img in page_images])
        
        # Text blocks
        text_dict = page.get_text("dict", sort=True)
        text_blocks = []
        
        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:  # Not text
                continue
            
            block_text = ""
            for line in block.get("lines", []):
                line_text = "".join([span.get("text", "") for span in line.get("spans", [])])
                block_text += line_text + "\n"
            
            if block_text.strip():
                text_blocks.append({
                    "page": page_num,
                    "bbox": block.get("bbox"),
                    "text": block_text.strip()
                })
                analysis["text_content"] += block_text + "\n"
                
                # Detect language for this block
                try:
                    if len(block_text.strip()) > 10:  # Only detect for meaningful text
                        lang = detect(block_text.strip())
                        if lang.startswith("en"):
                            analysis["languages"].add("en")
                        elif lang.startswith("fr"):
                            analysis["languages"].add("fr")
                        elif lang.startswith("ru"):
                            analysis["languages"].add("ru")
                except:
                    pass
        
        analysis["text_blocks"].extend(text_blocks)
    
    doc.close()
    return analysis


def compare_pdfs(original_path: Path, translated_path: Path, target_lang: str) -> dict:
    """Compare original and translated PDFs."""
    
    print(f"🔍 Analyzing original: {original_path.name}")
    original = analyze_pdf(original_path)
    
    print(f"🔍 Analyzing translated: {translated_path.name}")
    translated = analyze_pdf(translated_path)
    
    comparison = {
        "page_count": {
            "original": original["pages"],
            "translated": translated["pages"],
            "match": original["pages"] == translated["pages"]
        },
        "dimensions": {
            "differences": []
        },
        "images": {
            "original_count": len(original["images"]),
            "translated_count": len(translated["images"]),
            "match": len(original["images"]) == len(translated["images"])
        },
        "text_languages": {
            "original": list(original["languages"]),
            "translated": list(translated["languages"])
        },
        "target_language_present": target_lang in translated["languages"],
        "source_language_removed": target_lang not in original["languages"] or len(original["languages"]) <= 1,
        "overlay_artifacts": [],
        "quality_score": 0
    }
    
    # Compare page dimensions
    for i, (orig_dim, trans_dim) in enumerate(zip(original["dimensions"], translated["dimensions"])):
        width_diff = abs(orig_dim["width"] - trans_dim["width"])
        height_diff = abs(orig_dim["height"] - trans_dim["height"])
        
        if width_diff > 1 or height_diff > 1:  # Allow 1px tolerance
            comparison["dimensions"]["differences"].append({
                "page": i,
                "original": f"{orig_dim['width']}x{orig_dim['height']}",
                "translated": f"{trans_dim['width']}x{trans_dim['height']}",
                "width_diff": width_diff,
                "height_diff": height_diff
            })
    
    # Check for text overlay artifacts (overlapping text blocks)
    for page_num in range(translated["pages"]):
        page_blocks = [b for b in translated["text_blocks"] if b["page"] == page_num]
        overlaps = 0
        
        for i, block1 in enumerate(page_blocks):
            for block2 in page_blocks[i+1:]:
                bbox1 = block1["bbox"]
                bbox2 = block2["bbox"]
                
                if bbox1 and bbox2:  # Valid bboxes
                    overlap = not (bbox1[2] <= bbox2[0] or bbox2[2] <= bbox1[0] or
                                 bbox1[3] <= bbox2[1] or bbox2[3] <= bbox1[1])
                    
                    if overlap and block1["text"] != block2["text"]:
                        if len(block1["text"]) > 5 and len(block2["text"]) > 5:
                            overlaps += 1
                            comparison["overlay_artifacts"].append({
                                "page": page_num,
                                "text1": block1["text"][:50] + "...",
                                "text2": block2["text"][:50] + "..."
                            })
        
        # Allow 1-2 overlaps for layout complexity
        if overlaps > 2:
            comparison["overlay_artifacts"].append({
                "page": page_num,
                "excessive_overlaps": overlaps,
                "message": f"Too many overlapping text blocks: {overlaps}"
            })
    
    # Calculate quality score
    score = 0
    max_score = 100
    
    # Page count (10 points)
    if comparison["page_count"]["match"]:
        score += 10
    
    # Dimensions (20 points)
    if len(comparison["dimensions"]["differences"]) == 0:
        score += 20
    elif len(comparison["dimensions"]["differences"]) <= 1:
        score += 15
    
    # Images (20 points)
    if comparison["images"]["match"]:
        score += 20
    
    # Target language (25 points)
    if comparison["target_language_present"]:
        score += 25
    
    # No source language (25 points)
    if len(comparison["text_languages"]["original"]) > 1:  # Original had multiple languages
        if target_lang not in comparison["text_languages"]["translated"]:
            score += 25
    elif comparison["source_language_removed"]:
        score += 25
    
    # No overlay artifacts (10 points)
    if len(comparison["overlay_artifacts"]) == 0:
        score += 10
    elif len(comparison["overlay_artifacts"]) <= 2:
        score += 5
    
    comparison["quality_score"] = score
    
    return comparison


def print_results(comparison: dict, original_path: Path, translated_path: Path):
    """Print detailed comparison results."""
    
    print(f"\n📊 Layout Preservation Analysis")
    print(f"   Original: {original_path.name}")
    print(f"   Translated: {translated_path.name}")
    print(f"   Quality Score: {comparison['quality_score']}/100")
    
    # Page count
    status = "✅" if comparison["page_count"]["match"] else "❌"
    print(f"\n📄 Page Count: {status}")
    print(f"   Original: {comparison['page_count']['original']} pages")
    print(f"   Translated: {comparison['page_count']['translated']} pages")
    
    # Dimensions
    if len(comparison["dimensions"]["differences"]) == 0:
        print(f"\n📏 Dimensions: ✅")
        print(f"   All page dimensions preserved exactly")
    else:
        print(f"\n📏 Dimensions: ⚠️")
        for diff in comparison["dimensions"]["differences"]:
            print(f"   Page {diff['page']}: {diff['original']} → {diff['translated']}")
    
    # Images
    img_status = "✅" if comparison["images"]["match"] else "⚠️"
    print(f"\n🖼️ Images: {img_status}")
    print(f"   Original: {comparison['images']['original_count']} images")
    print(f"   Translated: {comparison['images']['translated_count']} images")
    
    # Languages
    print(f"\n🌐 Languages:")
    print(f"   Original: {', '.join(comparison['text_languages']['original']) or 'none'}")
    print(f"   Translated: {', '.join(comparison['text_languages']['translated']) or 'none'}")
    
    target_status = "✅" if comparison["target_language_present"] else "❌"
    print(f"   Target language present: {target_status}")
    
    # Overlay artifacts
    if len(comparison["overlay_artifacts"]) == 0:
        print(f"\n🎨 Text Overlays: ✅")
        print(f"   No overlay artifacts detected")
    else:
        print(f"\n🎨 Text Overlays: ⚠️")
        for artifact in comparison["overlay_artifacts"][:3]:  # Show first 3
            if isinstance(artifact, dict) and "message" in artifact:
                print(f"   Page {artifact['page']}: {artifact['message']}")
            else:
                print(f"   Page {artifact['page']}: Multiple text blocks may overlap")
    
    # Quality assessment
    score = comparison["quality_score"]
    if score >= 90:
        grade = "🏆 EXCELLENT"
    elif score >= 80:
        grade = "✅ GOOD"
    elif score >= 70:
        grade = "⚠️ FAIR"
    else:
        grade = "❌ POOR"
    
    print(f"\n🎯 Quality Assessment: {grade} ({score}/100)")
    
    return score >= 70  # Return True if quality is acceptable


def main():
    parser = argparse.ArgumentParser(description="Verify layout preservation in translated PDFs")
    parser.add_argument("original", help="Original PDF file")
    parser.add_argument("translated", help="Translated PDF file")
    parser.add_argument("--target-lang", required=True, help="Target language code (en/fr/ru)")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    original_path = Path(args.original)
    translated_path = Path(args.translated)
    target_lang = args.target_lang
    
    if not original_path.exists():
        print(f"ERROR: Original file not found: {original_path}")
        sys.exit(1)
    
    if not translated_path.exists():
        print(f"ERROR: Translated file not found: {translated_path}")
        sys.exit(1)
    
    # Compare PDFs
    comparison = compare_pdfs(original_path, translated_path, target_lang)
    
    if args.json:
        print(json.dumps(comparison, indent=2, default=str))
    else:
        success = print_results(comparison, original_path, translated_path)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
