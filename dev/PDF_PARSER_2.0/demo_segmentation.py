#!/usr/bin/env python3
"""
Demonstration of text segmentation with placeholder encoding for KPS v2.0.

Shows complete workflow:
1. Create document with blocks
2. Segment for translation
3. Encode placeholders
4. Simulate translation
5. Merge translated segments
6. Decode placeholders
"""


def create_sample_document():
    """Create a sample KPSDocument for demonstration."""
    from kps.core.document import (
        ContentBlock,
        BlockType,
        Section,
        SectionType,
        KPSDocument,
        DocumentMetadata,
    )

    # Create materials section
    materials_blocks = [
        ContentBlock(
            block_id="p.materials.001",
            block_type=BlockType.PARAGRAPH,
            content=(
                "Пряжа: 500г пряжи средней толщины.\n"
                "Купить можно на https://hollywool.com.\n"
                "Вопросы: info@hollywool.com"
            ),
        ),
        ContentBlock(
            block_id="p.materials.002",
            block_type=BlockType.PARAGRAPH,
            content=(
                "Спицы: круговые спицы US 7 (4.5мм).\n"
                "См. [[img-needles-p0-occ1]] для выбора."
            ),
        ),
    ]

    # Create instructions section
    instructions_blocks = [
        ContentBlock(
            block_id="p.instructions.001",
            block_type=BlockType.PARAGRAPH,
            content=(
                "Начните с набора 120 петель.\n"
                "Следуйте схеме [[chart-main-p2-occ1]].\n"
                "Вяжите резинкой 2x2 на протяжении 5см."
            ),
        ),
        ContentBlock(
            block_id="p.instructions.002",
            block_type=BlockType.PARAGRAPH,
            content=(
                "Повторяйте ряды 1-24 из схемы.\n"
                "Проверьте размеры в таблице [[tbl-sizes-p3-occ1]].\n"
                "Примерный вес: 450.5г готового изделия."
            ),
        ),
    ]

    # Create document
    doc = KPSDocument(
        slug="sample-pattern",
        metadata=DocumentMetadata(
            title="Образец схемы вязания",
            author="KPS Demo",
            language="ru",
        ),
        sections=[
            Section(
                section_type=SectionType.MATERIALS,
                title="Материалы",
                blocks=materials_blocks,
            ),
            Section(
                section_type=SectionType.INSTRUCTIONS,
                title="Инструкции",
                blocks=instructions_blocks,
            ),
        ],
    )

    return doc


