"""Thin wrapper around OpenAI's embeddings API with batching and retries."""

from __future__ import annotations

import logging
import time
from typing import Iterable, List, Optional, Sequence

try:
    from openai import OpenAI  # type: ignore
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore


logger = logging.getLogger(__name__)


class EmbeddingsClient:
    """Create embeddings with chunking, caching, and retry awareness."""

    def __init__(
        self,
        model: str,
        max_batch: int = 16,
        max_retries: int = 2,
        retry_base_seconds: float = 1.0,
        timeout: float = 30.0,
        client=None,
    ) -> None:
        if max_batch <= 0:
            raise ValueError("max_batch must be positive")

        self.model = model
        self.max_batch = max_batch
        self.max_retries = max_retries
        self.retry_base_seconds = retry_base_seconds
        self._client = client or self._default_client(timeout)

    def _default_client(self, timeout: float):
        if OpenAI is None:  # pragma: no cover
            raise RuntimeError(
                "openai package is not installed. Install openai>=1.0 to use embeddings."
            )
        return OpenAI(timeout=timeout)

    @property
    def client(self):  # pragma: no cover - getter for dependency injection visibility
        return self._client

    def create_vectors(self, texts: Sequence[str]) -> List[List[float]]:
        """Generate embeddings for the provided texts."""

        results: List[List[float]] = []
        batch: List[str] = []

        for text in texts:
            batch.append(text)
            if len(batch) >= self.max_batch:
                results.extend(self._fetch_batch(batch))
                batch = []

        if batch:
            results.extend(self._fetch_batch(batch))

        return results

    # ------------------------------------------------------------------
    def _fetch_batch(self, batch: List[str]) -> Iterable[List[float]]:
        attempt = 0
        while True:
            attempt += 1
            try:
                response = self._client.embeddings.create(
                    model=self.model,
                    input=batch,
                )
                return [item.embedding for item in response.data]
            except Exception as exc:  # pylint: disable=broad-except
                if attempt > self.max_retries or not self._is_retryable(exc):
                    logger.warning("Embedding batch failed permanently: %s", exc)
                    raise
                sleep_s = self.retry_base_seconds * attempt
                logger.info(
                    "Embedding batch hit retryable error (attempt %s/%s), sleeping %.1fs",
                    attempt,
                    self.max_retries,
                    sleep_s,
                )
                time.sleep(sleep_s)

    def _is_retryable(self, exc: Exception) -> bool:
        status = getattr(exc, "status", None) or getattr(exc, "status_code", None)
        if status == 429:
            return True
        message = str(exc).lower()
        return "rate limit" in message or "temporarily unavailable" in message


__all__ = ["EmbeddingsClient"]
