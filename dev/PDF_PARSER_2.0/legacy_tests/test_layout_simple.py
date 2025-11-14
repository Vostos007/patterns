#!/usr/bin/env python3
"""Simple test for layout preservation without pytest."""
from pathlib import Path
import tempfile
import sys

# Skip if dependencies missing
try:
    import fitz
except ImportError:
    print("SKIP: PyMuPDF not available")
    sys.exit(0)

try:
    from langdetect import detect
except ImportError:
    print("SKIP: langdetect not available")
    sys.exit(0)

try:
    import argostranslate
except ImportError:
    print("SKIP: argostranslate not available")
    sys.exit(0)

from kps.layout_preserver import process_pdf

def test_layout_preserve():
    """Test layout preservation with CSR page1 PDF."""
    print("🔄 Testing layout preservation...")
    
    input_pdf = Path("/Users/vostos/Dev/Hollywool patterns/dev/PDF_PARSER_2.0/runtime/input/CSR Report Jan 1 2025 to Jul 30 2025 (1) - page1.pdf")
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_dir = Path(tmp_dir) / "output"
        
        # Process to French
        result_paths = process_pdf(input_pdf, output_dir, target_langs=["fr"])
        
        print(f"✅ Processed {len(result_paths)} files")
        for path in result_paths:
            print(f"   Generated: {path.name}")
            
            # Test the PDF content
            doc = fitz.open(path)
            full_text = ""
            for page in doc:
                full_text += page.get_text("text") + "\n"
            
            print(f"   PDF text length: {len(full_text)} chars")
            print(f"   Sample text: {full_text[:200]}...")
            
            # Check for French content
            has_french = any(word in full_text.lower() for word in ["solde", "compte", "euros", "décembre"])
            print(f"   French content: {'YES' if has_french else 'NO'}")
            
            # Check for English content (should be removed)
            has_english = any(word in full_text for word in ["Merchant Account", "PayPal ID", "Balance", "Statement"])
            print(f"   English content: {'FOUND' if has_english else 'REMOVED'}")
            
            doc.close()
    
    print("🎉 Layout preservation test completed!")

if __name__ == "__main__":
    test_layout_preserve()
