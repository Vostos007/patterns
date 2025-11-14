"""
Translation orchestrator for KPS v2.0.

Handles OpenAI API calls with glossary integration and placeholder protection.
Enhanced from PDF_parser with multi-language batch support.

Production Features:
- Configurable batch processing
- Exponential backoff retry logic
- Progress tracking with callbacks
- Token counting and cost estimation
- Glossary integration with smart term selection
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

try:  # pragma: no cover - optional dependency
    import openai
    from openai import OpenAIError, RateLimitError
except ImportError:  # pragma: no cover
    openai = None
    OpenAIError = Exception  # type: ignore
    RateLimitError = Exception  # type: ignore

try:  # pragma: no cover - optional dependency
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None  # type: ignore

from ..core.placeholders import decode_placeholders, encode_placeholders

# Import term validator for glossary compliance
try:
    from .term_validator import TermValidator, TermRule, Violation
except ImportError:
    TermValidator = None  # type: ignore
    TermRule = None  # type: ignore
    Violation = None  # type: ignore


logger = logging.getLogger(__name__)


def _candidate_env_paths() -> List[Path]:
    paths: List[Path] = []

    override = os.getenv("KPS_ENV_FILE")
    if override:
        paths.append(Path(override).expanduser())

    module_path = Path(__file__).resolve()
    for ancestor in module_path.parents:
        candidate = ancestor / ".env"
        if candidate not in paths:
            paths.append(candidate)

    cwd_candidate = Path.cwd() / ".env"
    if cwd_candidate not in paths:
        paths.append(cwd_candidate)

    return paths


_DOTENV_LOADED = False


def _ensure_env_loaded() -> None:
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return

    if os.getenv("OPENAI_API_KEY"):
        _DOTENV_LOADED = True
        return

    if load_dotenv is not None:
        for path in _candidate_env_paths():
            if path.is_file():
                load_dotenv(dotenv_path=path)
                break

    _DOTENV_LOADED = True


@dataclass
class TranslationSegment:
    """Single segment to translate."""

    segment_id: str  # e.g., "p.materials.001.seg0"
    text: str
    placeholders: Dict[str, str]  # Encoded placeholders
    doc_ref: Optional[str] = None


@dataclass
class TranslationResult:
    """Result of translation for one target language."""

    target_language: str  # "en" or "fr"
    segments: List[str]  # Translated texts, same order as input


@dataclass
class BatchTranslationResult:
    """Result of batch translation to multiple languages."""

    detected_source_language: str
    translations: Dict[str, TranslationResult]  # {"en": TranslationResult, "fr": ...}
    total_cost: float = 0.0  # Total estimated cost in USD
    total_input_tokens: int = 0
    total_output_tokens: int = 0


@dataclass
class TranslationProgress:
    """Progress tracking for batch translation."""

    current_batch: int
    total_batches: int
    segments_completed: int
    total_segments: int
    current_language: str
    estimated_cost: float
    elapsed_time: float = 0.0
    estimated_time_remaining: float = 0.0


class TranslationOrchestrator:
    """
    Orchestrates translation with OpenAI API.

    Features:
    - Auto-detects source language
    - Batch translation to multiple target languages
    - Glossary context injection
    - Placeholder encoding/decoding
    - Newline preservation
    - Production batch processing with configurable limits
    - Retry logic with exponential backoff
    - Progress tracking and cost estimation
    """

    # Pricing per 1M tokens (as of 2025)
    MODEL_PRICING = {
        "gpt-5-nano": {"input": 0.15, "output": 0.60},  # placeholder pricing
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    }

    def __init__(
        self,
        model: str = "gpt-5-nano",
        fallback_model: Optional[str] = "gpt-4o-mini",
        api_key: Optional[str] = None,
        max_batch_size: Optional[int] = 10,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        term_validator: Optional["TermValidator"] = None,
        strict_glossary: bool = False,
    ):
        """
        Initialize orchestrator.

        Args:
            model: OpenAI model to use
            api_key: Optional API key. If None, uses OPENAI_API_KEY env var.
            max_batch_size: Maximum segments per batch. ``None`` means no limit.
            max_retries: Maximum retry attempts (default: 3)
            retry_delay: Initial retry delay in seconds (default: 1.0)
            term_validator: Optional TermValidator for glossary compliance (P2)
            strict_glossary: If True, enforce 100% glossary compliance (default: False)
        """
        self.model = model
        self.fallback_model = fallback_model if fallback_model != model else None
        self.max_batch_size = max_batch_size
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.term_validator = term_validator
        self.strict_glossary = strict_glossary

        _ensure_env_loaded()
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if openai is not None and self.api_key:
            openai.api_key = self.api_key

        # Token counting cache
        self._token_cache: Dict[str, int] = {}

        # Metrics for term validation
        self.validation_metrics = {
            "violations_detected": 0,
            "retries_for_terms": 0,
            "enforcements": 0,
        }

    def _ensure_client(self) -> None:
        if openai is None:
            raise RuntimeError(
                "OpenAI client is not available. Install the openai package or provide a mock."
            )
        if not (getattr(openai, "api_key", None) or self.api_key):
            raise RuntimeError(
                "OpenAI API key is not configured. Set OPENAI_API_KEY in your environment or pass api_key to TranslationOrchestrator."
            )

    def _chat_completion(self, *, messages, temperature, max_tokens, operation: str, **kwargs):
        def invoke(model_name: str):
            request_payload = {
                "model": model_name,
                "messages": messages,
                **kwargs,
            }

            temp_value = temperature
            if model_name.startswith("gpt-5"):
                temp_value = None  # model enforces default temperature
            if temp_value is not None:
                request_payload["temperature"] = temp_value
            if max_tokens is not None:
                token_param = self._token_param_name(model_name)
                request_payload[token_param] = max_tokens

            return openai.chat.completions.create(**request_payload)

        return self._invoke_with_fallback(invoke, operation)

    def _token_param_name(self, model_name: str) -> str:
        """Map model names to the correct token parameter."""

        if model_name.startswith("gpt-5"):
            return "max_completion_tokens"
        return "max_tokens"

    def _simple_language_guess(self, sample_text: str) -> str:
        """Fallback heuristic for language detection."""

        if re.search(r"[а-яё]", sample_text.lower()):
            return "ru"
        return "en"

    def _invoke_with_fallback(self, builder: Callable[[str], object], operation: str):
        models_to_try = [self.model]
        if self.fallback_model and self.fallback_model not in models_to_try:
            models_to_try.append(self.fallback_model)

        last_exc: Optional[Exception] = None
        for model_name in models_to_try:
            try:
                response = builder(model_name)
                setattr(response, "_kps_model_used", model_name)
                return response
            except Exception as exc:  # pragma: no cover - network failures
                last_exc = exc
                logger.warning(
                    "Model %s failed during %s: %s",
                    model_name,
                    operation,
                    exc,
                )
        if last_exc:
            raise last_exc
        raise RuntimeError("No model available for operation")

    def detect_language(self, sample_text: str) -> str:
        """
        Auto-detect source language of text.

        Args:
            sample_text: Sample text (first few segments)

        Returns:
            Language code (e.g., "ru", "en", "de")
        """
        self._ensure_client()

        prompt = f"""Detect the language of this text and respond with ONLY the ISO 639-1 language code (e.g., "ru", "en", "fr", "de").

