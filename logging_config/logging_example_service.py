"""Minimal second service, used to show that each logger gets its own file in a run."""

import logging
import time

import logging_config

time.sleep(1)

# Importing logging_config is what installs the custom Logger class, so this module does it
# itself rather than relying on whoever imports it having done so first.
logger: logging_config.Logger = logging.getLogger("example_service")


def log_service() -> None:
    """Log one INFO record, so the service has something in its log file."""
    logger.info("Service is starting...")
