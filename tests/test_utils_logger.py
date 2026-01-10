import logging
import sys
from unittest.mock import patch

import pytest
from loguru import logger

from tiebameow.utils.logger import InterceptHandler, init_logger


class TestLogger:
    @pytest.fixture(autouse=True)
    def reset_logger(self):
        """Reset logger before each test."""
        logger.remove()
        yield
        logger.remove()

    def test_init_logger_basics(self):
        """Test basic logger code paths."""
        # Simple init with defaults
        init_logger(reset=True, add_console=True, enqueue=False)
        # Verify handler count (sys.stderr is added)
        logger.info("Test message")

    def test_init_logger_no_console(self):
        """Test init without console."""
        init_logger(reset=True, add_console=False, enqueue=False)
        logger.info("Test message hidden")

    def test_file_logging(self, tmp_path):
        """Test file logging configuration."""
        log_dir = tmp_path / "logs"

        init_logger(
            service_name="test_service",
            enable_filelog=True,
            enable_error_filelog=True,
            log_dir=log_dir,
            level="DEBUG",
            rotation="100 KB",
            enqueue=False,  # Disable async for testing
        )

        logger.debug("Debug message")
        logger.error("Error message")

        # Verify files created
        assert (log_dir / "test_service.log").exists()
        assert (log_dir / "test_service.error.log").exists()

        # Verify content
        log_content = (log_dir / "test_service.log").read_text(encoding="utf-8")
        assert "Debug message" in log_content
        assert "Error message" in log_content

        err_log_content = (log_dir / "test_service.error.log").read_text(encoding="utf-8")
        assert "Error message" in err_log_content
        assert "Debug message" not in err_log_content

    def test_custom_formats(self, tmp_path):
        """Test custom formats."""
        log_dir = tmp_path / "logs"
        init_logger(
            enable_filelog=True, log_dir=log_dir, console_format="{message}", file_format="{message}", enqueue=False
        )

        logger.info("Custom format")

        log_content = (log_dir / "tiebameow.log").read_text(encoding="utf-8")
        assert "Custom format" in log_content

    def test_intercept_handler(self, capsys):
        """Test standard logging interception."""
        # Setup logger to print to stderr (default) so we can capture it
        init_logger(intercept_standard_logging=True, add_console=True, enqueue=False)

        # Use standard logging
        std_logger = logging.getLogger("std_test")
        std_logger.info("Standard logging message")

        # Verify it went through
        captured = capsys.readouterr()
        # Since we use enqueue=False, it should appear in stderr
        assert "Standard logging message" in captured.err

    def test_intercept_handler_exception(self):
        """Test intercept handler with exception info."""
        handler = InterceptHandler()
        # Create a LogRecord with exc_info
        exc_info = None
        try:
            _ = 1 / 0
        except ZeroDivisionError:
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )

        # We just want to ensure emit doesn't crash
        handler.emit(record)

    def test_intercept_handler_custom_level(self):
        """Test intercept handler with custom level that might not exist in loguru."""
        handler = InterceptHandler()
        record = logging.LogRecord(
            name="test",
            level=35,  # Non-standard level
            pathname=__file__,
            lineno=1,
            msg="Custom level",
            args=(),
            exc_info=None,
        )
        # Should fall back to level number
        handler.emit(record)

    def test_fail_create_dir(self):
        """Test failure to create log directory."""
        with patch("pathlib.Path.mkdir", side_effect=PermissionError("Mocked permission error")):
            init_logger(enable_filelog=True, log_dir="/root/forbidden", enqueue=False)
            # Should log warning internally, but not crash