Text:
{sample_text[:500]}

Language code:"""

        response = self._chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=10,
            operation="language_detection",
        )

        detected = response.choices[0].message.content.strip().lower()
        if not detected or len(detected) != 2:
            detected = self._simple_language_guess(sample_text)
        return detected or "ru"

    def translate_batch(
        self,
        segments: List[TranslationSegment],
        target_languages: List[str],
        glossary_context: Optional[str] = None,
    ) -> BatchTranslationResult:
        """
        Translate segments to multiple target languages.

        Args:
            segments: List of segments to translate
            target_languages: Target language codes (e.g., ["en", "fr"])
            glossary_context: Optional glossary context for prompt

        Returns:
            BatchTranslationResult with translations for each language
        """
        if not segments:
            return BatchTranslationResult(
                detected_source_language="unknown",
                translations={},
            )

        self._ensure_client()

        # Detect source language
        sample = " ".join([s.text for s in segments[:5]])
        source_lang = self.detect_language(sample)

        # Deduplicate targets while preserving order
        seen = set()
        deduped_targets: List[str] = []
        for lang in target_languages:
            key = lang.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped_targets.append(lang)
        target_languages = deduped_targets

        batches = self._split_into_batches(segments, self.max_batch_size)
        translations: Dict[str, TranslationResult] = {}
        total_input_tokens = 0
        total_output_tokens = 0
        total_cost = 0.0

        for target_lang in target_languages:
            translated_segments: List[str] = []

            for batch in batches:
                translated_batch, input_tokens, output_tokens, batch_model = self._retry_with_backoff(
                    lambda b=batch: self._translate_batch_with_tokens(
                        segments=b,
                        source_lang=source_lang,
                        target_lang=target_lang,
                        glossary_context=glossary_context,
                    )
                )

                translated_segments.extend(translated_batch)
                total_input_tokens += input_tokens
                total_output_tokens += output_tokens
                total_cost += self._calculate_cost(input_tokens, output_tokens, batch_model)

            if self.term_validator:
                translated_segments = self._validate_and_enforce_terms(
                    segments=segments,
                    translated_segments=translated_segments,
                    source_lang=source_lang,
                    target_lang=target_lang,
                )

            translations[target_lang] = TranslationResult(
                target_language=target_lang,
                segments=translated_segments,
            )

        return BatchTranslationResult(
            detected_source_language=source_lang,
            translations=translations,
            total_cost=total_cost,
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
        )

    def _translate_to_language(
        self,
        segments: List[TranslationSegment],
        source_lang: str,
        target_lang: str,
        glossary_context: Optional[str],
    ) -> TranslationResult:
        """
        Translate segments to a single target language.

        Args:
            segments: Segments to translate
            source_lang: Source language code
            target_lang: Target language code
            glossary_context: Optional glossary context

        Returns:
            TranslationResult with translated segments
        """
        self._ensure_client()

        # Build prompt
        system_prompt = self._build_system_prompt(
            source_lang=source_lang,
            target_lang=target_lang,
            glossary_context=glossary_context,
        )

        # Prepare segments for translation
        segments_text = "\n---\n".join([s.text for s in segments])

        user_prompt = f"""Translate the following segments from {source_lang} to {target_lang}.

