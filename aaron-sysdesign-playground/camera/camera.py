"""Camera service: owns frame capture and produces Frame messages."""

import numpy as np
from loguru import logger

from datatypes import Frame


class Camera:
    """Mock camera. Real version wraps cv2.VideoCapture / CameraStream.

    Hot-path method: read()
    Queryable state:  frames_captured, last_frame
    """

    def __init__(self, width: int = 10, height: int = 10):
        self._width = width
        self._height = height
        # State: other services read these via the properties below, never directly.
        self._frames_captured = 0
        self._last_frame: Frame | None = None
        logger.info(f"camera: initialized ({width}x{height})")

    def read(self) -> Frame:
        """Capture and return the next frame. Called once per loop iteration."""
        # Mock capture: a blank image. Real version pulls from hardware here.
        logger.trace("camera: generating blank pixel array")
        pixels = np.zeros((self._height, self._width))

        frame = Frame(pixels=pixels, frame_id=self._frames_captured)
        self._frames_captured += 1
        self._last_frame = frame
        logger.debug(f"camera: frame {frame.frame_id} captured")
        return frame

    # ---- read-only state accessors -------------------------------------

    @property
    def frames_captured(self) -> int:
        """How many frames this camera has produced so far."""
        return self._frames_captured

    @property
    def last_frame(self) -> Frame | None:
        """Most recent frame, or None if read() hasn't been called yet."""
        return self._last_frame
