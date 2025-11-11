"""
Search module for hybrid retrieval and context compression.

Provides:
- Hybrid search (BM25 + vector similarity)
- Context compression for LLM prompts
"""

from .hybrid import hybrid_search
from .snippets import compress_segments

__all__ = [
    "hybrid_search",
    "compress_segments",
]