IMPORTANT:
- Preserve ALL newlines (\\n) EXACTLY as they appear
- Do NOT translate placeholders like <ph id="..." />
- Separate translated segments with "---" on a new line
- Maintain original formatting and structure
- Respond ONLY with the translated segments; do not add commentary or explanations

Segments:
{segments_text}

Translated segments:"""

        # Call OpenAI API
        response = self._chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=8000,
            operation=f"translation:{target_lang}",
        )

        # Parse response using newline-delimited separators to avoid
        # splitting Markdown tables that contain "| --- |" in header rows.
        translated_text = response.choices[0].message.content
        translated_segments = self._split_translated_segments(
            translated_text,
            expected_count=len(segments),
            source_segments=segments,
        )

        # P2: Validate glossary compliance if term_validator is configured
        if self.term_validator:
            translated_segments = self._validate_and_enforce_terms(
                segments=segments,
                translated_segments=translated_segments,
                source_lang=source_lang,
                target_lang=target_lang,
            )

        return TranslationResult(
            target_language=target_lang,
            segments=translated_segments,
        )

    def _build_system_prompt(
        self,
        source_lang: str,
        target_lang: str,
        glossary_context: Optional[str],
    ) -> str:
        """Build system prompt with glossary context."""
        base_prompt = f"""You are a professional translator specializing in knitting patterns and craft documentation.

Task: Translate text from {source_lang} to {target_lang}.

