"""Checks which cameras are connected to this computer.

Run this file to log the index of each camera OpenCV can open. Use those indices to pick which
camera to read from.
"""

import cv2
import logging
import logging_config.logging_config

logger = logging.getLogger(__name__)


def get_available_cameras():
    """Returns the index of every camera that can be opened.

    Tries camera indices 0 through 4 with OpenCV and keeps the ones that open. Each camera is
    released right after the check so it is free to use afterward.

    Returns:
        list[int]: List of camera indices ready for use. Empty if no cameras are found.
    """
    available_cameras = []
    # Check for 5 cameras
    for i in range(5):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            available_cameras.append(i)
            cap.release()
    return available_cameras


cameras = get_available_cameras()
if cameras:
    logger.info("Available Cameras:", cameras)
else:
    logger.info("No cameras found.")
