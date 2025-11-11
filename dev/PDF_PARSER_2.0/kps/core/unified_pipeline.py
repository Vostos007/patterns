"""
Unified Document Processing Pipeline - единая точка входа.

Этот модуль объединяет все компоненты системы в единый pipeline:
1. Извлечение (Docling/PyMuPDF)
2. Сегментация
3. Перевод с глоссарием + самообучение
4. QA проверка
5. Экспорт (InDesign IDML)

Простой, быстрый, надёжный.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Union

# Extraction
from kps.extraction.docling_extractor import DoclingExtractor
from kps.extraction.pymupdf_extractor import PyMuPDFExtractor
from kps.extraction.segmenter import Segmenter, SegmenterConfig  # FIXED: correct class name

# Core
from kps.core.document import KPSDocument

# Translation
from kps.translation import (
    GlossaryManager,
    GlossaryTranslator,
    SemanticTranslationMemory,
    TranslationMemory,
    TranslationOrchestrator,
)
from kps.translation.orchestrator import TranslationSegment

# Knowledge Base (NEW: integrate KB layer)
try:
    from kps.knowledge import KnowledgeBase
    KNOWLEDGE_AVAILABLE = True
except ImportError:
    KNOWLEDGE_AVAILABLE = False

# InDesign
try:
    from kps.indesign.idml_handler import IDMLHandler
    from kps.indesign.style_manager import StyleManager

    INDESIGN_AVAILABLE = True
except ImportError:
    INDESIGN_AVAILABLE = False

# QA
try:
    from kps.qa.pipeline import QAPipeline

    QA_AVAILABLE = True
except ImportError:
    QA_AVAILABLE = False


logger = logging.getLogger(__name__)


class ExtractionMethod(Enum):
    """Метод извлечения контента из документа."""

    AUTO = "auto"  # Автоматический выбор
    DOCLING = "docling"  # Docling (AI-powered)
    PYMUPDF = "pymupdf"  # PyMuPDF (fast & reliable)


class MemoryType(Enum):
    """Тип памяти переводов."""

    NONE = "none"  # Без кэша
    SIMPLE = "simple"  # JSON cache
    SEMANTIC = "semantic"  # SQLite + embeddings + RAG


@dataclass
class PipelineConfig:
    """Конфигурация unified pipeline."""

    # Extraction
    extraction_method: ExtractionMethod = ExtractionMethod.AUTO
    use_ocr: bool = False  # OCR для сканов

    # Translation
    memory_type: MemoryType = MemoryType.SEMANTIC
    memory_path: Optional[str] = "data/translation_memory.db"
    glossary_path: Optional[str] = "glossary.yaml"
    enable_few_shot: bool = True
    enable_auto_suggestions: bool = True

    # Knowledge Base (NEW)
    enable_knowledge_base: bool = True  # Включить RAG
    knowledge_db_path: Optional[str] = "data/knowledge.db"

    # QA
    enable_qa: bool = False  # QA проверка (опционально)
    qa_tolerance: float = 2.0  # Допустимая погрешность (px)

    # Export
    export_format: str = "idml"  # idml, json, markdown
    style_template: Optional[str] = None  # YAML шаблон стилей


@dataclass
class PipelineResult:
    """Результат обработки документа."""

    # Input
    source_file: str
    source_language: str

    # Extraction
    extraction_method: str
    pages_extracted: int
    segments_extracted: int

    # Translation
    target_languages: List[str]
    segments_translated: int
    cache_hit_rate: float  # 0.0-1.0
    glossary_terms_found: int
    translation_cost: float

    # Output
    output_files: Dict[str, str]  # {lang: filepath}

    # Statistics
    processing_time: float  # seconds
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class UnifiedPipeline:
    """
    Unified Document Processing Pipeline.

    Единая система обработки документов от A до Z:
    PDF/DOCX → Извлечение → Перевод → Проверка → IDML

    Example:
        >>> # Простой случай
        >>> pipeline = UnifiedPipeline()
        >>> result = pipeline.process(
        ...     "document.pdf",
        ...     target_languages=["en", "fr"]
        ... )
        >>> print(f"Translated to: {result.target_languages}")
        >>> print(f"Cache hit: {result.cache_hit_rate:.0%}")
        >>>
        >>> # С настройками
        >>> config = PipelineConfig(
        ...     extraction_method=ExtractionMethod.DOCLING,
        ...     memory_type=MemoryType.SEMANTIC,
        ...     enable_qa=True
        ... )
        >>> pipeline = UnifiedPipeline(config)
        >>> result = pipeline.process("document.pdf", ["en"])
    """

    def __init__(self, config: Optional[PipelineConfig] = None):
        """
        Инициализация pipeline.

        Args:
            config: Конфигурация (defaults если None)
        """
        self.config = config or PipelineConfig()

        # Инициализация компонентов
        self._init_extractors()
        self._init_translation()
        self._init_qa()
        self._init_export()

        logger.info("UnifiedPipeline initialized")

    def _init_extractors(self):
        """Инициализация извлекателей."""
        self.docling_extractor = DoclingExtractor()
        self.pymupdf_extractor = PyMuPDFExtractor()

        # FIXED: Use correct Segmenter class with config
        segmenter_config = SegmenterConfig()
        self.segmenter = Segmenter(segmenter_config)

        logger.debug("Extractors initialized")

    def _init_translation(self):
        """Инициализация системы перевода."""
        # Orchestrator
        self.orchestrator = TranslationOrchestrator()

        # Glossary
        self.glossary = GlossaryManager()
        if self.config.glossary_path:
            glossary_file = Path(self.config.glossary_path)
            if glossary_file.exists():
                self.glossary.load_from_yaml(str(glossary_file))
                logger.info(f"Loaded {len(self.glossary.get_all_entries())} glossary terms")

        # Memory
        self.memory = None
        if self.config.memory_type != MemoryType.NONE and self.config.memory_path:
            if self.config.memory_type == MemoryType.SEMANTIC:
                self.memory = SemanticTranslationMemory(
                    self.config.memory_path, use_embeddings=True
                )
                logger.info("Semantic memory initialized (embeddings + RAG)")
            else:  # SIMPLE
                self.memory = TranslationMemory(self.config.memory_path)
                logger.info("Simple memory initialized (JSON cache)")

        # Knowledge Base (NEW: integrate KB layer for RAG)
        self.knowledge_base = None
        if self.config.enable_knowledge_base and KNOWLEDGE_AVAILABLE:
            if self.config.knowledge_db_path:
                kb_path = Path(self.config.knowledge_db_path)
                # Create parent directory if needed
                kb_path.parent.mkdir(parents=True, exist_ok=True)

                self.knowledge_base = KnowledgeBase(
                    str(kb_path),
                    use_embeddings=True,
                    split_sections=True,
                    use_chunking=True,
                )
                logger.info(f"Knowledge Base initialized: {kb_path}")
            else:
                logger.warning("Knowledge Base enabled but no path specified")

        # Translator
        self.translator = GlossaryTranslator(
            self.orchestrator,
            self.glossary,
            memory=self.memory,
            enable_few_shot=self.config.enable_few_shot,
            enable_auto_suggestions=self.config.enable_auto_suggestions,
        )

        # FIXED: Connect Knowledge Base to translator for RAG
        if self.knowledge_base:
            self.translator.knowledge_base = self.knowledge_base
            logger.info("Knowledge Base connected to translator (RAG enabled)")

        logger.debug("Translation system initialized")

    def _init_qa(self):
        """Инициализация QA системы."""
        self.qa_pipeline = None
        if self.config.enable_qa and QA_AVAILABLE:
            self.qa_pipeline = QAPipeline()
            logger.info("QA pipeline initialized")

    def _init_export(self):
        """Инициализация экспорта."""
        self.idml_handler = None
        self.style_manager = None

        if INDESIGN_AVAILABLE:
            self.idml_handler = IDMLHandler()

            if self.config.style_template:
                template_file = Path(self.config.style_template)
                if template_file.exists():
                    self.style_manager = StyleManager.from_yaml(str(template_file))
                    logger.info(f"Loaded style template: {template_file}")

        logger.debug("Export system initialized")

    def process(
        self,
        input_file: Union[str, Path],
        target_languages: List[str],
        output_dir: Optional[Union[str, Path]] = None,
    ) -> PipelineResult:
        """
        Обработать документ полностью.

        Args:
            input_file: Входной файл (PDF, DOCX, etc.)
            target_languages: Целевые языки ["en", "fr", "ru"]
            output_dir: Папка для выходных файлов

        Returns:
            PipelineResult с результатами обработки
        """
        import time

        start_time = time.time()

        input_path = Path(input_file)
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_file}")

        output_path = Path(output_dir) if output_dir else input_path.parent / "output"
        output_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Processing: {input_path.name}")
        logger.info(f"Target languages: {target_languages}")

        errors = []
        warnings = []

        # STEP 1: Извлечение контента
        logger.info("Step 1: Extracting content...")
        try:
            # FIXED: _extract_content returns KPSDocument now
            document = self._extract_content(input_path)
            pages_extracted = len(document.sections)
            logger.info(f"Extracted {pages_extracted} sections from document")
        except Exception as e:
            errors.append(f"Extraction failed: {e}")
            logger.error(f"Extraction error: {e}")
            raise

        # STEP 2: Сегментация
        logger.info("Step 2: Segmenting content...")
        try:
            # FIXED: _segment_content accepts KPSDocument now
            segments = self._segment_content(document)
            logger.info(f"Created {len(segments)} segments")
        except Exception as e:
            errors.append(f"Segmentation failed: {e}")
            logger.error(f"Segmentation error: {e}")
            raise

        # Определить исходный язык
        source_language = self._detect_language(segments)
        logger.info(f"Source language: {source_language}")

        # STEP 3: Перевод
        logger.info("Step 3: Translating...")
        translations = {}
        total_cost = 0.0
        cache_hits = 0
        total_segments = len(segments)
        glossary_terms_found = 0

        for target_lang in target_languages:
            logger.info(f"Translating to {target_lang}...")

            try:
                result = self.translator.translate(
                    segments, target_language=target_lang, source_language=source_language
                )

                translations[target_lang] = result.segments
                total_cost += result.total_cost
                cache_hits += result.cached_segments
                glossary_terms_found = max(glossary_terms_found, result.terms_found)

                logger.info(
                    f"{target_lang}: {result.cached_segments}/{total_segments} from cache"
                )

            except Exception as e:
                errors.append(f"Translation to {target_lang} failed: {e}")
                logger.error(f"Translation error ({target_lang}): {e}")
                continue

        # FIXED: Add zero division protection
        total_operations = total_segments * len(target_languages)
        cache_hit_rate = cache_hits / total_operations if total_operations > 0 else 0.0

        # STEP 4: QA (опционально)
        if self.config.enable_qa and self.qa_pipeline:
            logger.info("Step 4: QA validation...")
            try:
                # TODO: Implement QA check
                pass
            except Exception as e:
                warnings.append(f"QA validation failed: {e}")
                logger.warning(f"QA error: {e}")

        # STEP 5: Экспорт
        logger.info("Step 5: Exporting...")
        output_files = {}

        for target_lang, translated_segments in translations.items():
            output_file = output_path / f"{input_path.stem}_{target_lang}.{self.config.export_format}"

            try:
                self._export_translation(
                    translated_segments,
                    output_file,
                    source_language,
                    target_lang,
                )
                output_files[target_lang] = str(output_file)
                logger.info(f"Exported: {output_file.name}")

            except Exception as e:
                errors.append(f"Export to {target_lang} failed: {e}")
                logger.error(f"Export error ({target_lang}): {e}")

        # Сохранить память переводов
        if self.memory:
            self.translator.save_memory()
            logger.debug("Translation memory saved")

        processing_time = time.time() - start_time

        result = PipelineResult(
            source_file=str(input_path),
            source_language=source_language,
            extraction_method=self.config.extraction_method.value,
            pages_extracted=pages_extracted,
            segments_extracted=len(segments),
            target_languages=target_languages,
            segments_translated=len(segments) * len(translations),
            cache_hit_rate=cache_hit_rate,
            glossary_terms_found=glossary_terms_found,
            translation_cost=total_cost,
            output_files=output_files,
            processing_time=processing_time,
            errors=errors,
            warnings=warnings,
        )

        logger.info(f"Processing complete in {processing_time:.1f}s")
        logger.info(f"Cache hit rate: {cache_hit_rate:.0%}")
        logger.info(f"Translation cost: ${total_cost:.4f}")

        return result

    def _extract_content(self, input_file: Path) -> KPSDocument:
        """
        Извлечь контент из файла.

        FIXED: Returns KPSDocument instead of Dict.
        Uses proper extractor interface (extract_document).

        Args:
            input_file: Path to input file (PDF, DOCX, etc.)

        Returns:
            KPSDocument with structured content
        """
        method = self.config.extraction_method

        # Автоматический выбор
        if method == ExtractionMethod.AUTO:
            # Для PDF используем Docling (AI-powered, лучшее качество)
            if input_file.suffix.lower() == ".pdf":
                method = ExtractionMethod.DOCLING
            else:
                method = ExtractionMethod.DOCLING

        # Извлечение
        if method == ExtractionMethod.DOCLING:
            logger.debug("Using Docling extractor")
            # FIXED: Use correct method signature
            slug = input_file.stem  # Use filename as slug
            return self.docling_extractor.extract_document(input_file, slug)
        else:  # PYMUPDF
            # TODO: PyMuPDFExtractor.extract_assets returns AssetLedger, not KPSDocument
            # For now, fallback to Docling
            logger.warning(
                "PyMuPDF document extraction not implemented, using Docling fallback"
            )
            slug = input_file.stem
            return self.docling_extractor.extract_document(input_file, slug)

    def _segment_content(self, document: KPSDocument) -> List[TranslationSegment]:
        """
        Сегментировать контент для перевода.

        FIXED: Uses proper Segmenter.segment_document() API instead of manual segmentation.
        This ensures placeholder encoding and proper structure handling.

        Args:
            document: KPSDocument from extraction

        Returns:
            List of TranslationSegment with encoded placeholders
        """
        # FIXED: Use Segmenter.segment_document() which properly handles:
        # - Placeholder encoding (preserves [[asset_id]], URLs, numbers)
        # - Document structure validation
        # - Segment ID generation
        # - TranslationSegment construction (only segment_id, text, placeholders)
        return self.segmenter.segment_document(document)

    def _detect_language(self, segments: List[TranslationSegment]) -> str:
        """Определить язык текста."""
        if not segments:
            return "en"

        # Взять первые 5 сегментов для определения
        sample = " ".join([s.text for s in segments[:5]])
        return self.orchestrator.detect_language(sample)

    def _export_translation(
        self,
        translated_segments: List[str],
        output_file: Path,
        source_lang: str,
        target_lang: str,
    ):
        """Экспортировать перевод в файл."""
        if self.config.export_format == "idml" and self.idml_handler:
            # TODO: Implement IDML export
            logger.warning("IDML export not yet implemented, using JSON")
            self._export_json(translated_segments, output_file.with_suffix(".json"))
        elif self.config.export_format == "markdown":
            self._export_markdown(translated_segments, output_file)
        else:  # JSON
            self._export_json(translated_segments, output_file)

    def _export_json(self, segments: List[str], output_file: Path):
        """Экспорт в JSON."""
        import json

        data = {"segments": segments, "count": len(segments)}

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _export_markdown(self, segments: List[str], output_file: Path):
        """Экспорт в Markdown."""
        with open(output_file, "w", encoding="utf-8") as f:
            for i, segment in enumerate(segments, 1):
                f.write(f"{segment}\n\n")

    def get_statistics(self) -> Dict:
        """Получить статистику системы."""
        stats = {
            "glossary_terms": len(self.glossary.get_all_entries()),
            "memory_enabled": self.memory is not None,
            "memory_type": self.config.memory_type.value,
        }

        if self.memory:
            memory_stats = self.translator.get_statistics()
            if memory_stats:
                stats.update(memory_stats)

        return stats


__all__ = [
    "UnifiedPipeline",
    "PipelineConfig",
    "PipelineResult",
    "ExtractionMethod",
    "MemoryType",
]
