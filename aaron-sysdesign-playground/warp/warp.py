"""Warp service: rectifies arena-floor frames to a fixed-size top-down view.

Corners are picked by hand (pick_corners opens a window: click 4 points,
right-click to undo, Enter/Space to confirm) rather than detected
automatically -- wall thickness, background contrast, and lighting vary
enough across cameras that automatic detection wasn't reliable enough in
practice. The picker pads the frame with a clickable black margin
(CLICK_PAD_PX) so a corner the camera itself doesn't capture -- common
along the near wall -- can still be marked outside the real image; warping
then fills in black wherever that pulls from outside the source frame.

A camera can still drift or get bumped mid-tournament, so a key's
calibration isn't assumed to hold forever: review_warp shows each match's
warp against the currently cached calibration and lets the caller confirm
it or trigger a fresh pick_corners call, which then applies going forward
until reviewed again.
"""

import cv2
import numpy as np
from loguru import logger

OUTPUT_SIZE = (640, 640)  # (width, height); every warped frame comes out this size
CLICK_PAD_PX = 150  # clickable black margin around the frame, for corners the camera cuts off

# One OS window reused for every picker/review call in a run, rather than a
# new window per match -- with hundreds of matches to click through,
# creating/destroying a window each time is slow and flickery, and there's
# never more than one open at a time anyway (everything here is main-thread
# only). Title text still changes per call via cv2.setWindowTitle.
WINDOW_NAME = "brettzone-warp"


def close_review_window() -> None:
    """Best-effort close of the shared review/picker window at the end of a run."""
    try:
        cv2.destroyWindow(WINDOW_NAME)
    except cv2.error:
        pass


def order_corners(pts: np.ndarray) -> np.ndarray:
    """Sort 4 arbitrary points into [top-left, top-right, bottom-right, bottom-left]."""
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).reshape(-1)
    return np.array([
        pts[np.argmin(s)], pts[np.argmin(d)], pts[np.argmax(s)], pts[np.argmax(d)],
    ], dtype=np.float32)


def pad_outward(pts: np.ndarray, px: float) -> np.ndarray:
    """Push each corner away from the quad's centroid by px pixels. Not
    used by the interactive flow (clicks are expected to already include
    whatever margin you want), but handy if you ever want to pad
    programmatically."""
    center = pts.mean(axis=0)
    directions = pts - center
    norms = np.linalg.norm(directions, axis=1, keepdims=True)
    return pts + directions / np.where(norms == 0, 1, norms) * px


def build_transform(
    corners: np.ndarray, output_size: tuple[int, int] = OUTPUT_SIZE
) -> np.ndarray:
    """Homography mapping the 4 (any-order) corners onto a rectangle
    filling output_size."""
    width, height = output_size
    dst = np.array(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]],
        dtype=np.float32,
    )
    return cv2.getPerspectiveTransform(order_corners(corners), dst)


