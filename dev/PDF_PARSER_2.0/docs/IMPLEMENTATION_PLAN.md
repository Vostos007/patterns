# Implementation Plan: Приоритетные улучшения

**Дата создания:** 2025-11-11
**Статус:** Ready to start
**Основа:** [GAP_ANALYSIS.md](./GAP_ANALYSIS.md)

---

## Философия реализации

1. **Простота >> Сложность**: Daemon вместо KFP, простой validator вместо ML-модели
2. **Проверенные инструменты**: Pandoc, WeasyPrint, не изобретаем велосипед
3. **Сохранение сильных сторон**: Docling, IDML, Knowledge Base остаются без изменений
4. **Постепенность**: P1 → P2 → P3, каждый этап тестируется отдельно

---

## P1: Автоматизация pipeline (Daemon)

### Цель
Система должна автоматически обрабатывать новые документы в папке `inbox/` без ручного запуска.

### Архитектура

```
inbox/
  ├── document1.pdf    [новый]
  ├── document2.docx   [новый]
  └── processed/       [обработанные]

       ↓ monitor (каждые 5 мин)

    Daemon Process
       ↓

  UnifiedPipeline
       ↓

output/
  ├── document1_en.idml
  ├── document1_fr.idml
  └── ...
```

### Реализация

#### 1.1. Создать модуль daemon

**Файл:** `kps/automation/daemon.py`

```python
"""
Автоматический мониторинг и обработка документов.

Функциональность:
- Мониторинг папки inbox/ каждые N секунд
- Определение новых/измененных файлов (по hash)
- Запуск UnifiedPipeline для новых документов
- Перемещение обработанных в processed/
- Логирование всех операций
"""

import logging
import time
import hashlib
from pathlib import Path
from typing import Set, List
from datetime import datetime

from kps.core import UnifiedPipeline, PipelineConfig

logger = logging.getLogger(__name__)


class DocumentDaemon:
    """
    Daemon для автоматической обработки документов.

    Example:
        >>> daemon = DocumentDaemon(
        ...     inbox_dir="inbox",
        ...     target_languages=["en", "fr"],
        ...     check_interval=300
        ... )
        >>> daemon.start()  # бесконечный цикл
    """

    def __init__(
        self,
        inbox_dir: str = "inbox",
        output_dir: str = "output",
        processed_dir: str = "inbox/processed",
        target_languages: List[str] = None,
        check_interval: int = 300,  # 5 минут
        pipeline_config: PipelineConfig = None,
    ):
        self.inbox = Path(inbox_dir)
        self.output = Path(output_dir)
        self.processed = Path(processed_dir)
        self.target_languages = target_languages or ["en", "fr"]
        self.check_interval = check_interval

        # Создать папки
        self.inbox.mkdir(parents=True, exist_ok=True)
        self.output.mkdir(parents=True, exist_ok=True)
        self.processed.mkdir(parents=True, exist_ok=True)

        # Pipeline
        self.pipeline = UnifiedPipeline(pipeline_config or PipelineConfig())

        # Хранилище обработанных файлов
        self.state_file = Path("data/daemon_state.txt")
        self.processed_hashes = self._load_state()

        logger.info(f"Daemon initialized: inbox={inbox_dir}, interval={check_interval}s")

    def _load_state(self) -> Set[str]:
        """Загрузить список обработанных hash'ей."""
        if self.state_file.exists():
            return set(self.state_file.read_text().strip().split("\n"))
        return set()

    def _save_state(self):
        """Сохранить состояние."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text("\n".join(self.processed_hashes))

    def _get_file_hash(self, path: Path) -> str:
        """Вычислить SHA256 hash файла."""
        sha = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(8192):
                sha.update(chunk)
        return sha.hexdigest()

    def _find_new_documents(self) -> List[Path]:
        """Найти новые документы в inbox."""
        new_docs = []

        for ext in ["*.pdf", "*.docx", "*.doc"]:
            for file in self.inbox.glob(ext):
                if file.is_file():
                    file_hash = self._get_file_hash(file)
                    if file_hash not in self.processed_hashes:
                        new_docs.append(file)
                        logger.info(f"Found new document: {file.name} (hash={file_hash[:8]})")

        return new_docs

    def _process_document(self, file_path: Path):
        """Обработать один документ."""
        logger.info(f"Processing: {file_path.name}")

        try:
            # Запустить pipeline
            result = self.pipeline.process(
                input_file=file_path,
                target_languages=self.target_languages,
                output_dir=self.output,
            )

            # Добавить в обработанные
            file_hash = self._get_file_hash(file_path)
            self.processed_hashes.add(file_hash)
            self._save_state()

            # Переместить в processed
            dest = self.processed / file_path.name
            file_path.rename(dest)

            logger.info(
                f"✓ Successfully processed {file_path.name}: "
                f"{len(result.target_languages)} languages, "
                f"{result.segments_translated} segments, "
                f"cache hit: {result.cache_hit_rate:.0%}"
            )

        except Exception as e:
            logger.error(f"✗ Failed to process {file_path.name}: {e}", exc_info=True)

    def run_once(self):
        """Один цикл проверки."""
        new_docs = self._find_new_documents()

        if not new_docs:
            logger.debug("No new documents found")
            return

        logger.info(f"Found {len(new_docs)} new document(s)")

        for doc in new_docs:
            self._process_document(doc)

    def start(self):
        """Запустить daemon (бесконечный цикл)."""
        logger.info(f"Starting daemon (check every {self.check_interval}s)")
        logger.info(f"Monitoring: {self.inbox}")
        logger.info(f"Target languages: {', '.join(self.target_languages)}")

        while True:
            try:
                self.run_once()
            except KeyboardInterrupt:
                logger.info("Daemon stopped by user")
                break
            except Exception as e:
                logger.error(f"Unexpected error in daemon loop: {e}", exc_info=True)

            time.sleep(self.check_interval)


def main():
    """Entry point для CLI."""
    import typer

    app = typer.Typer()

    @app.command()
    def start(
        inbox: str = "inbox",
        output: str = "output",
        languages: str = "en,fr",
        interval: int = 300,
    ):
        """Запустить daemon."""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )

        daemon = DocumentDaemon(
            inbox_dir=inbox,
            output_dir=output,
            target_languages=languages.split(","),
            check_interval=interval,
        )

        daemon.start()

    app()


if __name__ == "__main__":
    main()
```

