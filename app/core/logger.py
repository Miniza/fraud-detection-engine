import logging
import sys
from typing import Optional


class ColoredFormatter(logging.Formatter):
    """Custom formatter that adds colored output to log messages."""

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with color coding."""
        color = self.COLORS.get(record.levelname, self.RESET)

        # Add color to the level name
        record.levelname_colored = f"{color}{record.levelname}{self.RESET}"

        # Format the message
        if record.exc_info:
            # Include exception traceback
            result = f"{color}[{record.levelname}]{self.RESET} {record.getMessage()}"
            if record.exc_text is None:
                record.exc_text = self.formatException(record.exc_info)
            result += f"\n{record.exc_text}"
            return result
        else:
            return f"{color}[{record.levelname}]{self.RESET} {record.getMessage()}"


def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """
    Get a configured logger with colored output.

    Args:
        name: Logger name (typically __name__)
        level: Log level (default: INFO)

    Returns:
        Configured logger instance
    """
    if level is None:
        level = logging.INFO

    logger = logging.getLogger(name)

    # Only add handler if one doesn't exist
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)

        formatter = ColoredFormatter()
        handler.setFormatter(formatter)

        logger.addHandler(handler)
        logger.setLevel(level)

    return logger
