import os
import logging.config

DEFAULT_BASE_LOGGING_LEVEL = logging.INFO
DEFAULT_VERBOSE_LOGGING_LEVEL = logging.DEBUG

LOGGER = {
    "version": 1,
    "formatters": {
        "file": {
            "format": "%(asctime)s %(levelname)s - %(message)s"
        },
        "console": {
            "format": "%(levelname)s - %(message)s"
        }
    },
    "handlers": {
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "file",
            "level": "DEBUG",
            "filename": os.path.expanduser("~/.cfyap/cfyap.log"),
            "maxBytes": 5000000,
            "backupCount": 20
        },
        "console": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "formatter": "console"
        }
    },
    "loggers": {
        "": {
            "handlers": ["file", "console"]
        },
    }
}


def init(logging_config=None):
    logging_config = logging_config or LOGGER
    try:
        log_dir = os.path.dirname(
            logging_config['handlers']['file']['filename'])
    except KeyError:
        pass
    else:
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
    logging.config.dictConfig(logging_config)
