#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Logging Module v2.3.2 for data_masking.py

Provides structured logging with JSON and colored console output
for masking operations.

Author: Vladyslav V. Prodan
Contact: github.com/click0
License: BSD 3-Clause
Year: 2025-2026
"""

import copy
import json
import logging
import sys
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, Optional


__version__ = "2.3.2"


class JsonFormatter(logging.Formatter):
    """Formatter that outputs log records as JSON strings."""

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as a JSON object.

        Args:
            record: The log record to format.

        Returns:
            A JSON-encoded string with structured log data.
        """
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include extra data if attached to the record
        if hasattr(record, "data") and record.data is not None:
            log_entry["data"] = record.data

        # Include exception info if present
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info),
            }

        return json.dumps(log_entry, ensure_ascii=False, default=str)


class ConsoleFormatter(logging.Formatter):
    """Formatter that outputs colored log messages to the console."""

    COLORS: Dict[str, str] = {
        "DEBUG": "\033[36m",      # cyan
        "INFO": "\033[32m",       # green
        "WARNING": "\033[33m",    # yellow
        "ERROR": "\033[31m",      # red
        "CRITICAL": "\033[35m",   # magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record with colored level name.

        Args:
            record: The log record to format.

        Returns:
            A formatted string with ANSI color codes.
        """
        color = self.COLORS.get(record.levelname, self.RESET)
        levelname = f"{color}{record.levelname:<8}{self.RESET}"

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = record.getMessage()

        formatted = f"{timestamp} {levelname} {record.name} - {message}"

        # Append extra data if present
        if hasattr(record, "data") and record.data is not None:
            formatted += f" | {record.data}"

        # Append exception info if present
        if record.exc_info and record.exc_info[0] is not None:
            formatted += "\n" + "".join(
                traceback.format_exception(*record.exc_info)
            )

        return formatted


class MaskingLogger:
    """Structured logger for masking operations.

    Provides convenience methods for logging masking-specific events
    with optional structured data attached to each log record.
    """

    def __init__(
        self,
        name: str = "data_masking",
        level: str = "INFO",
        format_type: str = "console",
        log_file: Optional[str] = None,
    ) -> None:
        """Initialize the masking logger.

        Args:
            name: Logger name.
            level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
            format_type: Output format - 'console' for colored output
                         or 'json' for structured JSON.
            log_file: Optional path to a log file.
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        self.format_type = format_type

        # Internal statistics counters
        self._stats: Dict[str, int] = {
            "entities_masked": 0,
            "collisions": 0,
            "validation_warnings": 0,
            "parse_errors": 0,
            "files_processed": 0,
        }

        # Avoid adding duplicate handlers
        if not self.logger.handlers:
            self._setup_handlers(format_type, log_file)

    def _setup_handlers(
        self, format_type: str, log_file: Optional[str]
    ) -> None:
        """Configure logging handlers based on format type.

        Args:
            format_type: 'console' or 'json'.
            log_file: Optional path to a log file.
        """
        if format_type == "json":
            formatter: logging.Formatter = JsonFormatter()
        else:
            formatter = ConsoleFormatter()

        # Console handler
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # File handler (optional)
        if log_file:
            file_formatter: logging.Formatter
            if format_type == "json":
                file_formatter = JsonFormatter()
            else:
                file_formatter = logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)

    def _log_with_data(
        self,
        level: int,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        exc_info: bool = False,
    ) -> None:
        """Log a message with optional structured data.

        Args:
            level: Numeric logging level.
            message: The log message.
            data: Optional dictionary of extra data to include.
            exc_info: Whether to include exception information.
        """
        extra = {"data": data}
        self.logger.log(level, message, extra=extra, exc_info=exc_info)

    # ---- Standard log level methods ----

    def debug(
        self, message: str, data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log a debug message."""
        self._log_with_data(logging.DEBUG, message, data)

    def info(
        self, message: str, data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log an info message."""
        self._log_with_data(logging.INFO, message, data)

    def warning(
        self, message: str, data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log a warning message."""
        self._log_with_data(logging.WARNING, message, data)

    def error(
        self,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        exc_info: bool = False,
    ) -> None:
        """Log an error message."""
        self._log_with_data(logging.ERROR, message, data, exc_info=exc_info)

    def critical(
        self,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        exc_info: bool = False,
    ) -> None:
        """Log a critical message."""
        self._log_with_data(
            logging.CRITICAL, message, data, exc_info=exc_info
        )

    # ---- Specialized masking operation methods ----

    def start_masking(
        self, filename: str, options: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log the start of a masking operation.

        Args:
            filename: Name of the file being processed.
            options: Optional masking options/configuration.
        """
        data: Dict[str, Any] = {"filename": filename}
        if options:
            data["options"] = options
        self.info(f"Starting masking: {filename}", data)

    def end_masking(
        self,
        filename: str,
        entities_count: int = 0,
        elapsed: float = 0.0,
    ) -> None:
        """Log the end of a masking operation.

        Args:
            filename: Name of the file that was processed.
            entities_count: Number of entities masked.
            elapsed: Time elapsed in seconds.
        """
        self._stats["files_processed"] += 1
        data = {
            "filename": filename,
            "entities_count": entities_count,
            "elapsed_seconds": round(elapsed, 3),
        }
        self.info(f"Finished masking: {filename}", data)

    def masked_entity(
        self,
        entity_type: str,
        original: str,
        masked: str,
    ) -> None:
        """Log a single masked entity.

        Args:
            entity_type: Category of the entity (e.g. 'name', 'email').
            original: The original value (may be partially redacted).
            masked: The masked replacement value.
        """
        self._stats["entities_masked"] += 1
        data = {
            "entity_type": entity_type,
            "original": original,
            "masked": masked,
        }
        self.debug(f"Masked {entity_type}", data)

    def collision_warning(
        self, original: str, existing: str, new: str
    ) -> None:
        """Log a mapping collision warning.

        Args:
            original: The original value that caused a collision.
            existing: The existing mapped value.
            new: The new value that conflicted.
        """
        self._stats["collisions"] += 1
        data = {
            "original": original,
            "existing_mapping": existing,
            "new_mapping": new,
        }
        self.warning(f"Mapping collision for: {original}", data)

    def validation_warning(self, message: str, value: Any = None) -> None:
        """Log a validation warning.

        Args:
            message: Description of the validation issue.
            value: The value that failed validation.
        """
        self._stats["validation_warnings"] += 1
        data: Dict[str, Any] = {}
        if value is not None:
            data["value"] = value
        self.warning(message, data if data else None)

    def parse_error(
        self, message: str, text: Optional[str] = None
    ) -> None:
        """Log a parse error.

        Args:
            message: Description of the parse error.
            text: The text that could not be parsed.
        """
        self._stats["parse_errors"] += 1
        data: Dict[str, Any] = {}
        if text is not None:
            data["text"] = text
        self.error(message, data if data else None)

    def config_loaded(self, config: Dict[str, Any]) -> None:
        """Log that configuration has been loaded.

        Args:
            config: The configuration dictionary (sensitive values
                    should be redacted before passing).
        """
        self.info("Configuration loaded", {"config": config})

    def get_stats(self) -> Dict[str, int]:
        """Return a copy of the internal statistics counters.

        Returns:
            Dictionary with counts for entities_masked, collisions,
            validation_warnings, parse_errors, and files_processed.
        """
        return copy.copy(self._stats)


# ---- Module-level singleton and factory functions ----

_logger: Optional[MaskingLogger] = None


def get_logger(
    level: str = "INFO",
    format_type: str = "console",
    log_file: Optional[str] = None,
    reinit: bool = False,
) -> MaskingLogger:
    """Get or create the global MaskingLogger instance.

    Args:
        level: Logging level string.
        format_type: 'console' or 'json'.
        log_file: Optional path to a log file.
        reinit: If True, force creation of a new logger instance.

    Returns:
        The global MaskingLogger instance.
    """
    global _logger
    if _logger is None or reinit:
        _logger = MaskingLogger(
            name="data_masking",
            level=level,
            format_type=format_type,
            log_file=log_file,
        )
    return _logger


def setup_logging(
    level: str = "INFO",
    format_type: str = "console",
    log_file: Optional[str] = None,
) -> MaskingLogger:
    """Set up and return a configured MaskingLogger.

    Convenience wrapper around get_logger for backward compatibility.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        format_type: Output format - 'console' or 'json'.
        log_file: Optional path to log file.

    Returns:
        Configured MaskingLogger instance.
    """
    return get_logger(
        level=level,
        format_type=format_type,
        log_file=log_file,
        reinit=True,
    )
