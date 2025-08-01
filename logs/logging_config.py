# logs/logging_config.py
import logging
import os
from colorlog import ColoredFormatter

def setup_logging(log_file_path="logs/app.log", level=logging.DEBUG):
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

    console_formatter = ColoredFormatter(
    "%(log_color)s[%(levelname)s] %(asctime)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    log_colors={
        'DEBUG': 'cyan',
        'INFO': 'blue',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'bold_red',
    },
    style='%'
    )





    # Plain formatter for file
    file_formatter = logging.Formatter(
        "\n========== %(levelname)s ==========\n%(asctime)s | %(name)s\n%(message)s\n",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Stream handler for console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)

    # File handler
    file_handler = logging.FileHandler(log_file_path)
    file_handler.setFormatter(file_formatter)

    # Get and configure the root logger
    logger = logging.getLogger()
    logger.setLevel(level)

    # Clear previous handlers
    if logger.hasHandlers():
        logger.handlers.clear()

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logging.getLogger(__name__)