class _Picker:
    """One click session on a single frame: 4 left-clicks place corners,
    right-click undoes the last one, Enter/Space confirms, 'r' resets,
    's' skips this camera, Esc stops the whole calibration session.

    The frame is shown with a CLICK_PAD_PX black margin so a corner the
    camera doesn't actually capture (common along the near wall) can still
    be clicked outside the real image -- points are tracked in this padded
    canvas's coordinates and shifted back to the original frame's
    coordinate space before being returned."""

    POINT_COLOR = (0, 0, 255)
    LINE_COLOR = (0, 220, 0)
    FRAME_OUTLINE_COLOR = (120, 120, 120)
    BANNER_HEIGHT = 32
    PAD = CLICK_PAD_PX

    def __init__(self, img: np.ndarray, title: str):
        self._title = title
        self._points: list[tuple[int, int]] = []  # in padded-canvas coordinates
        self._padded = cv2.copyMakeBorder(
            img, self.PAD, self.PAD, self.PAD, self.PAD,
            cv2.BORDER_CONSTANT, value=(0, 0, 0),
        )
        self._frame_rect = (self.PAD, self.PAD, self.PAD + img.shape[1], self.PAD + img.shape[0])

    def _on_mouse(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN and len(self._points) < 4:
            self._points.append((x, y))
            self._draw()
        elif event == cv2.EVENT_RBUTTONDOWN and self._points:
            self._points.pop()
            self._draw()

    def _draw(self):
        frame = self._padded.copy()
        x0, y0, x1, y1 = self._frame_rect
        cv2.rectangle(frame, (x0, y0), (x1, y1), self.FRAME_OUTLINE_COLOR, 1)
        for i, p in enumerate(self._points):
            cv2.circle(frame, p, 7, self.POINT_COLOR, -1)
            cv2.putText(frame, str(i + 1), (p[0] + 10, p[1] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        if len(self._points) > 1:
            cv2.polylines(frame, [np.array(self._points)], len(self._points) == 4,
                          self.LINE_COLOR, 2)
        banner = (
            "click 4 floor corners, any order (grey outline = camera's actual view; "
            "click outside it for corners it doesn't capture) | right-click: undo | "
            "r: reset | s: skip camera | esc: stop calibrating"
            if len(self._points) < 4 else
            "enter/space: confirm | right-click: undo | r: reset | esc: stop calibrating"
        )
        cv2.rectangle(frame, (0, 0), (frame.shape[1], self.BANNER_HEIGHT), (0, 0, 0), -1)
        cv2.putText(frame, f"{self._title} -- {banner}", (8, 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.imshow(WINDOW_NAME, frame)

    def run(self) -> np.ndarray | None | str:
        """Returns 4x2 float32 corners in the original (unpadded) frame's
        coordinate space -- may include negative values or values beyond
        the frame's width/height for off-camera corners -- None if this
        camera was skipped, or "abort" to stop calibrating altogether."""
        cv2.namedWindow(WINDOW_NAME)
        cv2.setWindowTitle(WINDOW_NAME, self._title)
        cv2.setMouseCallback(WINDOW_NAME, self._on_mouse)
        self._draw()
        while True:
            key = cv2.waitKey(20) & 0xFF
            if key in (13, 32) and len(self._points) == 4:  # enter / space
                pts = np.array(self._points, dtype=np.float32)
                return pts - self.PAD
            if key == ord("r"):
                self._points.clear()
                self._draw()
            elif key == ord("s"):
                return None
            elif key == 27:  # esc
                return "abort"


def pick_corners(img: np.ndarray, title: str) -> np.ndarray | None | str:
    """Show img and let the user click its 4 floor corners.

    Returns the corners (4x2 float32, any order), None if the user chose
    to skip this camera, or "abort" if they want to stop calibrating
    altogether for the rest of the run.
    """
    return _Picker(img, title).run()


def review_warp(warped: np.ndarray, title: str) -> str:
    """Show an already-warped frame for a quick confirm/redo check, rather
    than assuming a camera's calibration still holds for every match.

    Returns "confirm" (use it as-is), "redo" (the caller should reopen
    pick_corners and replace the calibration going forward), or "abort"
    (stop reviewing for the rest of this run).
    """
    banner_height = 32
    frame = cv2.copyMakeBorder(warped, banner_height, 0, 0, 0, cv2.BORDER_CONSTANT, value=(0, 0, 0))
    cv2.putText(
        frame, f"{title} -- enter/space: confirm | r: redo corners | esc: stop reviewing",
        (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA,
    )
    cv2.namedWindow(WINDOW_NAME)
    cv2.setWindowTitle(WINDOW_NAME, title)
    cv2.setMouseCallback(WINDOW_NAME, lambda *args: None)  # no clicks to handle here
    cv2.imshow(WINDOW_NAME, frame)
    while True:
        key = cv2.waitKey(20) & 0xFF
        if key in (13, 32):
            return "confirm"
        if key == ord("r"):
            return "redo"
        if key == 27:
            return "abort"


class FloorWarper:
    """Rectifies arena frames to a fixed-size top-down view, calibrating
    once per key via pick_corners().

    Hot-path method: warp()
    Queryable state:  calibrated_keys
    """

    def __init__(self, output_size: tuple[int, int] = OUTPUT_SIZE):
        self._output_size = output_size
        self._calibration: dict[str, np.ndarray | None] = {}

    def has(self, key: str) -> bool:
        """Whether key has already been calibrated or explicitly skipped."""
        return key in self._calibration

    def calibrate(self, key: str, corners: np.ndarray) -> None:
        """Cache a homography for key from 4 (any-order) corner points."""
        self._calibration[key] = build_transform(corners, self._output_size)
        logger.info("warp: calibrated {}", key)

    def skip(self, key: str) -> None:
        """Mark key as deliberately uncalibrated: warp() passes its frames through."""
        self._calibration[key] = None
        logger.info("warp: skipping {} (left unwarped)", key)

    def forget(self, key: str) -> None:
        """Drop any calibration or skip decision for key, as if it had
        never been seen -- unlike skip(), a later has(key) is False, so
        it'll be prompted for again."""
        self._calibration.pop(key, None)
        logger.info("warp: forgot {} (will be re-prompted)", key)

    def warp(self, img: np.ndarray, key: str) -> np.ndarray:
        """Return img rectified with key's cached calibration, or img
        unchanged if key was skipped or never calibrated. Corners clicked
        outside the frame (see CLICK_PAD_PX) make some output pixels map
        back to source coordinates that don't exist -- those come out
        black rather than stretched/replicated edge pixels."""
        matrix = self._calibration.get(key)
        if matrix is None:
            return img
        return cv2.warpPerspective(
            img, matrix, self._output_size,
            borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0),
        )

    @property
    def calibrated_keys(self) -> list[str]:
        """Keys with an active (non-skipped) calibration."""
        return [k for k, v in self._calibration.items() if v is not None]
