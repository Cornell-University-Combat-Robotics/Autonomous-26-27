#!/usr/bin/env python3
"""Download testing videos from the team's Box folder into videos/.

See box_sync.py for how the Box folder is located.
"""

import argparse

from box_sync import LOCAL_VIDEOS_DIR, copy_missing, get_box_videos_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dir",
        metavar="NAME",
        help="only download this subdirectory (e.g. huey) instead of everything",
    )
    args = parser.parse_args()

    box_dir = get_box_videos_dir()
    print(f"Box folder:   {box_dir}")
    print(f"Local folder: {LOCAL_VIDEOS_DIR}\n")

    copied, skipped = copy_missing(box_dir, LOCAL_VIDEOS_DIR, only=args.dir)

    print(f"\nDownloaded {copied} video(s), {skipped} already present locally.")


if __name__ == "__main__":
    main()