Critical rules:
1. Preserve ALL newlines (\\n) exactly as they appear
2. Do NOT translate placeholders: <ph id="..." />
3. Maintain original formatting (lists, tables, headings, inline math)
4. Output MUST be entirely in {target_lang}. Replace any {source_lang} or Cyrillic words with their {target_lang} equivalents (units/numbers may stay numeric)
5. Translate table headers, abbreviations, measurements, and descriptive phrases unless the glossary explicitly marks them as "do not translate"
6. Use glossary terminology when provided and stay consistent throughout the document"""

        if glossary_context:
            base_prompt += f"\n\n{glossary_context}"

        return base_prompt

    def translate_with_batching(
        self,
        segments: List[TranslationSegment],
        target_languages: List[str],
        glossary_manager=None,
        progress_callback: Optional[Callable[[TranslationProgress], None]] = None,
    ) -> BatchTranslationResult:
        """
        Translate segments with production batch processing.

        Features:
        - Splits into batches (max_batch_size segments per batch)
        - Retry logic with exponential backoff
        - Progress tracking via callback
        - Token counting and cost estimation
        - Smart glossary term selection

        Args:
            segments: List of segments to translate
            target_languages: Target language codes (e.g., ["en", "fr"])
            glossary_manager: Optional GlossaryManager for term selection
            progress_callback: Optional callback for progress updates

        Returns:
            BatchTranslationResult with translations and cost information

        Example:
            >>> def progress(p: TranslationProgress):
            ...     print(f"Batch {p.current_batch}/{p.total_batches}")
            ...     print(f"Cost: ${p.estimated_cost:.4f}")
            >>> result = orchestrator.translate_with_batching(
            ...     segments=segments,
            ...     target_languages=["en", "fr"],
            ...     glossary_manager=glossary,
            ...     progress_callback=progress
            ... )
        """
        if not segments:
            return BatchTranslationResult(
                detected_source_language="unknown",
                translations={},
            )

        start_time = time.time()

        # Detect source language
        sample = " ".join([s.text for s in segments[:5]])
        source_lang = self.detect_language(sample)

        # Remove source language from targets
        target_languages = [
            lang for lang in target_languages if lang.lower() != source_lang.lower()
        ]

        # Build glossary context if manager provided
        glossary_context = None
        if glossary_manager:
            glossary_context = self._build_glossary_context(
                segments=segments,
                glossary_manager=glossary_manager,
                source_lang=source_lang,
                target_lang=target_languages[0] if target_languages else "en",
            )

        # Split into batches
        batches = self._split_into_batches(segments, self.max_batch_size)
        total_batches = len(batches) * len(target_languages)

        # Track costs
        total_input_tokens = 0
        total_output_tokens = 0
        total_cost = 0.0

        # Translate to each target language
        translations: Dict[str, TranslationResult] = {}
        batch_counter = 0

        for target_lang in target_languages:
            all_translated_segments = []

            for batch_idx, batch in enumerate(batches):
                batch_counter += 1

                # Translate batch with retry
                translated_batch, input_tokens, output_tokens, batch_model = self._retry_with_backoff(
                    lambda: self._translate_batch_with_tokens(
                        segments=batch,
                        source_lang=source_lang,
                        target_lang=target_lang,
                        glossary_context=glossary_context,
                    )
                )

                all_translated_segments.extend(translated_batch)

                # Update cost tracking
                total_input_tokens += input_tokens
                total_output_tokens += output_tokens
                batch_cost = self._calculate_cost(input_tokens, output_tokens, batch_model)
                total_cost += batch_cost

                # Progress callback
                if progress_callback:
                    elapsed = time.time() - start_time
                    avg_time_per_batch = elapsed / batch_counter if batch_counter > 0 else 0
                    remaining_batches = total_batches - batch_counter
                    estimated_remaining = avg_time_per_batch * remaining_batches

                    progress = TranslationProgress(
                        current_batch=batch_counter,
                        total_batches=total_batches,
                        segments_completed=len(all_translated_segments),
                        total_segments=len(segments) * len(target_languages),
                        current_language=target_lang,
                        estimated_cost=total_cost,
                        elapsed_time=elapsed,
                        estimated_time_remaining=estimated_remaining,
                    )
                    progress_callback(progress)

            if self.term_validator:
                all_translated_segments = self._validate_and_enforce_terms(
                    segments=segments,
                    translated_segments=all_translated_segments,
                    source_lang=source_lang,
                    target_lang=target_lang,
                )

            translations[target_lang] = TranslationResult(
                target_language=target_lang,
                segments=all_translated_segments,
            )

        return BatchTranslationResult(
            detected_source_language=source_lang,
            translations=translations,
            total_cost=total_cost,
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
        )

    def _split_into_batches(
        self, segments: List[TranslationSegment], max_batch_size: Optional[int]
    ) -> List[List[TranslationSegment]]:
        """
        Split segments into batches.

        Args:
            segments: Segments to split
            max_batch_size: Maximum segments per batch

        Returns:
            List of segment batches
        """
        if not segments:
            return []

        if not max_batch_size or max_batch_size <= 0:
            return [segments]

        batches: List[List[TranslationSegment]] = []
        for i in range(0, len(segments), max_batch_size):
            batch = segments[i : i + max_batch_size]
            batches.append(batch)
        return batches

    def _retry_with_backoff(self, func: Callable, max_retries: Optional[int] = None):
        """
        Retry function with exponential backoff.

        Handles:
        - RateLimitError (429): Exponential backoff
        - Transient errors (500, 502, 503): Retry
        - Other errors: Raise immediately

        Args:
            func: Function to retry
            max_retries: Maximum retry attempts (uses self.max_retries if None)

        Returns:
            Function result

        Raises:
            OpenAIError: If all retries exhausted
        """
        max_retries = max_retries or self.max_retries
        delay = self.retry_delay

        for attempt in range(max_retries):
            try:
                return func()
            except RateLimitError as e:
                if attempt == max_retries - 1:
                    raise
                print(
                    f"Rate limit hit. Retrying in {delay:.1f}s (attempt {attempt + 1}/{max_retries})"
                )
                time.sleep(delay)
                delay *= 2  # Exponential backoff
            except OpenAIError as e:
                error_str = str(e)
                # Retry on transient errors
                if any(code in error_str for code in ["500", "502", "503"]):
                    if attempt == max_retries - 1:
                        raise
                    print(
                        f"Transient error: {e}. Retrying in {delay:.1f}s (attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(delay)
                    delay *= 2
                else:
                    # Non-retryable error
                    raise

        # Should not reach here
        raise OpenAIError("Max retries exhausted")

    def _translate_batch_with_tokens(
        self,
        segments: List[TranslationSegment],
        source_lang: str,
        target_lang: str,
        glossary_context: Optional[str],
    ) -> tuple[List[str], int, int, str]:
        """
        Translate batch and return token counts.

        Args:
            segments: Segments to translate
            source_lang: Source language code
            target_lang: Target language code
            glossary_context: Optional glossary context

        Returns:
            Tuple of (translated_segments, input_tokens, output_tokens)
        """
        # Build prompt
        system_prompt = self._build_system_prompt(
            source_lang=source_lang,
            target_lang=target_lang,
            glossary_context=glossary_context,
        )

        segments_text = "\n---\n".join([s.text for s in segments])

        user_prompt = f"""Translate the following segments from {source_lang} to {target_lang}.

