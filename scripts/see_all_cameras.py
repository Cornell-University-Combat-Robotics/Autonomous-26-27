import cv2
from cv2_enumerate_cameras import enumerate_cameras
import logging
import logging_config.logging_config 

logger = logging.getLogger(__name__)

# Enumerate all available cameras
cameras = enumerate_cameras()

if cameras:
    logger.info("Available cameras:")
    for camera_info in cameras:
        logger.info(f"Index: {camera_info.index}, Name: {camera_info.name}, Path: {camera_info.path}")

    # Example: Open the first camera using its index
    if cameras[0].index is not None:
        cap = cv2.VideoCapture(cameras[0].index)
        if not cap.isOpened():
            logger.warning(f"Unable to open camera at index {cameras[0].index}")
        else:
            logger.info(f"Successfully opened camera: {cameras[0].name}")
            # You can now proceed with your video stream operations...
            cap.release()
else:
    logger.info("No cameras found.")
