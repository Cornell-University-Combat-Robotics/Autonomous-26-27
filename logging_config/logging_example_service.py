import logging
import time

time.sleep(5)

logger = logging.getLogger("example_service")

def log_service():
    logger.info("Service is starting...")