#### 1.2. CLI integration

**Добавить в** `kps/cli.py`:

```python
@app.command()
def daemon(
    inbox: str = typer.Option("inbox", help="Inbox directory to monitor"),
    output: str = typer.Option("output", help="Output directory"),
    languages: str = typer.Option("en,fr", help="Target languages (comma-separated)"),
    interval: int = typer.Option(300, help="Check interval (seconds)"),
):
    """Start automatic document processing daemon."""
    from kps.automation.daemon import DocumentDaemon

    daemon = DocumentDaemon(
        inbox_dir=inbox,
        output_dir=output,
        target_languages=languages.split(","),
        check_interval=interval,
    )

    typer.echo(f"Starting daemon: {inbox} → {output}")
    typer.echo(f"Languages: {languages}, Interval: {interval}s")

    daemon.start()
```

#### 1.3. Systemd service (опционально)

**Файл:** `deployment/kps-daemon.service`

```ini
[Unit]
Description=KPS Document Processing Daemon
After=network.target

[Service]
Type=simple
User=kps
WorkingDirectory=/opt/kps
ExecStart=/opt/kps/.venv/bin/python -m kps.automation.daemon start
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Тестирование P1

```bash
# 1. Создать тестовый документ
cp "КАРДИГАН peer gynt.docx" inbox/

# 2. Запустить daemon (одна итерация)
python -m kps.automation.daemon start --interval 10

# 3. Проверить:
# - файл переместился в inbox/processed/
# - output/ содержит переводы
# - data/daemon_state.txt содержит hash
```

### Критерии успеха P1

- [ ] Daemon обнаруживает новые файлы
- [ ] Автоматически запускает UnifiedPipeline
- [ ] Перемещает обработанные файлы
- [ ] Не обрабатывает дубликаты (hash check)
- [ ] Логирует все операции
- [ ] Восстанавливается после ошибок

---

## P2: Term Validator (гарантия соблюдения терминов)

### Цель
100% соблюдение глоссария через post-validation после LLM перевода.

### Архитектура

```
Translation
     ↓
[LLM Response]
     ↓
TermValidator.validate()
     ↓
violations found? → Re-translate with stronger prompt
     ↓
