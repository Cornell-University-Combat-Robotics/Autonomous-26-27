"""Shared helpers for syncing testing videos between this repo and the team's Box folder.

Box Drive (the desktop app) mounts the team's Box account as a normal folder on
disk, so "syncing" here is just copying files to/from that mounted folder — no
API credentials needed. If Box Drive isn't mounted at one of the default
locations below (e.g. on Windows, or a nonstandard install), point
BOX_VIDEOS_DIR at the Box folder yourself.
"""

import os
import shutil
from pathlib import Path

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".webm"}

BOX_RELATIVE_PATH = "Combat Robotics @ Cornell (CRC)/2026-2027/autonomous-videos"

_BOX_DRIVE_ROOT_CANDIDATES = [
    Path.home() / "Library/CloudStorage/Box-Box",  # macOS, Box Drive
    Path.home() / "Box",  # Windows/macOS, some Box Drive/Box Sync installs
    Path.home() / "Box Sync",  # legacy Box Sync
]

REPO_ROOT = Path(__file__).resolve().parent.parent
LOCAL_VIDEOS_DIR = REPO_ROOT / "videos"


def get_box_videos_dir() -> Path:
    """Resolve the Box folder videos are synced with, creating it if needed."""
    override = os.environ.get("BOX_VIDEOS_DIR")
    if override:
        box_dir = Path(override).expanduser()
        if not box_dir.is_dir():
            raise SystemExit(
                f"BOX_VIDEOS_DIR is set to {box_dir}, but that folder does not exist."
            )
        return box_dir

    for root in _BOX_DRIVE_ROOT_CANDIDATES:
        if root.is_dir():
            box_dir = root / BOX_RELATIVE_PATH
            box_dir.mkdir(parents=True, exist_ok=True)
            return box_dir

    raise SystemExit(
        "Could not find a mounted Box Drive folder.\n"
        "Install and sign in to Box Drive (https://box.com/drive), or if it's\n"
        "mounted somewhere nonstandard, set BOX_VIDEOS_DIR to the full path of\n"
        "the Box videos folder, e.g.\n"
        '  BOX_VIDEOS_DIR="/path/to/Box/autonomous-videos" uv run scripts/download_videos.py'
    )


def list_videos(directory: Path) -> dict[str, Path]:
    """Map filename -> path for every video file directly inside `directory`."""
    if not directory.is_dir():
        return {}
    return {
        p.name: p
        for p in directory.iterdir()
        if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS
    }


def list_subdirs(directory: Path) -> list[str]:
    """Names of `directory`'s immediate subdirectories (e.g. "huey", "other")."""
    if not directory.is_dir():
        return []
    return sorted(
        p.name for p in directory.iterdir() if p.is_dir() and not p.name.startswith(".")
    )


def _sync_flat(src_dir: Path, dest_dir: Path) -> tuple[int, int]:
    """Copy every video directly in `src_dir` not already present in `dest_dir`.

    "Already present" means same filename and size. Same filename with a
    different size is left alone and reported, rather than overwritten.
    Returns (copied_count, skipped_count).
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    src_videos = list_videos(src_dir)
    dest_videos = list_videos(dest_dir)

    if not src_videos:
        print(f"No video files found in {src_dir}")
        return 0, 0

    copied = 0
    skipped = 0
    for name, src_path in sorted(src_videos.items()):
        existing = dest_videos.get(name)
        if existing is not None:
            if existing.stat().st_size == src_path.stat().st_size:
                print(f"skip     {name} (already present)")
                skipped += 1
                continue
            print(
                f"WARNING  {name} exists in both places with different sizes — "
                "leaving the existing copy alone. Rename one of them if they're "
                "actually different videos."
            )
            skipped += 1
            continue

        print(f"copy     {name}")
        shutil.copy2(src_path, dest_dir / name)
        copied += 1

    return copied, skipped


def copy_missing(
    src_root: Path, dest_root: Path, only: str | None = None
) -> tuple[int, int]:
    """Copy every video under `src_root` not already under `dest_root`.

    Videos are organized in one level of subdirectories (e.g. huey/, other/),
    mirrored by name between src and dest, plus any loose videos directly in
    the root. Pass `only` (a subdirectory name) to sync just that one category
    instead of everything. Returns (copied_count, skipped_count).
    """
    if only:
        if not (src_root / only).is_dir():
            available = list_subdirs(src_root)
            raise SystemExit(
                f"No such directory '{only}' in {src_root}.\n"
                f"Available: {', '.join(available) if available else '(none yet)'}"
            )
        categories = [only]
    else:
        categories = list_subdirs(src_root)

    total_copied = 0
    total_skipped = 0

    if not only:
        print(f"-- {src_root} --")
        copied, skipped = _sync_flat(src_root, dest_root)
        total_copied += copied
        total_skipped += skipped

    for name in categories:
        print(f"-- {name}/ --")
        copied, skipped = _sync_flat(src_root / name, dest_root / name)
        total_copied += copied
        total_skipped += skipped

    return total_copied, total_skipped
