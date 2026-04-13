from __future__ import annotations

import logging
from typing import Any
from pythonjsonlogger import jsonlogger


def setup_logger(environment: str = "development", log_level: str = "INFO") -> None:
    normalized_environment = (environment or "development").strip().lower()

    is_production = normalized_environment in {"prod", "production"}
    effective_level = logging.ERROR if is_production else getattr(logging, str(log_level).upper(), logging.INFO)

    handler = logging.StreamHandler()

    if is_production:
        formatter = jsonlogger.JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s %(pathname)s %(lineno)d",
            rename_fields={"levelname": "level", "asctime": "timestamp"},
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(name)s - %(message)s (%(filename)s:%(lineno)d)",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = []
    root_logger.setLevel(effective_level)
    root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def safe_exc_info(exc: BaseException) -> dict[str, Any]:
    return {
        "type": exc.__class__.__name__,
        "message": str(exc),
    }