[Final Translation]
```

### Реализация

#### 2.1. Term Validator

**Файл:** `kps/translation/term_validator.py`

```python
"""
Валидатор терминологии для post-проверки переводов.

Обеспечивает 100% соблюдение глоссария через:
- Проверку наличия обязательных терминов
- Проверку protected_tokens
- Проверку do_not_translate правил
"""

import re
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from kps.translation.glossary import GlossaryManager, GlossaryEntry

logger = logging.getLogger(__name__)


@dataclass
class TermViolation:
    """Нарушение терминологии."""

    entry: GlossaryEntry
    violation_type: str  # "missing", "wrong_translation", "protected_token"
    details: str
    severity: str = "error"  # "error", "warning"


class TermValidator:
    """
    Валидатор терминологии.

    Example:
        >>> validator = TermValidator(glossary_manager)
        >>> violations = validator.validate(
        ...     src_text="Провяжите 2 вместе лицевой",
        ...     tgt_text="Knit 2 together",
        ...     src_lang="ru",
        ...     tgt_lang="en"
        ... )
        >>> if violations:
        ...     print(f"Found {len(violations)} violations")
    """

    def __init__(self, glossary: GlossaryManager, strict: bool = True):
        """
        Args:
            glossary: GlossaryManager instance
            strict: If True, all violations are errors; if False, some are warnings
        """
        self.glossary = glossary
        self.strict = strict

    def validate(
        self,
        src_text: str,
        tgt_text: str,
        src_lang: str,
        tgt_lang: str,
    ) -> List[TermViolation]:
        """
        Проверить перевод на соблюдение терминологии.

        Returns:
            List of violations (empty if all good)
        """
        violations = []

        # Получить все релевантные entries
        entries = self._get_relevant_entries(src_lang, tgt_lang)

        for entry in entries:
            # Проверка 1: Если термин есть в исходнике, должен быть в переводе
            if self._contains_term(src_text, entry.source_term, src_lang):
                if not self._contains_term(tgt_text, entry.target_term, tgt_lang):
                    violations.append(
                        TermViolation(
                            entry=entry,
                            violation_type="missing",
                            details=f"Term '{entry.source_term}' found in source, "
                            f"but '{entry.target_term}' not found in translation",
                            severity="error" if self.strict else "warning",
                        )
                    )

            # Проверка 2: Protected tokens
            if hasattr(entry, "metadata") and entry.metadata:
                protected = entry.metadata.get("protected_tokens", [])
                for token in protected:
                    if self._contains_term(src_text, token, src_lang):
                        if not self._contains_term(tgt_text, token, tgt_lang):
                            violations.append(
                                TermViolation(
                                    entry=entry,
                                    violation_type="protected_token",
                                    details=f"Protected token '{token}' missing in translation",
                                    severity="error",
                                )
                            )

            # Проверка 3: Do not translate
            if hasattr(entry, "metadata") and entry.metadata:
                if entry.metadata.get("do_not_translate", False):
                    # Термин должен остаться без изменений
                    if self._contains_term(src_text, entry.source_term, src_lang):
                        if not self._contains_term(tgt_text, entry.source_term, tgt_lang):
                            violations.append(
                                TermViolation(
                                    entry=entry,
                                    violation_type="do_not_translate",
                                    details=f"Term '{entry.source_term}' should not be translated",
                                    severity="error",
                                )
                            )

        return violations

    def _get_relevant_entries(self, src_lang: str, tgt_lang: str) -> List[GlossaryEntry]:
        """Получить entries для языковой пары."""
        all_entries = self.glossary.get_all_entries()
        return [
            e
            for e in all_entries
            if e.source_lang == src_lang and e.target_lang == tgt_lang
        ]

    def _contains_term(self, text: str, term: str, lang: str) -> bool:
        """
        Проверить, содержит ли текст термин.

        Учитывает:
        - Case-insensitive поиск
        - Word boundaries
        - Morphology variants (базовая поддержка)
        """
        # Базовый поиск с word boundaries
        pattern = rf"\b{re.escape(term)}\b"
        if re.search(pattern, text, re.IGNORECASE):
            return True

        # TODO: Добавить морфологические варианты
        # Например: "петля" → "петли", "петель", "петлю"
        # Требует language-specific rules

        return False

    def get_validation_report(self, violations: List[TermViolation]) -> str:
        """Создать читаемый отчет о нарушениях."""
        if not violations:
            return "✓ All terms validated successfully"

        lines = [f"Found {len(violations)} term violation(s):\n"]

        for i, v in enumerate(violations, 1):
            lines.append(
                f"{i}. [{v.severity.upper()}] {v.violation_type}: {v.details}\n"
                f"   Term: {v.entry.source_term} → {v.entry.target_term}"
            )

        return "\n".join(lines)


