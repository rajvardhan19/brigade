"""Time source. Use now() everywhere instead of time.time() so tests can move time."""
import time

_offset = 0.0


def now() -> float:
    return time.time() + _offset


def advance(seconds: float) -> None:
    """Move the clock forward. Tests only."""
    global _offset
    _offset += seconds


def reset() -> None:
    global _offset
    _offset = 0.0
