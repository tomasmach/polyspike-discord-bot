"""Logging setup for the Discord bot.

By default, logs go to stdout which is captured by systemd journal.
Optionally, file logging with rotation can be enabled via LOG_FILE_PATH.

When running as systemd service, use journalctl to view logs:
    sudo journalctl -u polyspike-discord-bot -f
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Default rotation settings for file logging
DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10 MB per file
DEFAULT_BACKUP_COUNT = 5  # Keep 5 backup files (total ~60 MB max)


def setup_logger(
    log_level: str = "INFO",
    log_file: str | None = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
    backup_count: int = DEFAULT_BACKUP_COUNT,
) -> logging.Logger:
    """Setup and configure logger for the bot.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_file: Optional path to log file. If None, logs only to stdout
            (recommended for systemd journal integration).
        max_bytes: Maximum size of each log file before rotation (default 10MB).
        backup_count: Number of backup files to keep (default 5).

    Returns:
        Configured logger instance.

    Note:
        When running as a systemd service, stdout is automatically captured
        by the journal. File logging is optional and only needed if you
        require separate log files outside of journald.
    """
    # Create logger
    logger = logging.getLogger("polyspike_bot")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Clear existing handlers
    logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler (stdout) - always enabled
    # When running under systemd, stdout is captured by journal
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler with rotation (optional)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        logger.info(
            f"File logging enabled: {log_file} "
            f"(max {max_bytes // (1024 * 1024)}MB, {backup_count} backups)"
        )

    return logger


def get_logger() -> logging.Logger:
    """Get the configured logger instance.

    Returns:
        Logger instance.
    """
    return logging.getLogger("polyspike_bot")