class EnhancedGlossaryTranslator:
    """
    Расширенный GlossaryTranslator с автоматической валидацией и retry.
    """

    def __init__(self, base_translator, validator: TermValidator, max_retries: int = 2):
        self.translator = base_translator
        self.validator = validator
        self.max_retries = max_retries

    def translate_with_validation(
        self,
        src_text: str,
        src_lang: str,
        tgt_lang: str,
    ) -> Tuple[str, List[TermViolation]]:
        """
        Перевести с автоматической валидацией и retry.

        Returns:
            (translation, violations)
        """
        attempt = 0
        violations = []

        while attempt <= self.max_retries:
            # Перевод
            if attempt == 0:
                # Обычный перевод
                translation = self.translator.translate(src_text, src_lang, tgt_lang)
            else:
                # Retry с усиленным промптом
                logger.warning(f"Retry #{attempt} with stricter term enforcement")
                translation = self._translate_strict(src_text, src_lang, tgt_lang, violations)

            # Валидация
            violations = self.validator.validate(src_text, translation, src_lang, tgt_lang)

            if not violations:
                logger.debug(f"✓ Translation validated successfully (attempt {attempt + 1})")
                return translation, []

            attempt += 1

        # Все попытки исчерпаны
        logger.error(
            f"Translation validation failed after {self.max_retries + 1} attempts:\n"
            f"{self.validator.get_validation_report(violations)}"
        )

        return translation, violations

    def _translate_strict(
        self,
        src_text: str,
        src_lang: str,
        tgt_lang: str,
        prev_violations: List[TermViolation],
    ) -> str:
        """Перевод с усиленным промптом на основе предыдущих ошибок."""
        # Составить список проблемных терминов
        problem_terms = [
            f"- '{v.entry.source_term}' MUST be translated as '{v.entry.target_term}'"
            for v in prev_violations
        ]

        strict_prompt = (
            "CRITICAL: You MUST use these exact translations:\n"
            + "\n".join(problem_terms)
            + "\n\nTranslate the following text:"
        )

        # TODO: Реализовать вызов с modified prompt
        # Пока заглушка
        return self.translator.translate(src_text, src_lang, tgt_lang)
```

#### 2.2. Integration в UnifiedPipeline

**Модифицировать** `kps/core/unified_pipeline.py`:

```python
# В _init_translation():
from kps.translation.term_validator import TermValidator, EnhancedGlossaryTranslator

# После создания translator
self.term_validator = TermValidator(self.glossary, strict=True)
self.validated_translator = EnhancedGlossaryTranslator(
    base_translator=self.translator,
    validator=self.term_validator,
    max_retries=2
)
```

### Тестирование P2

```python
# tests/test_term_validator.py
def test_term_validator():
    glossary = GlossaryManager()
    glossary.load_from_yaml("глоссарий.json")

    validator = TermValidator(glossary)

    # Тест 1: Правильный перевод
    violations = validator.validate(
        src_text="Провяжите 2 вместе лицевой",
        tgt_text="Knit 2 together (k2tog)",
        src_lang="ru",
        tgt_lang="en"
    )
    assert len(violations) == 0

    # Тест 2: Неправильный перевод
    violations = validator.validate(
        src_text="Провяжите 2 вместе лицевой",
        tgt_text="Knit two stitches together",  # нет k2tog!
        src_lang="ru",
        tgt_lang="en"
    )
    assert len(violations) > 0
```

### Критерии успеха P2

- [ ] Validator обнаруживает missing terms
- [ ] Validator обнаруживает protected token violations
- [ ] Validator обнаруживает do_not_translate violations
- [ ] EnhancedTranslator автоматически retry
- [ ] Логирует все нарушения
- [ ] Тесты покрывают основные сценарии

---

## P3: Pandoc Export (DOCX + PDF)

### Цель
Добавить быстрый экспорт в DOCX и PDF через Pandoc для пользователей без InDesign.

### Архитектура

```
KPSDocument
     ↓
