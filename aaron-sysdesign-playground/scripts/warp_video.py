#!/usr/bin/env python3
"""Download a video, warp every frame to a top-down view, and save it as an mp4 in videos/.

Set VIDEO_URL below to the video you want, then run this script. It downloads
the video to a temp file, opens a window on its first frame to click the
arena floor's 4 corners (see warp/README.md for the picker controls), then
warps every frame with those corners and writes the result to
videos/<name>_warped.mp4.

Usage:
    uv run scripts/warp_video.py
"""

import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import cv2
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from warp import FloorWarper, close_review_window, pick_corners  # noqa: E402

# ----------------------------- config ---------------------------------------

VIDEO_URL = "https://nhrl-matches.us-east-1.linodeobjects.com/proxy/Cage-6-Overhead-High-2026-02-07_16-13-01.984_720p.mp4"  # set this to the video to download, then run this script

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "videos"
FOURCC = "mp4v"  # broadly supported by opencv for .mp4 containers

# -----------------------------------------------------------------------------


def output_path(url: str) -> Path:
    """videos/<url's filename stem>_warped.mp4, falling back to a generic
    name if the URL doesn't end in anything file-name-shaped."""
    stem = Path(urlparse(url).path).stem or "video"
    return OUTPUT_DIR / f"{stem}_warped.mp4"


def download_video(url: str, dest: Path) -> None:
    print(f"Downloading {url}")
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        written = 0
        with dest.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
                written += len(chunk)
                if total:
                    print(f"  {written / 1e6:6.1f} / {total / 1e6:.1f} MB", end="\r")
    size = dest.stat().st_size
    if size == 0:
        raise SystemExit(f"Downloaded 0 bytes from {url}; is the URL correct?")
    print(f"\nDownloaded {size / 1e6:.1f} MB")


def warp_video(src: Path, dest: Path) -> None:
    """Read src frame by frame, warp each to the corners picked on its
    first frame, and write the result to dest."""
    cap = cv2.VideoCapture(str(src))
    if not cap.isOpened():
        raise SystemExit(f"Couldn't open {src} as a video.")

    ok, frame = cap.read()
    if not ok:
        cap.release()
        raise SystemExit(f"{src} has no readable frames.")

    corners = pick_corners(frame, title=src.name)
    close_review_window()
    if corners is None or isinstance(corners, str):
        cap.release()
        raise SystemExit("Corner selection cancelled; no video written.")

    warper = FloorWarper()
    warper.calibrate("video", corners)
    warped = warper.warp(frame, "video")
    height, width = warped.shape[:2]

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or None

    dest.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(dest), cv2.VideoWriter_fourcc(*FOURCC), fps, (width, height)
    )
    if not writer.isOpened():
        cap.release()
        raise SystemExit(f"Couldn't open {dest} for writing (codec unavailable?).")

    writer.write(warped)
    n = 1
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        writer.write(warper.warp(frame, "video"))
        n += 1
        if n % 250 == 0:
            print(f"  warped {n}/{total_frames or '?'} frames")

    cap.release()
    writer.release()
    print(f"Wrote {dest} ({n} frames, {width}x{height} @ {fps:.2f} fps)")


def main() -> None:
    if VIDEO_URL == "<VIDEO_URL>":
        raise SystemExit("Set VIDEO_URL at the top of this script before running.")

    dest = output_path(VIDEO_URL)
    with tempfile.TemporaryDirectory() as tmp:
        suffix = Path(urlparse(VIDEO_URL).path).suffix or ".mp4"
        src = Path(tmp) / f"source{suffix}"
        download_video(VIDEO_URL, src)
        warp_video(src, dest)


if __name__ == "__main__":
    main()