def demonstrate_segmentation():
    """Demonstrate complete segmentation workflow."""
    from kps.extraction import Segmenter
    from kps.core.placeholders import decode_placeholders

    print("=" * 70)
    print("KPS v2.0 Text Segmentation Demonstration")
    print("=" * 70)

    # Step 1: Create document
    print("\n[Step 1] Creating sample document...")
    doc = create_sample_document()
    print(f"✓ Created document: {doc.metadata.title}")
    print(f"  Sections: {len(doc.sections)}")
    total_blocks = sum(len(s.blocks) for s in doc.sections)
    print(f"  Total blocks: {total_blocks}")

    # Step 2: Segment document
    print("\n[Step 2] Segmenting document...")
    segmenter = Segmenter()
    segments = segmenter.segment_document(doc)
    print(f"✓ Created {len(segments)} segments")

    # Step 3: Show encoding
    print("\n[Step 3] Segment details with placeholder encoding...")
    for i, segment in enumerate(segments):
        print(f"\n  Segment {i}: {segment.segment_id}")
        print(f"    Placeholders: {len(segment.placeholders)}")

        if segment.placeholders:
            print(f"    Encoded text preview:")
            preview = segment.text[:120].replace("\n", "\\n")
            print(f"      {preview}...")

            print(f"    Placeholder mappings:")
            for ph_id, original in list(segment.placeholders.items())[:3]:
                print(f"      {ph_id}: {original}")
            if len(segment.placeholders) > 3:
                print(f"      ... and {len(segment.placeholders) - 3} more")

    # Step 4: Demonstrate placeholder types
    print("\n[Step 4] Placeholder type analysis...")
    total_placeholders = sum(len(s.placeholders) for s in segments)
    asset_placeholders = sum(
        1
        for s in segments
        for ph in s.placeholders.keys()
        if ph.startswith("ASSET_")
    )
    standard_placeholders = total_placeholders - asset_placeholders

    print(f"  Total placeholders: {total_placeholders}")
    print(f"    Asset markers ([[...]]): {asset_placeholders}")
    print(f"    Standard tokens (URLs/emails/numbers): {standard_placeholders}")

    # Step 5: Simulate translation
    print("\n[Step 5] Simulating translation...")
    print("  (In production, this would call OpenAI API)")

    # Simple mock translation: just uppercase the encoded text
    translated_segments = []
    for segment in segments:
        # In real translation, placeholders stay as-is
        translated = segment.text.upper()  # Mock translation
        translated_segments.append(translated)

    print(f"✓ Translated {len(translated_segments)} segments")

    # Step 6: Merge back
    print("\n[Step 6] Merging translated segments...")
    merged_doc = segmenter.merge_segments(translated_segments, doc)
    print(f"✓ Merged into document")
    print(f"  Sections: {len(merged_doc.sections)}")
    print(f"  Blocks: {sum(len(s.blocks) for s in merged_doc.sections)}")

    # Step 7: Show result sample
    print("\n[Step 7] Sample translated content (with placeholders)...")
    first_block = merged_doc.sections[0].blocks[0]
    print(f"  Block: {first_block.block_id}")
    print(f"  Content preview:")
    preview = first_block.content[:150].replace("\n", "\\n")
    print(f"    {preview}...")

    # Step 8: Decode placeholders
    print("\n[Step 8] Decoding placeholders...")
    print("  (Restoring URLs, emails, numbers, asset markers)")

    decoded_segments = segmenter.decode_segments(
        [
            type(
                "Segment",
                (),
                {
                    "segment_id": s.segment_id,
                    "text": translated_segments[i],
                    "placeholders": s.placeholders,
                },
            )()
            for i, s in enumerate(segments)
        ]
    )

    print(f"✓ Decoded {len(decoded_segments)} segments")

    # Show final decoded sample
    print("\n[Step 9] Final decoded content sample...")
    decoded_text = decode_placeholders(
        translated_segments[0], segments[0].placeholders
    )
    print(f"  Original (RU):")
    print(f"    {doc.sections[0].blocks[0].content[:100]}...")
    print(f"  After translation + decoding (mock EN):")
    print(f"    {decoded_text[:100]}...")

    # Summary
    print("\n" + "=" * 70)
    print("✓ Segmentation workflow complete!")
    print("=" * 70)
    print("\nWorkflow summary:")
    print("  1. ✓ Document segmented (one segment per block)")
    print("  2. ✓ Fragile tokens encoded as placeholders")
    print("  3. ✓ Newlines preserved throughout")
    print("  4. ✓ Segments translated (mock)")
    print("  5. ✓ Segments merged back into document")
    print("  6. ✓ Placeholders decoded")
    print("\nPlaceholder types handled:")
    print("  ✓ URLs (http://, https://)")
    print("  ✓ Email addresses")
    print("  ✓ Numbers with separators")
    print("  ✓ Asset markers ([[asset_id]])")
    print("=" * 70)


def show_detailed_example():
    """Show detailed encoding example."""
    from kps.core.placeholders import encode_placeholders, decode_placeholders

    print("\n" + "=" * 70)
    print("Detailed Placeholder Encoding Example")
    print("=" * 70)

    text = (
        "Visit https://hollywool.com for patterns.\n"
        "Contact: info@hollywool.com\n"
        "Use 450.5 grams of yarn.\n"
        "See diagram [[img-sample-p0-occ1]] for details."
    )

    print("\nOriginal text:")
    print("-" * 70)
    print(text)

    encoded, placeholders = encode_placeholders(text)

    print("\nEncoded text:")
    print("-" * 70)
    print(encoded)

    print("\nPlaceholder mappings:")
    print("-" * 70)
    for ph_id, original in placeholders.items():
        ph_type = "ASSET" if ph_id.startswith("ASSET_") else "STANDARD"
        print(f"  [{ph_type}] {ph_id} → {original}")

    decoded = decode_placeholders(encoded, placeholders)

    print("\nDecoded text (should match original):")
    print("-" * 70)
    print(decoded)

    print("\nValidation:")
    print("-" * 70)
    if decoded == text:
        print("  ✓ Decoding successful - text matches original")
    else:
        print("  ✗ Decoding failed - text mismatch")

    newlines_original = text.count("\n")
    newlines_encoded = encoded.count("\n")
    newlines_decoded = decoded.count("\n")

    print(f"  Newlines: original={newlines_original}, encoded={newlines_encoded}, decoded={newlines_decoded}")
    if newlines_original == newlines_encoded == newlines_decoded:
        print("  ✓ Newlines preserved throughout")
    else:
        print("  ✗ Newline preservation failed")

    print("=" * 70)


if __name__ == "__main__":
    demonstrate_segmentation()
    show_detailed_example()
