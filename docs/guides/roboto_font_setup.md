# Roboto Font Configuration

The TextWriter renderer now prefers **Roboto** for English, French, and Russian output. To let PyMuPDF embed the correct glyphs, place the font files where the pipeline can find them:

1. Download the "Roboto" family (Roboto-Regular.ttf is sufficient) from Google Fonts.
2. Drop the files in one of the following locations:
   - `src/pdf_pipeline/fonts/`
   - `fonts/` in the repository root
   - `dev/PDF_PARSER_2.0/fonts/`
   - Your system font folder (`/Library/Fonts`, `/usr/share/fonts`, etc.)
3. Alternatively set environment variables:
   - `PDF_FONT_DIR` – directory containing Roboto fonts
   - `PDF_FONT_ROBOTO` – explicit path to `Roboto-Regular.ttf`

If Roboto is not found, the renderer automatically falls back to the built-in Helvetica (`helv`) so PDF generation continues without errors.
