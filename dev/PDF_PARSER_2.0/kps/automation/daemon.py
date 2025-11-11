"""
Автоматический мониторинг и обработка документов.

Функциональность:
- Мониторинг папки inbox/ каждые N секунд
- Определение новых/измененных файлов (по hash)
- Запуск UnifiedPipeline для новых документов
- Перемещение обработанных в processed/
- Логирование всех операций

Example:
    >>> daemon = DocumentDaemon(
    ...     inbox_dir="inbox",
    ...     target_languages=["en", "fr"],
    ...     check_interval=300
    ... )
    >>> daemon.start()  # бесконечный цикл
"""

import hashlib
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import List, Set

from kps.core import PipelineConfig, UnifiedPipeline

logger = logging.getLogger(__name__)


class DocumentDaemon:
    """
    Daemon для автоматической обработки документов.

    Мониторит папку inbox/ и автоматически обрабатывает новые документы
    через UnifiedPipeline. Использует hash-based deduplication для
    предотвращения повторной обработки одних и тех же файлов.

    Attributes:
        inbox: Папка для входящих документов
        output: Папка для результатов обработки
        processed: Папка для обработанных документов
        target_languages: Список целевых языков
        check_interval: Интервал проверки (секунды)
        pipeline: UnifiedPipeline instance

    Example:
        >>> # Простой запуск
        >>> daemon = DocumentDaemon()
        >>> daemon.run_once()  # одна итерация
        >>>
        >>> # Непрерывная работа
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
        """
        Инициализация daemon.

        Args:
            inbox_dir: Папка для входящих документов
            output_dir: Папка для результатов
            processed_dir: Папка для обработанных файлов
            target_languages: Список языков для перевода (default: ["en", "fr"])
            check_interval: Интервал проверки в секундах (default: 300)
            pipeline_config: Конфигурация pipeline (optional)
        """
        self.inbox = Path(inbox_dir)
        self.output = Path(output_dir)
        self.processed = Path(processed_dir)
        self.target_languages = target_languages or ["en", "fr"]
        self.check_interval = check_interval

        # Создать папки если не существуют
        self.inbox.mkdir(parents=True, exist_ok=True)
        self.output.mkdir(parents=True, exist_ok=True)
        self.processed.mkdir(parents=True, exist_ok=True)

        # Initialize pipeline
        self.pipeline = UnifiedPipeline(pipeline_config or PipelineConfig())

        # State management
        self.state_file = Path("data/daemon_state.txt")
        self.processed_hashes = self._load_state()

        # Statistics
        self.stats = {
            "total_processed": 0,
            "total_errors": 0,
            "start_time": None,
        }

        logger.info(f"DocumentDaemon initialized")
        logger.info(f"  Inbox: {self.inbox.absolute()}")
        logger.info(f"  Output: {self.output.absolute()}")
        logger.info(f"  Languages: {', '.join(self.target_languages)}")
        logger.info(f"  Check interval: {check_interval}s")
        logger.info(f"  Previously processed: {len(self.processed_hashes)} documents")

    def _load_state(self) -> Set[str]:
        """
        Загрузить список обработанных hash'ей из файла состояния.

        Returns:
            Set of file hashes that were already processed
        """
        if self.state_file.exists():
            content = self.state_file.read_text().strip()
            if content:
                return set(content.split("\n"))
        return set()

    def _save_state(self):
        """Сохранить текущее состояние в файл."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text("\n".join(sorted(self.processed_hashes)))
        logger.debug(f"State saved: {len(self.processed_hashes)} hashes")

    def _get_file_hash(self, path: Path) -> str:
        """
        Вычислить SHA256 hash файла.

        Args:
            path: Путь к файлу

        Returns:
            SHA256 hash в hex формате
        """
        sha = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(8192):
                sha.update(chunk)
        return sha.hexdigest()

    def _find_new_documents(self) -> List[Path]:
        """
        Найти новые (не обработанные) документы в inbox.

        Returns:
            List of new document paths
        """
        new_docs = []
        supported_extensions = ["*.pdf", "*.docx", "*.doc"]

        for pattern in supported_extensions:
            for file_path in self.inbox.glob(pattern):
                if not file_path.is_file():
                    continue

                # Skip if already being processed (e.g. .tmp files)
                if file_path.suffix.lower() in [".tmp", ".lock"]:
                    continue

                # Compute hash
                try:
                    file_hash = self._get_file_hash(file_path)
                except Exception as e:
                    logger.error(f"Failed to compute hash for {file_path.name}: {e}")
                    continue

                # Check if already processed
                if file_hash not in self.processed_hashes:
                    new_docs.append(file_path)
                    logger.info(f"Found new document: {file_path.name} (hash={file_hash[:8]}...)")

        return new_docs

    def _process_document(self, file_path: Path):
        """
        Обработать один документ через UnifiedPipeline.

        Args:
            file_path: Путь к документу

        Raises:
            Exception: If processing fails
        """
        logger.info(f"=" * 60)
        logger.info(f"Processing: {file_path.name}")
        logger.info(f"Languages: {', '.join(self.target_languages)}")
        logger.info(f"=" * 60)

        start_time = time.time()

        try:
            # Run pipeline
            result = self.pipeline.process(
                input_file=file_path,
                target_languages=self.target_languages,
                output_dir=self.output,
            )

            # Calculate processing time
            duration = time.time() - start_time

            # Mark as processed
            file_hash = self._get_file_hash(file_path)
            self.processed_hashes.add(file_hash)
            self._save_state()

            # Move to processed folder
            dest = self.processed / file_path.name
            # Handle duplicate names
            if dest.exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                dest = self.processed / f"{file_path.stem}_{timestamp}{file_path.suffix}"

            file_path.rename(dest)

            # Update stats
            self.stats["total_processed"] += 1

            # Log success
            logger.info(f"=" * 60)
            logger.info(f"✓ Successfully processed: {file_path.name}")
            logger.info(f"  Duration: {duration:.1f}s")
            logger.info(f"  Languages: {len(result.target_languages)}")
            logger.info(f"  Segments: {result.segments_translated}")
            logger.info(f"  Cache hit rate: {result.cache_hit_rate:.0%}")
            logger.info(f"  Translation cost: ${result.translation_cost:.4f}")
            logger.info(f"  Moved to: {dest.name}")

            if result.errors:
                logger.warning(f"  Errors: {len(result.errors)}")
                for err in result.errors:
                    logger.warning(f"    - {err}")

            if result.warnings:
                logger.info(f"  Warnings: {len(result.warnings)}")
                for warn in result.warnings:
                    logger.info(f"    - {warn}")

            logger.info(f"=" * 60)

        except Exception as e:
            self.stats["total_errors"] += 1
            logger.error(f"=" * 60)
            logger.error(f"✗ Failed to process: {file_path.name}")
            logger.error(f"  Error: {str(e)}")
            logger.error(f"=" * 60)
            logger.exception("Full traceback:")

            # Optionally move failed files to a separate folder
            failed_dir = self.inbox / "failed"
            failed_dir.mkdir(exist_ok=True)
            failed_dest = failed_dir / file_path.name
            try:
                file_path.rename(failed_dest)
                logger.info(f"Moved failed file to: {failed_dest}")
            except Exception as move_error:
                logger.error(f"Failed to move error file: {move_error}")

            raise

    def run_once(self):
        """
        Выполнить один цикл проверки и обработки.

        Находит новые документы и обрабатывает их последовательно.
        """
        logger.debug("Checking for new documents...")

        new_docs = self._find_new_documents()

        if not new_docs:
            logger.debug("No new documents found")
            return

        logger.info(f"Found {len(new_docs)} new document(s) to process")

        for doc in new_docs:
            try:
                self._process_document(doc)
            except Exception:
                # Error already logged in _process_document
                pass

    def start(self):
        """
        Запустить daemon в режиме бесконечного цикла.

        Мониторит inbox и обрабатывает новые документы.
        Останавливается по Ctrl+C (KeyboardInterrupt).
        """
        logger.info("=" * 60)
        logger.info("Starting DocumentDaemon")
        logger.info("=" * 60)
        logger.info(f"Monitoring: {self.inbox.absolute()}")
        logger.info(f"Check interval: {self.check_interval}s")
        logger.info(f"Target languages: {', '.join(self.target_languages)}")
        logger.info(f"Press Ctrl+C to stop")
        logger.info("=" * 60)

        self.stats["start_time"] = datetime.now()

        try:
            while True:
                try:
                    self.run_once()
                except Exception as e:
                    logger.error(f"Error in daemon loop: {e}", exc_info=True)
                    # Continue running despite errors

                # Sleep
                time.sleep(self.check_interval)

        except KeyboardInterrupt:
            logger.info("\n" + "=" * 60)
            logger.info("Daemon stopped by user")
            self._print_statistics()
            logger.info("=" * 60)

    def _print_statistics(self):
        """Вывести статистику работы daemon."""
        if self.stats["start_time"]:
            duration = datetime.now() - self.stats["start_time"]
            logger.info(f"Runtime: {duration}")

        logger.info(f"Documents processed: {self.stats['total_processed']}")
        logger.info(f"Errors encountered: {self.stats['total_errors']}")

        if self.stats["total_processed"] > 0:
            success_rate = (
                self.stats["total_processed"]
                / (self.stats["total_processed"] + self.stats["total_errors"])
            ) * 100
            logger.info(f"Success rate: {success_rate:.1f}%")


def main():
    """CLI entry point для запуска daemon."""
    import sys

    try:
        import typer
    except ImportError:
        print("Error: typer not installed. Install with: pip install typer[all]")
        sys.exit(1)

    app = typer.Typer()

    @app.command()
    def start(
        inbox: str = typer.Option("inbox", help="Inbox directory to monitor"),
        output: str = typer.Option("output", help="Output directory for translations"),
        languages: str = typer.Option("en,fr", help="Target languages (comma-separated)"),
        interval: int = typer.Option(300, help="Check interval in seconds"),
        log_level: str = typer.Option("INFO", help="Logging level (DEBUG, INFO, WARNING, ERROR)"),
    ):
        """
        Start the document processing daemon.

        Monitors the inbox directory and automatically processes new documents.
        """
        # Setup logging
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # Parse languages
        target_langs = [lang.strip() for lang in languages.split(",")]

        # Create and start daemon
        daemon = DocumentDaemon(
            inbox_dir=inbox,
            output_dir=output,
            target_languages=target_langs,
            check_interval=interval,
        )

        daemon.start()

    app()


if __name__ == "__main__":
    main()
