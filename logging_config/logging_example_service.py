import logging
import time

time.sleep(1)

logger = logging.getLogger("example_service")

def log_service():
    logger.info("Service is starting...")