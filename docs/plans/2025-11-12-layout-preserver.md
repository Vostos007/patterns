# Layout-Preserved PDF Translation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Пересобрать конвейер перевода PDF так, чтобы итоговые PDF визуально совпадали с оригиналом, но содержали текст только на языке перевода.

**Architecture:** Для каждого PDF извлекаем текстовые блоки PyMuPDF, удаляем исходный текстовый слой, вставляем переводы в те же bbox через `insert_textbox`, при этом векторные объекты и изображения копируются без изменений. CLI `kps` вызывает этот модуль при флаге `--layout-preserve` и логирует артефакты.

**Tech Stack:** Python 3.11, PyMuPDF (fitz), Argos Translate, Click CLI, pytest.

---

### Task 1: Добавить детерминированный PDF-файл-фикстуру и регрессионный тест

**Files:**
- Create: `tests/fixtures/pdf/layout_source.pdf`
- Modify: `tests/kps/test_layout_preserver.py`

**Step 1: Создать фикстуру PDF**

```python
# tests/fixtures/build_layout_fixture.py
import fitz
from pathlib import Path

path = Path(__file__).with_name("layout_source.pdf")
doc = fitz.open()
page = doc.new_page(width=595, height=842)
page.insert_text((72, 90), "Quarterly CSR Report", fontsize=16)
page.draw_rect((70, 120, 525, 240))
page.insert_textbox((75, 125, 520, 235), "Revenue 2024\nNorth America: $12M\nEMEA: $9M", fontsize=11)
page.insert_textbox((72, 260, 525, 500), "Notes: Sustainability investments...", fontsize=12)
doc.save(path)
```

Run: `python tests/fixtures/build_layout_fixture.py`

**Step 2: Написать падающий тест**

```python
# tests/kps/test_layout_preserver.py
from pathlib import Path
import fitz
from kps import layout_preserver

FIXTURE = Path(__file__).parents[1] / "fixtures" / "pdf" / "layout_source.pdf"


def test_process_pdf_replaces_text_layer(tmp_path):
    outputs = layout_preserver.process_pdf(FIXTURE, tmp_path, target_langs=["ru"])
    out_pdf = fitz.open(outputs[0])
    page_text = out_pdf[0].get_text()
    assert "Quarterly CSR Report" not in page_text
    assert "Quarterly" not in page_text
    assert "Отчет" in page_text
```

**Step 3: Запустить тест и убедиться, что он падает**

Run: `pytest tests/kps/test_layout_preserver.py -k text_layer`
Expected: FAIL (старый код не очищает текст полностью / смешивает языки).

---

### Task 2: Переписать `kps/layout_preserver.py` под стратегию «удаляем текст → вставляем перевод»

**Files:**
- Modify: `kps/layout_preserver.py`
- Modify: `kps/__init__.py` (если нужно экспортировать новые утилиты)

**Step 1: Реализовать чистое копирование графики без insert_pdf**

Добавить функцию:

```python
def clone_page_without_text(src_page: fitz.Page, dest_doc: fitz.Document) -> fitz.Page:
    new_page = dest_doc.new_page(width=src_page.rect.width, height=src_page.rect.height)
    display_list = src_page.get_displaylist()
    device = fitz.Device(new_page)
    display_list.run(device)
    new_page.clean_contents()
    return new_page
```

**Step 2: Заменить `rebuild_page`**

```python
def rebuild_page(orig_page, dest_doc, src_lang, tgt_lang):
    dest_page = clone_page_without_text(orig_page, dest_doc)
    bbox_blocks = orig_page.get_text("dict", sort=True).get("blocks", [])
    font_alias = pick_font(dest_page)
    for block in bbox_blocks:
        if block.get("type") != 0:
            continue
        original = block_text(block).strip()
        if not original:
            continue
        translated = clean_text(translate_text(original, src_lang, tgt_lang))
        rect = fitz.Rect(block["bbox"]) & dest_page.rect
        if rect.is_empty:
            continue
        _insert_textbox_auto(dest_page, rect, translated, font_alias, average_font_size(block))
```

