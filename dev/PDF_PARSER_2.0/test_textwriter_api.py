#!/usr/bin/env python3
"""Test TextWriter API to understand correct parameters."""
import fitz

doc = fitz.open()
page = doc.new_page(width=595, height=842)

tw = fitz.TextWriter(page.rect)

# Try to understand TextWriter.append() signature
import inspect
print("TextWriter.append signature:")
try:
    sig = inspect.signature(tw.append)
    print(f"  {sig}")
except Exception as e:
    print(f"  Error getting signature: {e}")

# Check help
print("\nTextWriter.append help:")
try:
    help(tw.append)
except Exception as e:
    print(f"  Error: {e}")

doc.close()
