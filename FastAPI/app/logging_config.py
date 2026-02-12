import logging
import sys


def setup_logging(level: int | str | None = None) -> None:
    """Configure root logger for the app."""
    if level is None:
        try:
            from app.config import settings
            level = getattr(logging, settings.log_level.upper(), logging.INFO)
        except Exception:
            level = logging.INFO
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt))
    root = logging.getLogger()
    root.setLevel(level)
    if root.handlers:
        root.handlers.clear()
    root.addHandler(handler)
    # Reduce noise from third-party libs
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
