"""Shared message types passed between pipeline stages.

Rules for these types:
- Each dataclass is produced by exactly one service (its "owner").
- Downstream services read them but never mutate them.
- slots=True: faster attribute access + typo'd fields raise AttributeError
  instead of silently creating new attributes.
"""

from dataclasses import dataclass, field

import numpy as np


@dataclass(slots=True)
class Frame:
    """Produced by Camera. One captured image plus bookkeeping."""

    pixels: np.ndarray  # HxW image (real system: HxWx3 uint8 BGR)
    frame_id: int       # monotonically increasing; lets any stage detect stale data


@dataclass(slots=True)
class Detection:
    """One robot found by ObjectDetector."""

    bbox: np.ndarray    # (2, 2) array: [[x1, y1], [x2, y2]], pixel coords
    confidence: float   # 0.0 - 1.0


@dataclass(slots=True)
class DetectionResult:
    """Produced by ObjectDetector for a single Frame."""

    bots: list[Detection] = field(default_factory=list)
    frame_id: int = -1  # copied from the input Frame so results stay traceable
