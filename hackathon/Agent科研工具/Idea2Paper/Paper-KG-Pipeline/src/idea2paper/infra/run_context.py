from contextvars import ContextVar
from typing import Optional

from .run_logger import RunLogger

current_logger: ContextVar[Optional[RunLogger]] = ContextVar("current_logger", default=None)


def set_logger(logger: RunLogger):
    """Set current run logger and return token for reset."""
    return current_logger.set(logger)


def reset_logger(token):
    """Reset logger using token returned by set_logger."""
    current_logger.reset(token)


def get_logger() -> Optional[RunLogger]:
    """Get current run logger (or None)."""
    return current_logger.get()
