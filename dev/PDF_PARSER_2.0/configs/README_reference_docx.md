# Reference DOCX Template

## Generating reference.docx

The `reference.docx` file is a template document that defines all styles for DOCX export via Pandoc.

### Method 1: Using the provided script (recommended)

```bash
# Install python-docx
pip install python-docx

# Run the generator script
python scripts/create_reference_docx.py configs/reference.docx
```

### Method 2: Using Pandoc default template

If you have Pandoc installed:

```bash
# Extract Pandoc's default reference.docx
pandoc -o configs/reference.docx --print-default-data-file reference.docx
```

Then customize the styles in Microsoft Word or LibreOffice:

1. Open `configs/reference.docx`
2. Modify styles:
   - **Heading 1-6**: Font, size, color, spacing
   - **Normal**: Default paragraph style
   - **Code**: Monospace font for code blocks
   - **Caption**: Style for image/table captions
   - **Table**: Table borders and shading
3. Save and close

### Method 3: Manual creation

Create a blank DOCX in Word/LibreOffice and define the following styles:

- **Heading 1**: Calibri Light 16pt, Blue (#2E74B5)
- **Heading 2**: Calibri Light 13pt, Blue (#2E74B5)
- **Heading 3**: Calibri Light 12pt, Blue (#2E74B5)
- **Normal**: Calibri 11pt, line spacing 1.15
- **Code**: Consolas 9pt, gray background
- **Caption**: Calibri 9pt italic, centered
- **Table Grid**: Light grid with borders

Save as `configs/reference.docx`.

## Usage

Once created, the reference.docx is used by Pandoc:

```bash
pandoc input.md --reference-doc=configs/reference.docx -o output.docx
```

All styles from reference.docx will be applied to the generated output.docx.

## Docker

The Docker image automatically generates reference.docx on build using the script.
