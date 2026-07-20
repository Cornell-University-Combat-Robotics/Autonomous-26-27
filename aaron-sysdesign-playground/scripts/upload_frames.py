#!/usr/bin/env python3
"""
Upload every frame in frames/ to Roboflow that isn't already uploaded --
no BrettZone API calls, no ffmpeg, no corner-picking. Just the upload step
pulled out of brettzone_frames.py standalone, for when you already have a
populated frames/ + manifest.json and just want to push to Roboflow (e.g.
you scraped without --upload, or want to re-upload under a different
batch name).

Usage:
    python upload_frames.py                     # upload under the default batch name
    python upload_frames.py --batch-name NAME   # upload under a custom batch name
    python upload_frames.py --dry-run           # report how many images would upload

Shares manifest.json's "uploaded" tracking with brettzone_frames.py, so
running either one won't re-upload what the other already sent.
"""

import argparse

from brettzone_frames import OUT_DIR, ROBOFLOW_BATCH, load_manifest, upload_to_roboflow


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch-name", default=ROBOFLOW_BATCH,
                     help=f"Roboflow batch name for this upload (default: {ROBOFLOW_BATCH})")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    manifest = load_manifest()
    files = sorted(OUT_DIR.glob("*.jpg"))
    todo = [f for f in files if f.name not in set(manifest["uploaded"])]

    if args.dry_run:
        print(f"Would upload {len(todo)} images to Roboflow (batch: {args.batch_name}).")
        return

    upload_to_roboflow(files, manifest, args.batch_name)


if __name__ == "__main__":
    main()
