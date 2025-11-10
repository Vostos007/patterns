# IDML Structure Documentation

Complete reference for InDesign Markup Language (IDML) file format.

## Overview

IDML is InDesign's XML-based file format introduced in CS4. It provides programmatic access to InDesign documents without requiring the InDesign application.

**Key Characteristics:**
- ZIP archive containing XML files
- Human-readable (unlike binary .indd format)
- Version-independent (mostly)
- Suitable for automation and batch processing

## File Structure

IDML files are ZIP archives with specific structure:

```
document.idml (ZIP archive)
├── mimetype                    # MUST be first, uncompressed
├── designmap.xml              # Manifest (table of contents)
├── Stories/                   # Text content
│   ├── Story_u123.xml
│   ├── Story_u456.xml
│   └── ...
├── Spreads/                   # Page layouts
│   ├── Spread_ub6.xml
│   ├── Spread_uc7.xml
│   └── ...
├── XML/                       # Metadata and structure
│   ├── BackingStory.xml      # Document metadata
│   ├── Graphic.xml           # Graphic elements
│   └── Tags.xml              # XML structure tags
├── Resources/                 # Styles and settings
│   ├── Styles.xml            # Paragraph/character styles
│   ├── Fonts.xml             # Font definitions
│   └── Preferences.xml       # Document preferences
└── META-INF/                  # Container metadata
    └── container.xml
```

### Critical: mimetype File

The `mimetype` file **MUST**:
1. Be the **first file** in the ZIP archive
2. Be **uncompressed** (ZIP_STORED, not DEFLATE)
3. Contain exactly: `application/vnd.adobe.indesign-idml-package`
4. Have no newline at end

**Why?** InDesign uses this to quickly identify IDML files without parsing entire ZIP.

## Core XML Files

### 1. designmap.xml

The manifest file listing all document components.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Document DOMVersion="7.5" Self="d">
    <idPkg:Story src="Stories/Story_u123.xml" />
    <idPkg:Story src="Stories/Story_u456.xml" />
    <idPkg:Spread src="Spreads/Spread_ub6.xml" />
    <idPkg:Spread src="Spreads/Spread_uc7.xml" />
    <idPkg:Graphic src="XML/Graphic.xml" />
    <idPkg:Styles src="Resources/Styles.xml" />
</Document>
```

**Key Attributes:**
- `DOMVersion`: IDML version (7.5 = CS6, 8.0 = CC)
- `Self`: Document self-reference ID

### 2. Stories/Story_*.xml

Text content with formatting and inline objects.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Story Self="u123" AppliedTOCStyle="n">
    <StoryPreference />

    <ParagraphStyleRange AppliedParagraphStyle="ParagraphStyle/Heading1">
        <CharacterStyleRange AppliedCharacterStyle="CharacterStyle/$ID/[No character style]">
            <Content>Materials</Content>
        </CharacterStyleRange>
    </ParagraphStyleRange>

    <ParagraphStyleRange AppliedParagraphStyle="ParagraphStyle/BodyText">
        <CharacterStyleRange>
            <Content>100% merino wool, super soft...</Content>
        </CharacterStyleRange>

        <!-- Inline anchored object -->
        <CharacterStyleRange>
            <Rectangle Self="u1a3" Label="img-abc123-p0-occ1">
                <AnchoredObjectSettings
                    AnchoredPosition="InlinePosition"
                    AnchorPoint="TopLeftAnchor"
                    HorizontalAlignment="LeftAlign"
                    VerticalReferencePoint="LineBaseline"
                />
                <Image Self="u1a4">
                    <Link AssetURL="file:///assets/yarn.png" />
                </Image>
            </Rectangle>
        </CharacterStyleRange>
    </ParagraphStyleRange>
</Story>
```

**Key Elements:**
- `Story`: Container for text flow
- `ParagraphStyleRange`: Paragraph with style
- `CharacterStyleRange`: Character-level formatting
- `Content`: Actual text content
- `Rectangle`: Image frame (can be anchored)

### 3. Spreads/Spread_*.xml

Page layout with positioned objects.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Spread Self="ub6" FlattenerOverride="Default">
    <Page Self="p1" GeometricBounds="0 0 792 612">
        <!-- Text frame -->
        <TextFrame Self="u1f2" ParentStory="u123"
                   ItemTransform="1 0 0 1 72 72"
                   GeometricBounds="72 72 720 540">
            <Properties>
                <PathGeometry>
                    <GeometryPathType PathOpen="false">
                        <PathPointArray>
                            <PathPointType Anchor="0 0" />
                            <PathPointType Anchor="648 0" />
                            <PathPointType Anchor="648 468" />
                            <PathPointType Anchor="0 468" />
                        </PathPointArray>
                    </GeometryPathType>
                </PathGeometry>
            </Properties>
        </TextFrame>

        <!-- Image frame -->
        <Rectangle Self="u1a5" ItemTransform="1 0 0 1 100 200">
            <Image Self="u1a6">
                <Link AssetURL="file:///assets/photo.jpg" />
            </Image>
        </Rectangle>
    </Page>
