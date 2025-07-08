# logs/logging_config.py
import logging
import os
from colorlog import ColoredFormatter

def setup_logging(log_file_path="logs/app.log", level=logging.DEBUG):
    # Create logs directory if it doesn't exist
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

    # Define color formatter for console output
    console_formatter = ColoredFormatter(
        "%(log_color)s[%(levelname)s] %(asctime)s - %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        log_colors={
            'DEBUG':    'cyan',
            'INFO':     'blue',
            'WARNING':  'yellow',
            'ERROR':    'red',
            'CRITICAL': 'bold_red',
        }
    )

    # Define plain formatter for file output
    file_formatter = logging.Formatter(
        "[%(levelname)s] %(asctime)s - %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Stream (console) handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)

    # File handler
    file_handler = logging.FileHandler(log_file_path)
    file_handler.setFormatter(file_formatter)

    # Get root logger
    logger = logging.getLogger()
    logger.setLevel(level)

    # Clear existing handlers if any (avoid duplication)
    if logger.hasHandlers():
        logger.handlers.clear()

    # Add both handlers
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logging.getLogger(__name__)
