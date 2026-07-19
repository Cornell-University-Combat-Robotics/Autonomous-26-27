#!/usr/bin/env python3
"""Upload local testing videos that aren't already in the team's Box folder.

See box_sync.py for how the Box folder is located.
"""

import argparse

from box_sync import LOCAL_VIDEOS_DIR, copy_missing, get_box_videos_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dir",
        metavar="NAME",
        help="only upload this subdirectory (e.g. huey) instead of everything",
    )
    args = parser.parse_args()

    box_dir = get_box_videos_dir()
    print(f"Local folder: {LOCAL_VIDEOS_DIR}")
    print(f"Box folder:   {box_dir}\n")

    copied, skipped = copy_missing(LOCAL_VIDEOS_DIR, box_dir, only=args.dir)

    print(f"\nUploaded {copied} video(s), {skipped} already present in Box.")


if __name__ == "__main__":
    main()
