import logging
import dictconfig

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
        "console": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "formatter": "console"
        }
    },
    "loggers": {
        "user": {
            "handlers": ["console"]
        },
    }
}


def init(base_level=DEFAULT_BASE_LOGGING_LEVEL,
         verbose_level=DEFAULT_VERBOSE_LOGGING_LEVEL):
    """Initializes a base logger
    """
    lgr = logging.getLogger('user')
    lgr.setLevel(base_level)
    return lgr


def configure():
    """Configures the logger using the default configuration.
    """
    dictconfig.dictConfig(LOGGER)
