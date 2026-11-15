"""Converts a match video into a folder of warped, top-down frames of the arena floor.

Shows the first frame of the video so the user can click the four arena corners, builds a
homography from those clicks, then warps every Nth frame to a flat square view and saves each one
as a PNG. Run directly to process the video named in the ``__main__`` block; output goes to
``data/warped_vid_frames/<video name>/``.
"""

import cv2
import os
import numpy as np
from warp_main import get_homography_mat
import logging
import logging_config.logging_config

logger = logging.getLogger(__name__)


def process_video(
    video_path: str,
    output_w: int = 700,
    output_h: int = 700,
    target_fps: int = 5,
) -> None:
    """Warps a video's frames to a top-down arena view and saves a subsample of them as PNGs.

    Opens a window on the first frame for the user to click the arena corners (see
    get_homography_mat), then keeps one frame in every fps // target_fps and warps it with
    the resulting homography. Frames are saved to OUTPUT_BASE_PATH/<video name>/<frame #>.png,
    where the video name is the part of video_path between input_video/ and .mp4 and
    the frame number is the frame's index in the original video. Logs a warning and returns early
    if the video or its first frame can't be read.

    Args:
        video_path: Path to the input .mp4, expected to contain an input_video/ folder.
        output_w: Width of each saved image in pixels. Defaults to 700. The homography always maps
            the arena to 700x700, so other values pad or crop the arena rather than scale it.
        output_h: Height of each saved image in pixels. Defaults to 700. Same caveat as
            output_w.
        target_fps: Approximate number of frames to keep per second of video. Defaults to 5.
            Values of 0 or less, or at least the video's fps, keep every frame. Because the skip
            interval rounds down, the actual rate can be slightly higher than requested.

    Returns:
        None

    Raises:
        NameError: If OUTPUT_BASE_PATH is not defined at module level. It is only set in the
            __main__ block, so calling this function from an import raises this error.
    """
    # open the video
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.warning("Error opening video file")
        return

    ret, frame = cap.read()
    # ret: True if cap.read() successfully reads a frame, False otherwise
    if not ret:
        logger.warning("Error opening video frame")
        return

    # frame = cv2.resize(frame, (output_w, output_h), interpolation=cv2.INTER_NEAREST)
    homography_mat = get_homography_mat(frame, display_scale=1.0)

    fps = int(cap.get(cv2.CAP_PROP_FPS))
    if target_fps > 0 and target_fps < fps:
        coeff = fps // target_fps
    else:
        coeff = 1

    frame_counter = 0

    start_index = video_path.find("input_video/") + len("input_video/")
    end_index = video_path.find(".mp4")
    output_img_folder_dir = OUTPUT_BASE_PATH + video_path[start_index:end_index] + "/"
    os.makedirs(output_img_folder_dir, exist_ok=True)

    num_saved_imgs = 0
    logger.info("Starting processing")
    while ret:
        if frame_counter % coeff == 0:
            # frame = cv2.resize(frame, (output_w, output_h), interpolation=cv2.INTER_AREA)
            warped_frame = cv2.warpPerspective(
                frame, homography_mat, (output_w, output_h), flags=cv2.INTER_NEAREST
            )

            output_img_path = output_img_folder_dir + "/" + str(frame_counter) + ".png"
            num_saved_imgs += 1
            cv2.imwrite(output_img_path, warped_frame)

        ret, frame = cap.read()
        frame_counter += 1

    logger.info("Processing finished")
    logger.debug(f"Total saved images: {num_saved_imgs}")


if __name__ == "__main__":
    INPUT_BASE_PATH = "data/input_video/"
    OUTPUT_BASE_PATH = "data/warped_vid_frames/"
    video_name = "huey_vs_prince.mp4"
    process_video(INPUT_BASE_PATH + video_name)
