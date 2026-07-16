"""ObjectDetector service: Frame in, DetectionResult out."""

from collections import deque

import numpy as np
from loguru import logger

from datatypes import Detection, DetectionResult, Frame


class ObjectDetector:
    """Mock detector. Real version wraps the Ultralytics predictor.

    Hot-path method: detect()
    Queryable state:  last_result, recent_bot_counts()
    """

    # Bounded history: old results fall off automatically, no unbounded growth.
    HISTORY_LEN = 30

    def __init__(self):
        self._history: deque[DetectionResult] = deque(maxlen=self.HISTORY_LEN)
        logger.info("object_detection: initialized")

    def detect(self, frame: Frame) -> DetectionResult:
        """Run detection on one frame. Reads the Frame, never mutates it."""
        logger.trace("object_detection: running inference on frame {}", frame.frame_id)
        # Mock inference: always "find" two robots. Real version runs the model
        # on frame.pixels here.
        bots = [
            Detection(bbox=np.array([[1, 1], [3, 3]]), confidence=0.9),
            Detection(bbox=np.array([[6, 6], [8, 8]]), confidence=0.7),
        ]

        # frame_id carried through so downstream stages can match results to frames.
        result = DetectionResult(bots=bots, frame_id=frame.frame_id)
        self._history.append(result)
        logger.debug("object_detection: found {} bots in frame {}", len(bots), frame.frame_id)
        return result

    # ---- read-only state accessors -------------------------------------

    @property
    def last_result(self) -> DetectionResult | None:
        """Most recent detection result, or None before the first detect()."""
        return self._history[-1] if self._history else None

    def recent_bot_counts(self, n: int = 5) -> list[int]:
        """Bot count for each of the last n frames (oldest first).

        Example of a query method another service might use, e.g. to check
        whether detections have been stable lately.
        """
        recent = list(self._history)[-n:]
        return [len(result.bots) for result in recent]
