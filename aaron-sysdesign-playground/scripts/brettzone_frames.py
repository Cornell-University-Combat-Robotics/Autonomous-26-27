#!/usr/bin/env python3
"""
Scrape a few frames from every 2026 NHRL fight on BrettZone and upload to Roboflow.

No full video downloads: recordings are plain MP4s on object storage, so
`ffmpeg -ss T -i URL -frames:v 1` seeks via HTTP range requests and only pulls
a few MB per frame. Safe to run locally.

Usage:
    pip install requests roboflow
    python brettzone_frames.py                 # scrape frames only
    python brettzone_frames.py --upload        # scrape + upload to Roboflow
    python brettzone_frames.py --dry-run       # just list what would be scraped

Resumable: progress tracked in manifest.json; rerun to continue where you left off.
"""

import argparse
import concurrent.futures as cf
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import requests

# ----------------------------- config ---------------------------------------

API = "https://brettzone.nhrl.io/brettZone/api.php"
HEADERS = {"X-API-Key": "huey-yolo-dataset"}  # any value; identifies you politely

OUT_DIR = Path("frames")
MANIFEST = Path("manifest.json")

YEAR = 2026
WEIGHT_CLASSES = {3}          # lbs; BrettZone files XP brackets under 3lb too
PUBLIC_ONLY = True            # unlisted 2026 brackets are mostly test/dup copies
CAMERA_REGEX = r"Overhead"    # e.g. r"Overhead|Ceiling" or r".*" for every angle
QUALITY = "proxy720"          # proxy720 | proxy360 | s3path (original)
FRAMES_PER_VIDEO = 4          # sampled evenly across the fight
SKIP_HEAD_SECONDS = 8         # skip the very start (bots parked in squares)
MAX_WORKERS = 6               # be polite to their CDN
TOURNAMENT_SKIP = re.compile(r"livestats|test|dummy|soccer", re.I)

# Roboflow (only needed with --upload)
ROBOFLOW_API_KEY = "Y7v6MgucolBH3nV90OeP"
ROBOFLOW_WORKSPACE = "crc-autonomous"
ROBOFLOW_PROJECT = "nhrl-sampled-segmentation"
ROBOFLOW_BATCH = "brettzone-2026"

# ----------------------------- helpers --------------------------------------


def api_get(path: str, retries: int = 3) -> dict:
    for attempt in range(retries):
        try:
            r = requests.get(f"{API}{path}", headers=HEADERS, timeout=30)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt == retries - 1:
                raise
            time.sleep(2 * (attempt + 1))
    return {}


def load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text())
    return {"done": {}, "uploaded": []}


def save_manifest(m: dict) -> None:
    MANIFEST.write_text(json.dumps(m, indent=1))


def year_of(t: dict) -> int | None:
    for key in ("startTime", "endTime", "createTime"):
        v = t.get(key) or ""
        if v.startswith(("20",)):
            return int(v[:4])
    return None


def sample_times(offset: float, match_len: float, n: int) -> list[float]:
    """Evenly spaced timestamps inside the fight, skipping the opening seconds."""
    start = offset + SKIP_HEAD_SECONDS
    end = offset + max(match_len - 5, SKIP_HEAD_SECONDS + 5)
    if n == 1:
        return [start + (end - start) / 2]
    step = (end - start) / (n - 1)
    return [round(start + i * step, 2) for i in range(n)]


def extract_frame(url: str, t: float, out_path: Path) -> bool:
    """Grab one frame from a remote MP4. -ss before -i => range-request seek."""
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-ss", str(t), "-i", url,
        "-frames:v", "1", "-q:v", "2", "-y", str(out_path),
    ]
    try:
        subprocess.run(cmd, check=True, timeout=120, capture_output=True)
        return out_path.exists() and out_path.stat().st_size > 10_000
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


# ----------------------------- pipeline -------------------------------------


def get_2026_tournaments() -> list[dict]:
    ts = api_get("/tournaments")["tournaments"]
    keep = []
    for t in ts:
        if year_of(t) != YEAR:
            continue
        if t.get("WeightClass") not in WEIGHT_CLASSES:
            continue
        if PUBLIC_ONLY and t.get("privacy") != "public":
            continue
        if TOURNAMENT_SKIP.search(t["tournamentID"] + t["tournamentName"]):
            continue
        keep.append(t)
    return keep