IMPORTANT:
- Preserve ALL newlines (\\n) EXACTLY as they appear
- Do NOT translate placeholders like <ph id="..." />
- Separate translated segments with "---" on a new line
- Maintain original formatting and structure
- Respond ONLY with the translated segments; do not add commentary or explanations

Segments:
{segments_text}

Translated segments:"""

        # Call OpenAI API
        response = self._chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=8000,
            operation=f"translation_batch:{target_lang}",
        )
        response_model = getattr(response, "_kps_model_used", getattr(response, "model", self.model))

        # Extract token counts from response (some tests omit usage)
        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
        output_tokens = getattr(usage, "completion_tokens", 0) if usage else 0

        if not isinstance(input_tokens, int):
            input_tokens = 0
        if not isinstance(output_tokens, int):
            output_tokens = 0

        # Parse response
        translated_text = response.choices[0].message.content
        translated_segments = self._split_translated_segments(
            translated_text,
            expected_count=len(segments),
            source_segments=segments,
        )

        return translated_segments, input_tokens, output_tokens, response_model

    def _split_translated_segments(
        self,
        translated_text: Optional[str],
        expected_count: int,
        source_segments: Optional[List[TranslationSegment]] = None,
    ) -> List[str]:
        """Split translated output using dedicated delimiter lines."""

        if expected_count <= 0:
            return []

        text = (translated_text or "").strip("\n")
        if not text:
            return [""] * expected_count

        segments: List[str] = []
        current_lines: List[str] = []

        for line in text.splitlines():
            if line.strip() == "---":
                segments.append("\n".join(current_lines).strip())
                current_lines = []
            else:
                current_lines.append(line)

        segments.append("\n".join(current_lines).strip())

        # Remove trailing empties caused by a terminal delimiter when we already
        # collected enough segments.
        while len(segments) > expected_count and segments and segments[-1] == "":
            segments.pop()

        if len(segments) == expected_count:
            return segments

        if len(segments) < expected_count:
            segments.extend([""] * (expected_count - len(segments)))
        else:
            overflow = segments[expected_count - 1 :]
            merged = "\n---\n".join(part for part in overflow if part)
            segments = segments[: expected_count - 1] + [merged]

        if len(segments) == expected_count:
            return segments

        if source_segments is not None:
            return [seg.text for seg in source_segments]

        segments.extend([""] * max(0, expected_count - len(segments)))
        return segments[:expected_count]

    def _count_tokens(self, text: str, model: str) -> int:
        """
        Estimate token count for text.

        Uses simple heuristic: ~4 characters per token for most models.
        For production, consider using tiktoken library for exact counting.

        Args:
            text: Text to count tokens for
            model: Model name

        Returns:
            Estimated token count
        """
        # Check cache
        cache_key = f"{model}:{hash(text)}"
        if cache_key in self._token_cache:
            return self._token_cache[cache_key]

        # Simple heuristic: 4 chars per token
        # For Cyrillic/Asian languages, adjust slightly
        estimated_tokens = math.ceil(len(text) / 4)

        # Cache result
        self._token_cache[cache_key] = estimated_tokens

        return estimated_tokens

    def _calculate_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        """
        Calculate estimated cost for API call.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            model: Model name

        Returns:
            Estimated cost in USD
        """
        pricing = self.MODEL_PRICING.get(model, self.MODEL_PRICING["gpt-4o-mini"])

        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]

        return input_cost + output_cost

    def _build_glossary_context(
        self,
        segments: List[TranslationSegment],
        glossary_manager,
        source_lang: str,
        target_lang: str,
    ) -> str:
        """
        Build glossary context with smart term selection.

        Args:
            segments: Segments to translate
            glossary_manager: GlossaryManager instance
            source_lang: Source language code
            target_lang: Target language code

        Returns:
            Formatted glossary context string
        """
        # Import selector here to avoid circular dependency
        from .glossary.selector import select_glossary_terms

        # Extract all text from segments
        all_text = " ".join([s.text for s in segments])

        # Split into terms (simple whitespace split)
        terms = all_text.split()

        # Get all glossary entries as dicts
        glossary_entries = []
        for entry in glossary_manager.get_all_entries():
            glossary_entries.append(
                {
                    "key": entry.key,
                    source_lang: entry.ru if source_lang == "ru" else getattr(entry, source_lang),
                    target_lang: entry.en if target_lang == "en" else getattr(entry, target_lang),
                    "category": entry.category,
                    "description": entry.description,
                }
            )

        # Select relevant terms (max 50)
        selected_dicts = select_glossary_terms(
            terms=terms,
            glossary_entries=glossary_entries,
            source_lang=source_lang,
            max_terms=50,
        )

        # Convert back to GlossaryEntry objects
        from .glossary.manager import GlossaryEntry

        selected_entries = []
        for d in selected_dicts:
            entry = GlossaryEntry(
                key=d["key"],
                ru=d.get("ru", ""),
                en=d.get("en", ""),
                fr=d.get("fr", ""),
                category=d.get("category", "term"),
                description=d.get("description"),
            )
            selected_entries.append(entry)

        # Build context string
        return glossary_manager.build_context_for_prompt(
            source_lang=source_lang,
            target_lang=target_lang,
            selected_entries=selected_entries,
        )

    def _validate_and_enforce_terms(
        self,
        segments: List[TranslationSegment],
        translated_segments: List[str],
        source_lang: str,
        target_lang: str,
    ) -> List[str]:
        """
        Validate and enforce glossary term compliance (P2).

        Steps:
        1. Validate each segment pair for term violations
        2. If violations found, log them and update metrics
        3. Enforce terms using term_validator.enforce()

        Args:
            segments: Original source segments
            translated_segments: Translated segments
            source_lang: Source language code
            target_lang: Target language code

        Returns:
            Corrected translated segments with enforced terms
        """
        if not self.term_validator:
            return translated_segments

        corrected_segments: List[str] = []
        total_violations = 0

        for idx, (src_seg, tgt_text) in enumerate(zip(segments, translated_segments)):
            violations = self.term_validator.validate(
                src_text=src_seg.text,
                tgt_text=tgt_text,
                src_lang=source_lang,
                tgt_lang=target_lang,
            )

            if violations:
                total_violations += len(violations)
                if self.term_validator and self.strict_glossary:
                    structured_translation = self._translate_with_structured_outputs(
                        segment=src_seg,
                        source_lang=source_lang,
                        target_lang=target_lang,
                        rules=[violation.rule for violation in violations if violation.rule],
                    )
                else:
                    structured_translation = None

                corrected_text = structured_translation or tgt_text
                corrected_text = self.term_validator.enforce(
                    src_text=src_seg.text,
                    tgt_text=corrected_text,
                    src_lang=source_lang,
                    tgt_lang=target_lang,
                    fix_mode="replace",
                )
            else:
                corrected_text = tgt_text

            corrected_segments.append(corrected_text)

        if total_violations:
            logger.info(
                "Term validation corrected %s violations for %s segments",
                total_violations,
                len(segments),
            )

        return corrected_segments

    def translate_segments_strict(
        self,
        segments: List[TranslationSegment],
        source_lang: str,
        target_lang: str,
        glossary_context: Optional[str],
    ) -> List[str]:
        """Translate segments with explicit reminder to avoid source language."""
        if not segments:
            return []

        system_prompt = self._build_system_prompt(
            source_lang=source_lang,
            target_lang=target_lang,
            glossary_context=glossary_context,
        )
        extra_notice = (
            f"The output MUST be entirely in {target_lang}."
            f" Replace any {source_lang} or Cyrillic words with {target_lang} equivalents."
        )
        segments_text = "\n---\n".join([s.text for s in segments])

        user_prompt = f"""Translate the following segments from {source_lang} to {target_lang}.

