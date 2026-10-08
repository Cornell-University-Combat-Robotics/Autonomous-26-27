"""Turn a `camera_number` URL into something `cv2.VideoCapture` can open.

Handles YouTube links and direct video-file links such as Brettzone's
`https://nhrl-matches.us-east-1.linodeobjects.com/proxy/<match>_720p.mp4`. Both go through yt-dlp:
for YouTube it finds the real media URL behind the watch page, and for a direct link its generic
extractor just hands the link back. The video is then either streamed (OpenCV reads it over the
network, nothing is saved) or downloaded once into a local folder and reused on later runs.

Webcam indices and local file paths pass through unchanged.
"""

import logging
import os
from collections.abc import Callable

import logging_config.logging_config  # noqa: F401 - imported for its side effect of configuring logging
import yt_dlp

logger = logging.getLogger(__name__)

# yt-dlp makes its web requests through `requests`, whose urllib3 logs every request (with very
# long YouTube URLs) at DEBUG. Those drown out our own DEBUG console output.
logging.getLogger("urllib3").setLevel(logging.WARNING)

# Video-only H.264 at <=1080p over plain HTTPS. The pipeline never uses audio, and a video-only
# stream needs no ffmpeg merge step. OpenCV's bundled FFmpeg can always decode H.264 and can
# read plain HTTPS directly (not YouTube's fragmented DASH/HLS streams). Each `/` is a fallback,
# and the last one (`b[protocol=https]`) is what matches a direct Brettzone .mp4 link.
VIDEO_FORMAT = (
    "bv*[vcodec^=avc1][height<=1080][protocol=https]/b[ext=mp4][protocol=https]/b[protocol=https]"
)

# yt-dlp needs a JavaScript runtime to unlock all YouTube formats. It only tries deno by
# default, so node is listed too. If neither is installed it warns and still works for now.
JS_RUNTIMES = {"deno": {}, "node": {}}


class _YtDlpLogger:
    """Forward yt-dlp's console output into our logging so it lands in the run's log files.

    yt-dlp's warnings are downgraded to DEBUG: the common ones ("Falling back on generic
    information extractor" for every Brettzone link) are expected, not faults. Real failures
    still raise `yt_dlp.utils.DownloadError`.
    """

    def debug(self, msg: str) -> None:
        """Log yt-dlp's info and debug messages (it routes both through `debug`)."""
        if not msg.startswith("[debug] "):
            logger.debug(msg)

    def warning(self, msg: str) -> None:
        """Log yt-dlp's warnings at DEBUG; see the class docstring for why."""
        logger.debug(msg)

    def error(self, msg: str) -> None:
        """Log yt-dlp's errors."""
        logger.error(msg)


def is_video_url(source: int | str) -> bool:
    """Check whether a `camera_number` is a web URL rather than a webcam index or local path.

    Args:
        source: The `camera_number` setting from main.py.

    Returns:
        bool: True for an `http://` or `https://` string.
    """
    return isinstance(source, str) and source.startswith(("http://", "https://"))


def resolve_video_source(source: int | str, download: bool, download_dir: str) -> int | str:
    """Return a `cv2.VideoCapture`-openable source for a webcam index, local path, or video URL.

    Args:
        source: Webcam index, local video path, or YouTube or direct video-file URL.
        download: For URLs, True saves the video into `download_dir` (skipped if it is already
            there) and returns the local path. False returns a URL that OpenCV streams from.
        download_dir: Folder downloaded videos are saved in, e.g. `main_files/test_videos`.

    Returns:
        int | str: `source` unchanged if it is not a URL. Otherwise the downloaded file's path,
            or the media URL to stream.

    Raises:
        yt_dlp.utils.DownloadError: If the URL can't be read or has no suitable video format.
    """
    if not is_video_url(source):
        return source

    options = {
        "format": VIDEO_FORMAT,
        "js_runtimes": JS_RUNTIMES,
        "logger": _YtDlpLogger(),
        "noprogress": True,
        "noplaylist": True,  # a watch URL with &list=... means just that one video
        # Saved as the video's title, kept ASCII with no spaces, e.g. "NHRL_Huey_vs_Prince.mp4".
        # A direct link's title is its file name, e.g. "Program-Feed-..._720p.mp4".
        "restrictfilenames": True,
        "outtmpl": os.path.join(download_dir, "%(title)s.%(ext)s"),
    }
    if download:
        options["progress_hooks"] = [make_download_progress_logger()]

    with yt_dlp.YoutubeDL(options) as ydl:
        logger.info(f"{'Downloading' if download else 'Streaming'} video from {source}")
        info = ydl.extract_info(source, download=download)

    if not download:
        logger.info(f"Streaming '{info['title']}' ({info.get('height') or '?'}p)")
        return info["url"]

    # yt-dlp skips the download when the file already exists but still reports its path here
    path = info["requested_downloads"][0]["filepath"]
    logger.info(f"Using downloaded video {path}")
    return path


def make_download_progress_logger() -> Callable[[dict], None]:
    """Build a yt-dlp progress hook that logs download progress every 10%.

    Returns:
        Callable[[dict], None]: Hook taking yt-dlp's progress dict (`status`,
            `downloaded_bytes`, `total_bytes`).
    """
    last_logged_tenths = -1

    def log_download_progress(status: dict) -> None:
        nonlocal last_logged_tenths
        total = status.get("total_bytes") or status.get("total_bytes_estimate")
        if status["status"] != "downloading" or not total:
            return
        tenths = int(10 * status["downloaded_bytes"] / total)
        if tenths > last_logged_tenths:
            last_logged_tenths = tenths
            logger.debug(f"Downloaded {10 * tenths}% of {total / 1e6:.0f} MB")

    return log_download_progress
