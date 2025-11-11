"""
Interoperability module for industry standards.

Supports:
- TBX (TermBase eXchange, ISO 30042) - terminology import/export
- TMX (Translation Memory eXchange) - translation memory import/export
"""

from .tbx import import_tbx_to_db, export_glossary_to_tbx
from .tmx import import_tmx_to_db, export_translations_to_tmx

__all__ = [
    "import_tbx_to_db",
    "export_glossary_to_tbx",
    "import_tmx_to_db",
    "export_translations_to_tmx",
]
