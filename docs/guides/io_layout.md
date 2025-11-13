# Runtime I/O Layout

The translation harness now follows a fixed folder contract inspired by Docling reference apps and PaddleOCR's document pipeline (each keeps raw inputs, normalized intermediate assets, and publishable outputs in dedicated folders).citeturn0search0turn1search0

```
runtime/
├─ input/                 # original DOCX/PDF files (copied verbatim)
├─ inter/
│  ├─ json/               # Docling JSON dumps per <slug>_vXXX.json
│  └─ markdown/           # Docling Markdown dumps per <slug>_vXXX.md
├─ output/
│  └─ <slug>/
│     └─ vXXX/            # docx/pdf/json/markdown exports per run
└─ tmp/                   # ephemeral runs when `--tmp` is set
```

- **Input** — every CLI run copies the source document into `input/`, so daemons/tests can reproduce the same artifact without hunting for paths.
- **Intermediate (`inter/`)** — Docling writes the structured JSON + Markdown snapshot once per run right after extraction. These files are versioned so you can diff OCR/layout changes independently of translation output.
- **Output** — each translation run gets `output/<slug>/v001`, then `v002`, etc. All requested formats (docx, pdf, json, markdown, …) for every target language live under that version folder.
- **Tmp runs** — passing `kps translate ... --tmp` routes the entire structure under `runtime/tmp/<timestamp>/...`, so experiments never pollute the canonical history.

This layout gives us a reproducible “input → intermediate → output” lineage similar to enterprise OCR/translation pipelines, while still being easy to navigate by hand.
