import os
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional

from backend.app.modules.infrastructure_platform.logging.formatters.json_formatter import (
    JsonLogFormatter,
)

LOG_DIR = os.path.join("logs", "application")
LOG_FILE_PATH = os.path.join(LOG_DIR, "application.jsonl")


def setup_application_logging(level: int = logging.INFO):
    """Initializes centralized structured rotating file handler and console handler."""
    os.makedirs(LOG_DIR, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Avoid adding duplicate handlers on reload
    if any(isinstance(h, RotatingFileHandler) for h in root_logger.handlers):
        return

    json_formatter = JsonLogFormatter()

    # 1. Rotating File Handler (10MB per file, up to 5 backups)
    file_handler = RotatingFileHandler(
        LOG_FILE_PATH,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(json_formatter)
    file_handler.setLevel(level)
    root_logger.addHandler(file_handler)

    # 2. Console Stream Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(json_formatter)
    console_handler.setLevel(level)
    root_logger.addHandler(console_handler)


def get_structured_logger(name: str) -> logging.Logger:
    """Returns a logger pre-configured to output through the structured pipeline."""
    return logging.getLogger(name)
