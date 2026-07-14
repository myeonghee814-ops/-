import logging
import logging.config


def setup_logging(level: str = "INFO") -> None:
    """Configure application-wide structured logging.

    Called once at startup so every module can simply use
    `logging.getLogger(__name__)` and inherit consistent formatting/handlers.
    """
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                },
            },
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