def iter_2026_fights(tournament_ids: set[str]):
    """Fetch each tournament's fight list directly (has the real gameID,
    unlike the global /fights feed, which only exposes the bracket label
    e.g. "W:4-1" under "id" and duplicates entries)."""
    for tid in tournament_ids:
        data = api_get(f"/tournaments/{tid}/fights")
        for f in data.get("fights", []):
            if not f.get("id"):
                continue
            if not f.get("matchLength") or not f.get("cams"):
                continue  # never fought / no video
            yield f


def process_fight(tid: str, fight: dict, manifest: dict, dry: bool) -> list[Path]:
    
    
    game_id = fight.get("id")
    if not game_id:
        print(f"  ! skipping malformed fight record: {list(fight.keys())}")
        return []

    key = f"{tid}/{game_id}"
    if key in manifest["done"]:
        return []

    try:
        feed = api_get(f"/video-feeds/fight/{tid}/{game_id}")
    except Exception as e:
        print(f"  ! feed fetch failed {key}: {e}")
        return []

    offset = float(feed.get("fightStartOffset") or 10.0)
    match_len = float(fight.get("matchLength") or 180)
    cams = [r for r in feed.get("recordings", [])
            if re.search(CAMERA_REGEX, r.get("camera", ""))]
    if not cams:
        manifest["done"][key] = "no-matching-camera"
        return []

    p1 = fight.get("player1clean") or "unknown"
    p2 = fight.get("player2clean") or "unknown"

    new_files = []
    for rec in cams:
        url = rec.get(QUALITY) or rec.get("s3path")
        if not url:
            continue
        cam = rec["camera"]
        for t in sample_times(offset, match_len, FRAMES_PER_VIDEO):
            name = (f"{tid}__{game_id}__{p1}-vs-{p2}__{cam}__{t:07.1f}s.jpg"
                     .replace("/", "-"))
            out = OUT_DIR / name
            if out.exists():
                new_files.append(out)
                continue
            if dry:
                print(f"  would extract {name}")
                new_files.append(out)
                continue
            if extract_frame(url, t, out):
                new_files.append(out)
            else:
                print(f"  ! frame failed: {name}")
    if not dry:
        manifest["done"][key] = len(new_files)
    return new_files


def upload_to_roboflow(files: list[Path], manifest: dict) -> None:
    from roboflow import Roboflow
    rf = Roboflow(api_key=ROBOFLOW_API_KEY)
    project = rf.workspace(ROBOFLOW_WORKSPACE).project(ROBOFLOW_PROJECT)
    uploaded = set(manifest["uploaded"])
    todo = [f for f in files if f.name not in uploaded]
    print(f"Uploading {len(todo)} images to Roboflow…")
    for i, f in enumerate(todo, 1):
        try:
            project.upload(
                image_path=str(f),
                batch_name=ROBOFLOW_BATCH,
                num_retry_uploads=3,
                tag_names=[f.name.split("__")[0]],  # tag = tournament ID
            )
            manifest["uploaded"].append(f.name)
        except Exception as e:
            print(f"  ! upload failed {f.name}: {e}")
        if i % 50 == 0:
            save_manifest(manifest)
            print(f"  {i}/{len(todo)}")
    save_manifest(manifest)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--upload", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit-fights", type=int, default=0,
                    help="stop after N fights (for testing)")
    args = ap.parse_args()

    OUT_DIR.mkdir(exist_ok=True)
    manifest = load_manifest()

    tournaments = get_2026_tournaments()
    print(f"{len(tournaments)} tournaments in {YEAR}:")
    for t in tournaments:
        print(f"  {t['tournamentID']:30s} {t['tournamentName']}")

    tids = {t["tournamentID"] for t in tournaments}
    all_new: list[Path] = []
    n_fights = 0
    with cf.ThreadPoolExecutor(MAX_WORKERS) as pool:
        futures = []
        for f in iter_2026_fights(tids):
            if args.limit_fights and n_fights >= args.limit_fights:
                break
            futures.append(pool.submit(
                process_fight, f["tournamentID"], f, manifest, args.dry_run))
            n_fights += 1
        for i, fut in enumerate(cf.as_completed(futures), 1):
            all_new.extend(fut.result())
            if i % 25 == 0:
                save_manifest(manifest)
    save_manifest(manifest)

    processed = n_fights if args.dry_run else len(manifest["done"])
    print(f"\nDone. {len(all_new)} frames in {OUT_DIR}/ "
          f"({processed} fights processed total).")

    if args.upload and not args.dry_run:
        # upload everything on disk not yet uploaded, not just this run's files
        upload_to_roboflow(sorted(OUT_DIR.glob("*.jpg")), manifest)


if __name__ == "__main__":
    main()
