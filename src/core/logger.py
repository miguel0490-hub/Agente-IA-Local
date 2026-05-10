import logging
import os
import re
from logging.handlers import RotatingFileHandler


class SecretRedactionFilter(logging.Filter):
    """Redacts common secret patterns from log messages."""

    _PATTERNS = [
        re.compile(r"(api[_-]?key\s*[:=]\s*)([^\s,;]+)", re.IGNORECASE),
        re.compile(r"(token\s*[:=]\s*)([^\s,;]+)", re.IGNORECASE),
        re.compile(r"(password\s*[:=]\s*)([^\s,;]+)", re.IGNORECASE),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        msg = str(record.getMessage())
        for pattern in self._PATTERNS:
            msg = pattern.sub(r"\1[REDACTED]", msg)
        record.msg = msg
        record.args = ()
        return True

def get_logger(name: str):
    """Configura y retorna un logger estructurado."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # Salida por consola
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        ch.addFilter(SecretRedactionFilter())
        logger.addHandler(ch)
        
        # Salida a archivo (Rotatorio simple)
        os.makedirs("logs", exist_ok=True)
        fh = RotatingFileHandler("logs/app.log", encoding="utf-8", maxBytes=2_000_000, backupCount=5)
        fh.setFormatter(formatter)
        fh.addFilter(SecretRedactionFilter())
        logger.addHandler(fh)
        
    return logger
