"""Warp a whole video to a top-down view of the arena floor.

Opens a file picker to choose a video, shows one frame so you can click the four arena corners
(top left, top right, bottom right, bottom left; 'z' undoes a click, Esc cancels), then warps
every frame with that homography and writes the result to a file chosen in a save dialog.

Run from the repo root so `warp_main`, `logging_config`, and `main_files/` resolve:

    uv run python -m scripts.warp_video
    uv run python -m scripts.warp_video --frame 300 --display-scale 0.6
"""

import argparse
import logging
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

import cv2
import logging_config.logging_config  # noqa: F401 - configures the custom logger class
import numpy as np
from warp_main import ARENA_WIDTH, get_homography_mat, get_warp_maps, warp_map

logger = logging.getLogger(__name__)

VIDEO_FILETYPES = [("Video files", "*.mp4 *.mov *.avi *.mkv *.m4v"), ("All files", "*.*")]


def parse_args() -> argparse.Namespace:
    """Parse the command-line options.

    Returns:
        argparse.Namespace: `frame` (index of the frame to click corners on) and
            `display_scale` (scale of the corner-selection window).
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--frame",
        type=int,
        default=0,
        help="index of the frame used for corner selection (default: 0)",
    )
    parser.add_argument(
        "--display-scale",
        type=float,
        default=1.0,
        help="scale of the corner-selection window, e.g. 0.6 for large videos (default: 1.0)",
    )
    return parser.parse_args()


def ask_input_and_output_paths() -> tuple[Path, Path] | None:
    """Ask for the source video and the output location with native file dialogs.

    The Tk root is destroyed before returning so it can't fight OpenCV's windows for the
    main-thread event loop on macOS.

    Returns:
        tuple[Path, Path] | None: (input video, output video), or None if either dialog was
            cancelled.
    """
    root = tk.Tk()
    root.withdraw()
    try:
        in_name = filedialog.askopenfilename(
            title="Select a video to warp", filetypes=VIDEO_FILETYPES
        )
        if not in_name:
            return None
        in_path = Path(in_name)
        out_name = filedialog.asksaveasfilename(
            title="Save warped video as",
            initialdir=in_path.parent,
            initialfile=f"{in_path.stem}_warped.mp4",
            defaultextension=".mp4",
            filetypes=[("MP4 video", "*.mp4")],
        )
        if not out_name:
            return None
        return in_path, Path(out_name)
    finally:
        root.destroy()


def read_frame_at(cap: cv2.VideoCapture, index: int) -> cv2.typing.MatLike | None:
    """Read a single frame from a video, then rewind the capture to the start.

    Args:
        cap: An opened video capture.
        index: Zero-based frame index to read.

    Returns:
        cv2.typing.MatLike | None: The frame, or None if it couldn't be read.
    """
    cap.set(cv2.CAP_PROP_POS_FRAMES, index)
    ok, frame = cap.read()
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    return frame if ok else None


def write_warped_video(
    cap: cv2.VideoCapture, out_path: Path, fps: float, maps: tuple[np.ndarray, np.ndarray]
) -> int:
    """Warp every frame of `cap` with precomputed remap tables and write them to `out_path`.

    Args:
        cap: An opened video capture positioned at the first frame.
        out_path: Where to write the warped .mp4.
        fps: Frame rate for the output video.
        maps: The (map_x, map_y) pair from `get_warp_maps`.

    Returns:
        int: Number of frames written.
    """
    map_x, map_y = maps
    fourcc = cv2.VideoWriter.fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(out_path), fourcc, fps, (ARENA_WIDTH, ARENA_WIDTH))
    if not writer.isOpened():
        raise OSError(f"Could not open video writer for {out_path}")

    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    written = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            writer.write(warp_map(frame, map_x, map_y))
            written += 1
            if written % 300 == 0:
                logger.info(f"Warped {written}/{total} frames")
    finally:
        writer.release()
    return written


def main() -> None:
    """Pick a video, select arena corners, and save the warped video."""
    args = parse_args()

    paths = ask_input_and_output_paths()
    if paths is None:
        logger.info("No file selected, exiting.")
        return
    in_path, out_path = paths

    cap = cv2.VideoCapture(str(in_path))
    if not cap.isOpened():
        logger.error(f"Could not open video: {in_path}")
        return

    try:
        frame = read_frame_at(cap, args.frame)
        if frame is None:
            logger.error(f"Could not read frame {args.frame} of {in_path}")
            return

        try:
            h_mat = get_homography_mat(frame, display_scale=args.display_scale)
        except cv2.error:
            # findHomography raises when fewer than 4 corners were clicked (Esc pressed).
            logger.info("Corner selection cancelled, exiting.")
            return

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        written = write_warped_video(cap, out_path, fps, get_warp_maps(h_mat))
        logger.info(f"Saved {written} warped frames to {out_path}")
    finally:
        cap.release()


if __name__ == "__main__":
    main()
