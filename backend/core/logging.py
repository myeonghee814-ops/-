import json
import logging
import logging.config
from datetime import datetime, timezone

_RESERVED_LOG_RECORD_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__.keys())


class JsonFormatter(logging.Formatter):
    """Minimal structured formatter for production log aggregators
    (CloudWatch, Datadog, ELK, ...), which parse JSON far more reliably
    than the human-oriented text format used in development.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        # Include any extra=... fields callers attached (e.g. request_id).
        for key, value in record.__dict__.items():
            if key not in _RESERVED_LOG_RECORD_ATTRS:
                payload[key] = value

        return json.dumps(payload, default=str)


def setup_logging(level: str = "INFO", log_format: str = "text") -> None:
    """Configure application-wide logging.

    Called once at startup so every module can simply use
    `logging.getLogger(__name__)` and inherit consistent formatting/handlers.

    `log_format="json"` switches to structured JSON output (LOG_FORMAT env
    var) — intended for production, where log aggregators consume it;
    "text" (the default) stays human-readable for local development.
    """
    formatter: dict[str, object] = (
        {"()": JsonFormatter}
        if log_format == "json"
        else {"format": "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"}
    )

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"default": formatter},
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                },
            },
            "root": {
                "handlers": ["console"],
                "level": level,
            },
        }
    )