IMPORTANT:
- Preserve ALL newlines (\\n) EXACTLY as they appear
- Do NOT translate placeholders like <ph id=\"...\" />
- Separate translated segments with \"---\" on a new line
- Maintain original formatting and structure
- Respond ONLY with the translated segments; do not add commentary or explanations
- {extra_notice}

Segments:
{segments_text}

Translated segments:"""

        response = self._chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=4000,
            operation=f"translation_strict:{target_lang}",
        )
        translated_text = response.choices[0].message.content
        translated_segments = [s.strip() for s in translated_text.split("---")]
        if len(translated_segments) != len(segments):
            translated_segments = [s.text for s in segments]
        return translated_segments


    def _translate_with_structured_outputs(
        self,
        segment: TranslationSegment,
        source_lang: str,
        target_lang: str,
        rules: List[TermRule],
    ) -> Optional[str]:
        """Retry translation using structured outputs to guarantee glossary terms."""

        if openai is None:
            return None

        if self.term_validator and rules:
            rules_text = self.term_validator.format_rules_for_prompt(rules)
        else:
            rules_text = (
                f"Ensure the translation uses proper knitting terminology and stays in {target_lang}."
            )

        system_prompt = (
            "You are a compliance-focused translator. "
            "Return STRICT JSON with a 'translation' field that satisfies all glossary instructions."
        )
        payload = {
            "source_language": source_lang,
            "target_language": target_lang,
            "source_text": segment.text,
            "instructions": rules_text,
        }

        try:
            response = self._chat_completion(
                temperature=0.0,
                max_tokens=2048,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "translation_response",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "translation": {"type": "string"}
                            },
                            "required": ["translation"],
                            "additionalProperties": False,
                        },
                        "strict": True,
                    },
                },
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": json.dumps(payload, ensure_ascii=False),
                    },
                ],
                operation=f"structured_retry:{target_lang}",
            )
            content = response.choices[0].message.content
            data = json.loads(content)
            translation = data.get("translation") or data.get("text")
            return translation.strip() if translation else None
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Structured translation retry failed: %s", exc)
            return None

    def _looks_like_source_language(self, text: str, source_lang: str) -> bool:
        if not text:
            return False
        if source_lang.lower().startswith("ru"):
            return bool(re.search(r"[а-яё]", text.lower()))
        return False


__all__ = [
    "TranslationOrchestrator",
    "TranslationSegment",
    "TranslationResult",
    "BatchTranslationResult",
    "TranslationProgress",
]
