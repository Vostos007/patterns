"""
KPS Automation - автоматизация обработки документов.

Модули:
- daemon: Автоматический мониторинг и обработка документов из корневой
  папки `to_translate/` с выводом готовых артефактов в `translations/`.
"""

from .daemon import DocumentDaemon

__all__ = ["DocumentDaemon"]
