"""Rule-based, analysis-only XAUUSD market analysis engine.

This package deliberately does not connect to a broker or place trades.
"""

from .signal import Signal, generate_signal

__all__ = ["Signal", "generate_signal"]