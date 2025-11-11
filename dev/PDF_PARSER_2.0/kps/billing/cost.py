"""
Cost estimation for OpenAI API usage.

Provides pricing information and cost calculation utilities.
"""

from dataclasses import dataclass
from typing import Dict

# Pricing per 1M tokens (as of 2025-01-11)
# Update these when OpenAI changes pricing
PRICES_PER_1K = {
    "gpt-4.1-mini": {"in": 0.15, "out": 0.60},
    "gpt-4o-mini": {"in": 0.15, "out": 0.60},
    "gpt-4.1": {"in": 5.00, "out": 15.00},
    "gpt-4o": {"in": 2.50, "out": 10.00},
    "text-embedding-3-small": {"in": 0.02, "out": 0.00},
    "text-embedding-3-large": {"in": 0.13, "out": 0.00},
}


@dataclass
class Usage:
    """
    API usage for a single request.

    Attributes:
        model: Model name (e.g., "gpt-4o-mini")
        tokens_in: Input tokens
        tokens_out: Output tokens
    """

    model: str
    tokens_in: int
    tokens_out: int


def estimate_cost(usage: Usage) -> float:
    """
    Estimate cost in USD for API usage.

    Args:
        usage: Usage object with model and token counts

    Returns:
        Estimated cost in USD

    Example:
        >>> u = Usage(model="gpt-4o-mini", tokens_in=1000, tokens_out=500)
        >>> cost = estimate_cost(u)
        >>> print(f"${cost:.4f}")
        $0.4500
    """
    prices = PRICES_PER_1K.get(usage.model)
    if not prices:
        # Unknown model - return 0 to avoid breaking, but log warning
        import logging
        logging.warning(f"Unknown model for pricing: {usage.model}")
        return 0.0

    cost_in = (usage.tokens_in / 1000) * prices["in"]
    cost_out = (usage.tokens_out / 1000) * prices["out"]

    return cost_in + cost_out


def estimate_cost_from_tokens(
    model: str,
    tokens_in: int,
    tokens_out: int,
) -> float:
    """
    Estimate cost directly from parameters.

    Args:
        model: Model name
        tokens_in: Input tokens
        tokens_out: Output tokens

    Returns:
        Estimated cost in USD
    """
    usage = Usage(model=model, tokens_in=tokens_in, tokens_out=tokens_out)
    return estimate_cost(usage)


def get_model_pricing(model: str) -> Dict[str, float]:
    """
    Get pricing for a specific model.

    Args:
        model: Model name

    Returns:
        Dict with "in" and "out" prices per 1K tokens

    Raises:
        KeyError: If model not found
    """
    if model not in PRICES_PER_1K:
        raise KeyError(f"Unknown model: {model}. Available: {list(PRICES_PER_1K.keys())}")

    return PRICES_PER_1K[model].copy()


__all__ = [
    "PRICES_PER_1K",
    "Usage",
    "estimate_cost",
    "estimate_cost_from_tokens",
    "get_model_pricing",
]
