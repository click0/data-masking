#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Tests for modules/masking_logger.py"""

import json
import logging
import os
import tempfile
import pytest

from modules.masking_logger import (
    JsonFormatter,
    ConsoleFormatter,
    MaskingLogger,
    setup_logging,
)


@pytest.fixture(autouse=True)
def _clean_loggers():
    """Remove handlers added during tests to avoid side effects."""
    yield
    for name in ("test_masking", "data_masking", "test_json", "test_console"):
        logger = logging.getLogger(name)
        logger.handlers.clear()


class TestJsonFormatter:
    """Tests for JsonFormatter."""

    def test_basic_format(self):
        fmt = JsonFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="hello %s", args=("world",), exc_info=None,
        )
        result = fmt.format(record)
        parsed = json.loads(result)
        assert parsed["level"] == "INFO"
        assert parsed["message"] == "hello world"
        assert "timestamp" in parsed

    def test_exception_info(self):
        fmt = JsonFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()
        record = logging.LogRecord(
            name="test", level=logging.ERROR, pathname="", lineno=0,
            msg="error occurred", args=(), exc_info=exc_info,
        )
        result = fmt.format(record)
        parsed = json.loads(result)
        assert "exception" in parsed
        assert parsed["exception"]["type"] == "ValueError"
        assert "test error" in parsed["exception"]["message"]

    def test_extra_data(self):
        fmt = JsonFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="with data", args=(), exc_info=None,
        )
        record.data = {"key": "value"}
        result = fmt.format(record)
        parsed = json.loads(result)
        assert parsed["data"] == {"key": "value"}


class TestConsoleFormatter:
    """Tests for ConsoleFormatter."""

    def test_basic_format(self):
        fmt = ConsoleFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="hello", args=(), exc_info=None,
        )
        result = fmt.format(record)
        assert "hello" in result
        assert "INFO" in result

    def test_color_codes(self):
        fmt = ConsoleFormatter()
        for level_name in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            level = getattr(logging, level_name)
            record = logging.LogRecord(
                name="test", level=level, pathname="", lineno=0,
                msg="msg", args=(), exc_info=None,
            )
            result = fmt.format(record)
            assert level_name in result


class TestMaskingLogger:
    """Tests for MaskingLogger."""

    def test_creation(self):
        ml = MaskingLogger(name="test_masking", level="DEBUG")
        assert ml.logger.level == logging.DEBUG

    def test_log_levels(self, capsys):
        ml = MaskingLogger(name="test_masking", level="DEBUG", format_type="console")
        ml.debug("debug msg")
        ml.info("info msg")
        ml.warning("warn msg")
        ml.error("error msg")
        ml.critical("critical msg")
        # No assertion on output — just ensure no exceptions

    def test_json_format(self):
        ml = MaskingLogger(name="test_json", level="DEBUG", format_type="json")
        ml.info("test message")
        # Just ensure no exceptions

    def test_file_logging(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            log_path = f.name
        try:
            ml = MaskingLogger(
                name="test_console", level="INFO",
                format_type="console", log_file=log_path
            )
            ml.info("file test message")
            # Force flush
            for handler in ml.logger.handlers:
                handler.flush()
            with open(log_path, 'r', encoding='utf-8') as f:
                content = f.read()
            assert "file test message" in content
        finally:
            os.unlink(log_path)

    def test_stats_tracking(self):
        ml = MaskingLogger(name="test_masking", level="INFO")
        assert ml._stats["entities_masked"] == 0
        assert ml._stats["collisions"] == 0

    def test_log_with_data(self):
        ml = MaskingLogger(name="test_masking", level="DEBUG", format_type="json")
        ml.info("test", data={"count": 42})
        # Just ensure no exceptions


class TestSetupLogging:
    """Tests for setup_logging() convenience function."""

    def test_default_setup(self):
        logger = setup_logging(level="WARNING")
        assert logger is not None

    def test_setup_with_file(self):
        with tempfile.NamedTemporaryFile(suffix='.log', delete=False) as f:
            log_path = f.name
        try:
            logger = setup_logging(level="INFO", log_file=log_path)
            assert logger is not None
        finally:
            os.unlink(log_path)
