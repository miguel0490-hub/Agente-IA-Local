import json
import logging
import os
import re
import threading
from datetime import datetime, timezone
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


_correlation_id = threading.local()


def set_correlation_id(cid: str) -> None:
    """Sets the correlation ID for the current thread."""
    _correlation_id.value = cid


def get_correlation_id() -> str:
    return getattr(_correlation_id, "value", "")


class JSONFormatter(logging.Formatter):
    """Structured JSON log format for production (ELK/CloudWatch compatible)."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": get_correlation_id(),
        }
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


def get_logger(name: str):
    """Returns a configured logger with secret redaction and optional JSON format."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)

        is_production = os.getenv("ENVIRONMENT", "").lower() == "production"

        if is_production:
            formatter = JSONFormatter()
        else:
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        ch.addFilter(SecretRedactionFilter())
        logger.addHandler(ch)

        os.makedirs("logs", exist_ok=True)
        fh = RotatingFileHandler("logs/app.log", encoding="utf-8", maxBytes=2_000_000, backupCount=5)
        fh.setFormatter(formatter)
        fh.addFilter(SecretRedactionFilter())
        logger.addHandler(fh)

    return logger