Markdown Export
     ↓
Pandoc Renderer
     ├→ DOCX (+ reference.docx)
     └→ PDF (+ LaTeX или WeasyPrint)
```

### Реализация

#### 3.1. Markdown Exporter

**Файл:** `kps/export/markdown_exporter.py`

```python
"""
Экспорт KPSDocument в Markdown для последующего рендера через Pandoc.

Сохраняет:
- Структуру заголовков
- Списки и таблицы
- Изображения
- Подписи
"""

from pathlib import Path
from typing import Optional
import logging

from kps.core.document import KPSDocument, Section, ContentBlock, BlockType

logger = logging.getLogger(__name__)


class MarkdownExporter:
    """
    Экспорт KPSDocument → Markdown.

    Example:
        >>> exporter = MarkdownExporter()
        >>> markdown = exporter.export(document)
        >>> Path("output.md").write_text(markdown)
    """

    def export(self, document: KPSDocument) -> str:
        """Экспортировать документ в Markdown."""
        lines = []

        # Заголовок документа
        if document.metadata.title:
            lines.append(f"# {document.metadata.title}\n")

        # Секции
        for section in document.sections:
            section_md = self._export_section(section)
            lines.append(section_md)
            lines.append("\n")

        return "\n".join(lines)

    def _export_section(self, section: Section, level: int = 2) -> str:
        """Экспортировать секцию."""
        lines = []

        # Заголовок секции
        if section.title:
            lines.append(f"{'#' * level} {section.title}\n")

        # Блоки
        for block in section.blocks:
            block_md = self._export_block(block)
            if block_md:
                lines.append(block_md)

        # Подсекции (рекурсивно)
        if hasattr(section, "subsections"):
            for subsec in section.subsections:
                lines.append(self._export_section(subsec, level + 1))

        return "\n".join(lines)

    def _export_block(self, block: ContentBlock) -> Optional[str]:
        """Экспортировать блок."""
        if block.type == BlockType.TEXT or block.type == BlockType.PARAGRAPH:
            return block.text + "\n"

        elif block.type == BlockType.HEADING:
            # Определить уровень
            level = block.metadata.get("level", 3)
            return f"{'#' * level} {block.text}\n"

        elif block.type == BlockType.LIST_ITEM:
            # TODO: Определить ordered/unordered
            return f"- {block.text}"

        elif block.type == BlockType.TABLE:
            # Markdown table (простая реализация)
            return self._export_table(block)

        elif block.type == BlockType.IMAGE:
            # Image reference
            asset_id = block.metadata.get("asset_id", "unknown")
            caption = block.metadata.get("caption", "")
            return f"![{caption}](assets/{asset_id}.png)\n"

        else:
            logger.warning(f"Unknown block type: {block.type}")
            return None

    def _export_table(self, block: ContentBlock) -> str:
        """Экспортировать таблицу в Markdown."""
        # Простая реализация (требует улучшения)
        # TODO: Parse table structure from metadata
        return f"[Table: {block.text[:50]}...]\n"
```

#### 3.2. Pandoc Renderer

**Файл:** `kps/export/pandoc_renderer.py`

```python
"""
Рендеринг Markdown → DOCX/PDF через Pandoc.
"""

