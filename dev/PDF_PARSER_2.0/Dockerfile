FROM python:3.11-slim

# Системные зависимости для WeasyPrint (Cairo/Pango/GDK-PixBuf) и шрифты
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates fonts-noto fonts-dejavu \
    libpango-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 libffi8 libglib2.0-0 libjpeg62-turbo \
    && rm -rf /var/lib/apt/lists/*

# Pandoc (официальные бинарники)
RUN curl -L https://github.com/jgm/pandoc/releases/download/3.2/pandoc-3.2-linux-amd64.tar.gz \
  | tar xz --strip-components 1 -C /usr/local

# Python-библиотеки
RUN pip install --no-cache-dir docling weasyprint python-docx

WORKDIR /app
COPY . /app

# Generate reference.docx on build
RUN python scripts/create_reference_docx.py configs/reference.docx || echo "Skipping reference.docx generation"

CMD ["python", "-m", "kps.cli", "export", \
     "--input", "to_translate/sample.pdf", \
     "--md", "build/sample.md", \
     "--html", "build/sample.html", \
     "--docx", "translations/final.docx", \
     "--pdf", "translations/final.pdf", \
     "--reference", "configs/reference.docx", \
     "--css", "configs/pdf.css"]
