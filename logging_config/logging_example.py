import logging_config
from logging_example_service import log_service

logger = logging_config.Logger("example_logger") 

def run_example_detection(frame_id: int, threshold: float) -> bool:
    label = "enemy"
    confidence = 0.87
    logger.trace("post-detect")
    return confidence > threshold

logger.debug("Test debug")
run_example_detection(frame_id=118, threshold=0.5)
log_service()
print("Hello World!")