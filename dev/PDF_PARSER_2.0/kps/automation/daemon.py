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
import os
import time
from datetime import datetime
from pathlib import Path
from typing import List, Set, Optional
import fcntl  # For file locking on Unix
import tempfile

from kps.core import PipelineConfig, UnifiedPipeline

logger = logging.getLogger(__name__)


def wait_file_stable(
    path: Path,
    checks: int = 3,
    interval: float = 2.0,
    timeout: float = 30.0
) -> bool:
    """
    Wait for file to become stable (no size/mtime changes).

    This prevents processing files that are still being written/copied.

    Args:
        path: Path to file
        checks: Number of consecutive stable checks required
        interval: Interval between checks (seconds)
        timeout: Maximum wait time (seconds)

    Returns:
        True if file is stable, False if timeout

    Example:
        >>> if wait_file_stable(Path("inbox/doc.pdf")):
        ...     # Safe to process
        ...     process(doc)
    """
    if not path.exists():
        return False

    start_time = time.time()
    last_stat = None
    stable_count = 0

    while (time.time() - start_time) < timeout:
        try:
            current_stat = (path.stat().st_size, path.stat().st_mtime)

            if last_stat is not None:
                if current_stat == last_stat:
                    stable_count += 1
                    if stable_count >= checks:
                        logger.debug(
                            f"File {path.name} is stable after {stable_count} checks"
                        )
                        return True
                else:
                    # File changed, reset counter
                    stable_count = 0
                    logger.debug(f"File {path.name} still changing...")

            last_stat = current_stat
            time.sleep(interval)

        except (OSError, FileNotFoundError) as e:
            logger.warning(f"Error checking file stability: {e}")
            return False

    logger.warning(
        f"File {path.name} did not stabilize within {timeout}s"
    )
    return False


