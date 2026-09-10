import logging
import logging_config
from logging_example_service import log_service

# Use the custom logger
logger = logging_config.Logger("example_logger") 
logger.debug("Test debug")
log_service()
print("Hello World!")