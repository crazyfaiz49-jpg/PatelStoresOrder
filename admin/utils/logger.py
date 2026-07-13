import logging
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
LOG_FILE = ROOT_DIR / 'admin.log'


def get_logger(name: str = 'patelstores.admin') -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')

    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