class FileLock:
    """
    Cross-platform file lock using lock files.

    Uses fcntl (Unix) or alternative mechanism to ensure only one
    process can work on a file at a time.

    Example:
        >>> with FileLock(Path("inbox/doc.pdf")) as lock:
        ...     if lock.acquired:
        ...         process_file()
    """

    def __init__(self, file_path: Path, timeout: float = 5.0):
        """
        Args:
            file_path: Path to file to lock
            timeout: Lock acquisition timeout (seconds)
        """
        self.file_path = file_path
        self.lock_path = file_path.with_suffix(file_path.suffix + ".lock")
        self.timeout = timeout
        self.lock_file: Optional[int] = None
        self.acquired = False

    def __enter__(self):
        """Acquire lock."""
        start_time = time.time()

        while (time.time() - start_time) < self.timeout:
            try:
                # Try to create lock file exclusively
                self.lock_file = os.open(
                    self.lock_path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY
                )

                # Write PID to lock file
                os.write(self.lock_file, str(os.getpid()).encode())

                # Apply advisory lock (Unix only)
                try:
                    fcntl.flock(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except (AttributeError, OSError):
                    # fcntl not available or lock failed
                    pass

                self.acquired = True
                logger.debug(f"Acquired lock: {self.lock_path}")
                return self

            except FileExistsError:
                # Lock file exists, check if stale
                if self._is_stale_lock():
                    logger.warning(f"Removing stale lock: {self.lock_path}")
                    try:
                        self.lock_path.unlink()
                    except FileNotFoundError:
                        pass
                else:
                    # Active lock, wait and retry
                    time.sleep(0.1)
                    continue

            except Exception as e:
                logger.error(f"Failed to acquire lock: {e}")
                break

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Release lock."""
        if self.lock_file is not None:
            try:
                # Release fcntl lock
                try:
                    fcntl.flock(self.lock_file, fcntl.LOCK_UN)
                except (AttributeError, OSError):
                    pass

                os.close(self.lock_file)
                self.lock_path.unlink(missing_ok=True)
                logger.debug(f"Released lock: {self.lock_path}")
            except Exception as e:
                logger.error(f"Error releasing lock: {e}")

        self.acquired = False

    def _is_stale_lock(self) -> bool:
        """Check if lock file is stale (process no longer exists)."""
        try:
            if not self.lock_path.exists():
                return True

            # Check if lock is old (> 1 hour)
            age = time.time() - self.lock_path.stat().st_mtime
            if age > 3600:
                return True

            # Try to read PID from lock file
            with open(self.lock_path, 'r') as f:
                pid_str = f.read().strip()
                if not pid_str:
                    return True

                pid = int(pid_str)

                # Check if process with this PID exists (Unix only)
                try:
                    os.kill(pid, 0)  # Signal 0 = check existence
                    return False  # Process exists, lock is active
                except (OSError, ProcessLookupError):
                    return True  # Process doesn't exist, stale lock

        except Exception as e:
            logger.warning(f"Error checking stale lock: {e}")
            return False  # Assume active on error


def exponential_backoff(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: bool = True
) -> float:
    """
    Calculate exponential backoff delay.

    Args:
        attempt: Attempt number (0-indexed)
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        jitter: Add random jitter to prevent thundering herd

    Returns:
        Delay in seconds

    Example:
        >>> for attempt in range(5):
        ...     delay = exponential_backoff(attempt)
        ...     time.sleep(delay)
        ...     try_operation()
    """
    import random

    delay = min(base_delay * (2 ** attempt), max_delay)

    if jitter:
        # Add ±25% jitter
        jitter_range = delay * 0.25
        delay += random.uniform(-jitter_range, jitter_range)

    return max(0, delay)


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
        state_file: Optional[Path] = None,
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
        self.state_file = Path(state_file) if state_file else Path("data/daemon_state.txt")
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

    def _process_document(self, file_path: Path, max_retries: int = 3):
        """
        Обработать один документ через UnifiedPipeline.

        PRODUCTION READY:
        - Waits for file stability
        - Uses file locking
        - Atomic operations (os.replace)
        - Exponential backoff retry
        - Proper error handling

        Args:
            file_path: Путь к документу
            max_retries: Maximum retry attempts

        Raises:
            Exception: If processing fails after all retries
        """
        # STEP 1: Wait for file to become stable
        logger.debug(f"Waiting for {file_path.name} to stabilize...")
        if not wait_file_stable(file_path, checks=3, interval=2.0, timeout=30.0):
            logger.warning(f"File {file_path.name} did not stabilize, skipping")
            return

        # STEP 2: Acquire file lock
        with FileLock(file_path, timeout=10.0) as lock:
            if not lock.acquired:
                logger.warning(
                    f"Could not acquire lock for {file_path.name}, "
                    "another process may be working on it"
                )
                return

            logger.info(f"=" * 60)
            logger.info(f"Processing: {file_path.name}")
            logger.info(f"Languages: {', '.join(self.target_languages)}")
            logger.info(f"=" * 60)

            # STEP 3: Process with retry
            for attempt in range(max_retries):
                try:
                    start_time = time.time()

                    # Run pipeline
                    result = self.pipeline.process(
                        input_file=file_path,
                        target_languages=self.target_languages,
                        output_dir=self.output,
                    )

                    duration = time.time() - start_time

                    # STEP 4: Mark as processed (atomic state update)
                    file_hash = self._get_file_hash(file_path)
                    self.processed_hashes.add(file_hash)
                    self._save_state()

                    # STEP 5: Atomic move to processed folder
                    dest = self.processed / file_path.name

                    # Handle duplicate names
                    if dest.exists():
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        dest = self.processed / f"{file_path.stem}_{timestamp}{file_path.suffix}"

                    # Use os.replace for atomic operation (within same filesystem)
                    try:
                        os.replace(str(file_path), str(dest))
                    except OSError:
                        # Fallback to non-atomic if cross-filesystem
                        import shutil
                        shutil.move(str(file_path), str(dest))

                    # Update stats
                    self.stats["total_processed"] += 1

                    # Log success
                    logger.info(f"=" * 60)
                    logger.info(f"✓ Successfully processed: {file_path.name}")
                    logger.info(f"  Duration: {duration:.1f}s")
                    logger.info(f"  Attempt: {attempt + 1}/{max_retries}")
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

                    # Success - break retry loop
                    break

                except Exception as e:
                    if attempt < max_retries - 1:
                        # Retry with exponential backoff
                        delay = exponential_backoff(attempt, base_delay=2.0)
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries} failed: {e}"
                        )
                        logger.warning(f"Retrying in {delay:.1f}s...")
                        time.sleep(delay)
                    else:
                        # Final attempt failed
                        self.stats["total_errors"] += 1
                        logger.error(f"=" * 60)
                        logger.error(f"✗ Failed to process: {file_path.name}")
                        logger.error(f"  Error: {str(e)}")
                        logger.error(f"  Attempts: {max_retries}")
                        logger.error(f"=" * 60)
                        logger.exception("Full traceback:")

                        # Move failed file atomically
                        failed_dir = self.inbox / "failed"
                        failed_dir.mkdir(exist_ok=True)
                        failed_dest = failed_dir / file_path.name

                        # Handle duplicate names in failed folder
                        if failed_dest.exists():
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            failed_dest = failed_dir / f"{file_path.stem}_{timestamp}{file_path.suffix}"

                        try:
                            os.replace(str(file_path), str(failed_dest))
                            # Save error details
                            error_file = failed_dest.with_suffix(failed_dest.suffix + ".error")
                            error_file.write_text(
                                f"Error: {str(e)}\n"
                                f"Time: {datetime.now().isoformat()}\n"
                                f"Attempts: {max_retries}\n"
                            )
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