**Step 3: Обновить `process_pdf`**

- Создавать `dest_doc = fitz.open()` один раз на язык.
- Для каждой страницы вызывать `clone_page_without_text` + `rebuild_page`.
- Гарантировать закрытие документов в `finally`.

**Step 4: Запустить тесты**

Run: `pytest tests/kps/test_layout_preserver.py`
Expected: PASS.

---

### Task 3: Обновить CLI `kps cli --layout-preserve`

**Files:**
- Modify: `kps/cli.py`
- Modify: `kps/pipeline.py`
- Modify: `tests/kps/test_cli.py` (или создать `tests/kps/test_cli_layout.py`)

**Step 1: Написать интеграционный тест CLI**

```python
from click.testing import CliRunner
from kps.cli import cli


def test_cli_layout_preserve(tmp_path):
    runner = CliRunner()
    result = runner.invoke(cli, [
        "layout-preserve",
        "--input", str(FIXTURE),
        "--output", str(tmp_path),
        "--target", "ru",
    ])
    assert result.exit_code == 0
    assert any(f.name.endswith("_ru.pdf") for f in tmp_path.iterdir())
```

**Step 2: Запустить тест (ожидаем падение)**

Run: `pytest tests/kps/test_cli_layout.py`

**Step 3: Реализовать команду**

- CLI парсит `--target` (повторяемое, default = другие языки).
- Команда вызывает `layout_preserver.process_pdf` и печатает пути.
- Добавить логирование времени и размера файлов.

**Step 4: Прогнать тест**

Run: `pytest tests/kps/test_cli_layout.py`
Expected: PASS.

---

### Task 4: Скрипт визуальной/текстовой проверки + документация

**Files:**
- Create: `scripts/verify_layout_preserve.py`
- Modify: `docs/pdf_pipeline.md`

**Step 1: Написать скрипт проверки**

Функционал:
- Принимает `--original` и `--translated`.
- Сравнивает количество страниц, размеры, число изображений (`page.get_images()`), извлечённый текст (deterministic diff).
- Печатает отчёт и статус.

**Step 2: Задокументировать процесс**

В `docs/pdf_pipeline.md` описать:
- Как запускать `kps cli --layout-preserve`.
- Как использовать `verify_layout_preserve.py`.
- Требования к шрифтам и моделям Argos.

**Step 3: Прогнать скрипт на CSR sample**

Run:
```
python scripts/verify_layout_preserve.py \
  --original runtime/input/CSR\ Report...pdf \
  --translated runtime/output/..._ru.pdf
```
Expected: "MATCH" статус.

---

### Task 5: Финальная регрессия и QA

**Files:**
- Modify: `csr_page1_pipeline_test_report.md`
- Modify: `translation_engine_analysis.md`

**Step 1: Прогнать полный CLI пайплайн**

Run: `poetry run kps cli layout-preserve --input runtime/input/CSR...pdf --output runtime/output/csr-layout --target ru --target fr`
Expected: 2 новых PDF, лог без предупреждений.

**Step 2: Вручную открыть PDF (Preview/Skim) и проверить соответствие**

- Текст читабелен, язык один.
- Таблицы/графика совпадает.

**Step 3: Обновить отчёты**

- Зафиксировать время, размер файлов, замеченные нюансы в `csr_page1_pipeline_test_report.md`.
- Добавить выводы в `translation_engine_analysis.md`.

**Step 4: Финальные тесты**

Run: `pytest tests/kps -q`
Expected: PASS.

**Step 5: Коммит**

```bash
git add kps layout_preserver.py tests/kps docs/plans docs/pdf_pipeline.md scripts/verify_layout_preserve.py \
        csr_page1_pipeline_test_report.md translation_engine_analysis.md
git commit -m "feat: rebuild layout-preserve pipeline for PDFs"
```