import subprocess
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class PandocRenderer:
    """
    Рендер Markdown через Pandoc.

    Example:
        >>> renderer = PandocRenderer(reference_docx="styles/reference.docx")
        >>> renderer.render_docx("input.md", "output.docx")
        >>> renderer.render_pdf("input.md", "output.pdf")
    """

    def __init__(self, reference_docx: Optional[Path] = None):
        """
        Args:
            reference_docx: Шаблон DOCX со стилями
        """
        self.reference_docx = reference_docx

        # Проверить наличие pandoc
        try:
            subprocess.run(["pandoc", "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError("Pandoc not found. Install: https://pandoc.org/installing.html")

    def render_docx(self, markdown_path: Path, output_path: Path):
        """Рендер Markdown → DOCX."""
        cmd = [
            "pandoc",
            str(markdown_path),
            "--toc",  # Table of contents
            "--toc-depth=3",
            "-o",
            str(output_path),
        ]

        if self.reference_docx and self.reference_docx.exists():
            cmd.extend(["--reference-doc", str(self.reference_docx)])

        logger.info(f"Rendering DOCX: {markdown_path.name} → {output_path.name}")
        subprocess.run(cmd, check=True)
        logger.info(f"✓ DOCX created: {output_path}")

    def render_pdf(
        self,
        markdown_path: Path,
        output_path: Path,
        pdf_engine: str = "xelatex",
    ):
        """Рендер Markdown → PDF."""
        cmd = [
            "pandoc",
            str(markdown_path),
            "--pdf-engine",
            pdf_engine,
            "-V",
            "mainfont=Noto Serif",
            "-V",
            "monofont=Noto Sans Mono",
            "-o",
            str(output_path),
        ]

        logger.info(f"Rendering PDF: {markdown_path.name} → {output_path.name}")
        subprocess.run(cmd, check=True)
        logger.info(f"✓ PDF created: {output_path}")
```

#### 3.3. Integration в UnifiedPipeline

**Модифицировать** `_export_translation()`:

```python
def _export_translation(self, ...):
    if self.config.export_format == "docx":
        # Markdown export
        md_path = output_file.with_suffix(".md")
        markdown = self.markdown_exporter.export(document)
        md_path.write_text(markdown)

        # Pandoc render
        self.pandoc_renderer.render_docx(md_path, output_file)

    elif self.config.export_format == "pdf":
        md_path = output_file.with_suffix(".md")
        markdown = self.markdown_exporter.export(document)
        md_path.write_text(markdown)

        self.pandoc_renderer.render_pdf(md_path, output_file)

    elif self.config.export_format == "idml":
        # Existing IDML export
        ...
```

#### 3.4. Создать reference.docx

**Шаги:**

1. Открыть Word/LibreOffice
2. Настроить стили:
   - **Heading 1**: Noto Sans Bold, 18pt, цвет #2C3E50
   - **Heading 2**: Noto Sans Bold, 14pt, цвет #34495E
   - **Heading 3**: Noto Sans SemiBold, 12pt
   - **Normal**: Noto Serif, 11pt, межстрочный 1.5
   - **Caption**: Noto Sans Italic, 10pt, цвет #7F8C8D
   - **Table Grid**: Границы, padding
3. Сохранить как `dev/PDF_PARSER_2.0/styles/reference.docx`

### Тестирование P3

```bash
# 1. Экспорт в Markdown
python -c "
from kps.core.document import KPSDocument
from kps.export.markdown_exporter import MarkdownExporter

doc = ...  # load document
exporter = MarkdownExporter()
md = exporter.export(doc)
Path('test.md').write_text(md)
"

# 2. Рендер DOCX
python -c "
from kps.export.pandoc_renderer import PandocRenderer
renderer = PandocRenderer(reference_docx='styles/reference.docx')
renderer.render_docx(Path('test.md'), Path('test.docx'))
"

# 3. Рендер PDF
python -c "
renderer.render_pdf(Path('test.md'), Path('test.pdf'))
"
```

### Критерии успеха P3

- [ ] Markdown exporter сохраняет структуру
- [ ] Pandoc render создает DOCX с правильными стилями
- [ ] Pandoc render создает читаемый PDF
- [ ] reference.docx применяется корректно
- [ ] Изображения и таблицы отображаются
- [ ] Integration в UnifiedPipeline работает

---

## Общие критерии готовности

### Code Quality
- [ ] Все тесты проходят (pytest)
- [ ] Type hints и docstrings
- [ ] Логирование всех важных операций
- [ ] Error handling и graceful degradation

### Documentation
- [ ] README обновлен
- [ ] USAGE_GUIDE дополнен примерами
- [ ] API docs для новых модулей

### Performance
- [ ] Daemon не создает memory leaks
- [ ] Validator работает быстро (<100ms на сегмент)
- [ ] Pandoc render занимает разумное время

---

## Timeline

| Неделя | Задачи | Статус |
|--------|--------|--------|
| 1 | P1: Daemon implementation + testing | Planned |
| 2 | P2: Term Validator + integration | Planned |
| 3 | P3: Pandoc export + reference.docx | Planned |
| 4 | Integration testing + documentation | Planned |

---

## Next Steps

1. **Начать с P1** - Daemon для автоматизации
2. Создать тесты для каждого компонента
3. Постепенная интеграция в UnifiedPipeline
4. Документирование процесса

---

**Status:** Ready for implementation
**Owner:** Development Team
**Review Date:** End of Week 4