</Spread>
```

**Key Elements:**
- `Spread`: One or more facing pages
- `Page`: Single page with bounds
- `TextFrame`: Text container (references Story)
- `Rectangle`: Image frame
- `ItemTransform`: Position/rotation matrix `[a b c d tx ty]`
- `GeometricBounds`: `[y1 x1 y2 x2]` (InDesign coordinate system)

## Anchored Objects

Anchored objects attach graphics to text, making them flow with content.

### Anchor Types

1. **Inline**: Flows with text like a character
2. **Above Line**: Positioned above text line
3. **Custom**: Custom position relative to text frame

### AnchoredObjectSettings Attributes

```xml
<AnchoredObjectSettings
    AnchoredPosition="Anchored|AboveLine|InlinePosition"
    AnchorPoint="TopLeftAnchor|TopCenterAnchor|..."
    HorizontalAlignment="LeftAlign|CenterAlign|RightAlign"
    HorizontalReferencePoint="ColumnEdge|TextFrame|PageEdge"
    VerticalReferencePoint="LineBaseline|TopOfFrame|BottomOfFrame"
    AnchorXOffset="0"
    AnchorYOffset="0"
    SpaceBefore="None|Height|BoundingBox"
    SpaceAfter="None|Height|BoundingBox"
    AnchorSpaceAbove="0"
    PinPosition="true|false"
    PreventManualPositioning="true|false"
/>
```

**Common Configurations:**

**Inline (flows with text):**
```xml
<AnchoredObjectSettings
    AnchoredPosition="InlinePosition"
    AnchorPoint="TopLeftAnchor"
    HorizontalAlignment="LeftAlign"
    VerticalReferencePoint="LineBaseline"
/>
```

**Custom left-aligned:**
```xml
<AnchoredObjectSettings
    AnchoredPosition="Anchored"
    AnchorPoint="TopLeftAnchor"
    HorizontalAlignment="LeftAlign"
    HorizontalReferencePoint="ColumnEdge"
    VerticalReferencePoint="LineBaseline"
    AnchorXOffset="10"
    AnchorYOffset="-50"
    PinPosition="true"
/>
```

## Object References

### Self Attribute

Every object has unique `Self` identifier:
- Format: `u` + hex/numeric ID
- Examples: `u123`, `u1a3`, `ub6f2`
- Used for cross-references

### Cross-References

**TextFrame → Story:**
```xml
<TextFrame Self="u1f2" ParentStory="u123" />
```

**Image → Link:**
```xml
<Image Self="u1a4">
    <Link Self="u1a5" AssetURL="file:///path/to/image.png" />
</Image>
```

## Coordinate Systems

### InDesign Coordinate System

- Origin: Top-left of page
- X-axis: Left → Right (increases)
- Y-axis: Top → Bottom (increases)
- Units: Points (72 points = 1 inch)

**Note:** Opposite of PDF (origin bottom-left, Y increases upward)

### ItemTransform Matrix

Format: `a b c d tx ty`

Where:
- `[a b c d]` = 2×2 rotation/scale matrix
- `[tx ty]` = translation (position)

**Common transforms:**
- Identity: `1 0 0 1 0 0`
- Translate to (100, 200): `1 0 0 1 100 200`
- Rotate 90°: `0 1 -1 0 tx ty`
- Scale 2×: `2 0 0 2 tx ty`

### GeometricBounds

Format: `[y1 x1 y2 x2]`

**Order is unusual:** top, left, bottom, right

Example:
```xml
<Page GeometricBounds="0 0 792 612">
    <!-- 11×8.5 inch page (letter landscape) -->
    <!-- Top: 0, Left: 0, Bottom: 792pt, Right: 612pt -->
</Page>
```

## Labels and Metadata

### Object Labels

Labels identify objects for external systems:

```xml
<Rectangle Self="u1a3" Label="img-abc123-p0-occ1">
```

**Best Practices:**
- Use consistent naming scheme
- Include page number and occurrence
- Keep labels under 255 characters
- Use ASCII-safe characters

### Custom Metadata

Add custom namespace for KPS metadata:

```xml
<Rectangle Self="u1a3"
           Label="img-abc123-p0-occ1"
           xmlns:kps="http://github.com/vostos/kps/1.0"
           kps:metadata='{"sha256":"abc...","type":"image"}'>
```

## Validation Rules

### Required Files
- `mimetype` (uncompressed, first)
- `designmap.xml`
- `Stories/` directory
- `Spreads/` directory

### XML Well-Formedness
- Valid UTF-8 encoding
- Proper XML declaration
- Well-formed XML (balanced tags)

### References
- All `ParentStory` references must exist
- All `Self` IDs must be unique
- Image links should point to valid files

### Anchored Objects
- Must have valid `AnchoredPosition`
- Must have valid `AnchorPoint`
- Offsets must be numeric

## Common Issues

### Issue: IDML Won't Open in InDesign

**Causes:**
1. `mimetype` not first or compressed
2. Malformed XML
3. Invalid cross-references
4. Missing required files

**Solution:** Use `IDMLValidator` to check structure.

### Issue: Anchored Objects Don't Position Correctly

**Causes:**
1. Invalid `AnchoredPosition` value
2. Missing offset attributes
3. Wrong reference point

**Solution:** Verify all anchored object settings are valid enum values.

### Issue: Images Don't Display

**Causes:**
1. Invalid `AssetURL` path
2. Missing image files
3. Wrong file path format

**Solution:** Use absolute paths or ensure relative paths are correct from IDML location.

## References

- [IDML Specification](http://wwwimages.adobe.com/www.adobe.com/content/dam/acom/en/devnet/indesign/sdk/cs6/idml/idml-specification.pdf)
- [IDML Cookbook](http://wwwimages.adobe.com/www.adobe.com/content/dam/acom/en/devnet/indesign/sdk/cs6/idml/idml-cookbook.pdf)
- [InDesign Scripting Guide](https://www.adobe.com/devnet/indesign/documentation.html)

## Version History

- **IDML 7.5** (CS6): Most stable version
- **IDML 8.0** (CC): Added CC features
- **IDML 9.0+** (CC 2014+): Additional enhancements

**Recommendation:** Target IDML 7.5 for maximum compatibility.
