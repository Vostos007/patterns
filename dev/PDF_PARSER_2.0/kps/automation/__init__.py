"""
KPS Automation - автоматизация обработки документов.

Модули:
- daemon: Автоматический мониторинг и обработка документов из inbox/
"""

from .daemon import DocumentDaemon

__all__ = ["DocumentDaemon"]
