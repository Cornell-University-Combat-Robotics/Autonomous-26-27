#!/usr/bin/env python3
"""
Scrape a few frames from NHRL fights on BrettZone and upload to Roboflow.

No full video downloads: recordings are plain MP4s on object storage, so
`ffmpeg -ss T -i URL -frames:v 1` seeks via HTTP range requests and only pulls
a few MB per frame. Safe to run locally.

Each frame is then rectified to a top-down 640x640 view of the arena floor
by the warp/ service (see warp/README.md). A camera isn't assumed to hold
still for a whole tournament: the first time a camera shows up, a window
pops up to click its 4 floor corners; for every match after that on the
same camera, another window shows that match's frame warped with the
current corners and asks you to confirm it or redo it -- a redo replaces
the camera's corners going forward, used for that match and every later
one on it until reviewed again. Corners are cached in manifest.json, so a
resumed run only reviews matches it hasn't gotten to yet.

Usage:
    pip install requests roboflow opencv-python
    python brettzone_frames.py                 # scrape frames (reviews every match's warp)
    python brettzone_frames.py --upload        # scrape + upload to Roboflow
    python brettzone_frames.py --dry-run       # just list what would be scraped, no prompts
    python brettzone_frames.py --recalibrate   # forget cached corners, re-prompt every camera

    # 50 frames/match from every match "huey" fought in, skipping May 2026 only
    # (May 2025 IDs use "may25", so "may26" leaves that year's May alone)
    python brettzone_frames.py --robot huey --exclude-tournament may26 \
        --frames-per-match 50 --upload

    # you clicked a bad quad for a whole camera: wipe its local frames,
    # Roboflow uploads, and cached corners, then reprocess + re-upload it
    python brettzone_frames.py --redo nhrl_jun26_3lb/Cage-2-Overhead-High --upload

    # a camera moved mid-tournament and only ONE match needs different
    # corners: wipe + reprompt just that match, without touching the rest
    # of that camera's (already-correct) matches
    python brettzone_frames.py --redo-match nhrl_apr26_3lb/EX-1675513be398446a/Cage-5-Overhead-High --upload

While picking a camera's initial corners: click its 4 floor corners in
any order, right-click to undo the last point, Enter/Space to confirm,
'r' to reset, 's' to skip this camera (leave it unwarped), Esc to stop
reviewing for the rest of this run (cameras already reviewed keep working
as last set; matches not yet reached use each camera's current warp
unchecked).

While reviewing an already-calibrated camera's warp on a new match:
Enter/Space to confirm it as still correct, 'r' to redo its corners
(opens the same picker as above and replaces the camera's calibration
from this match onward), Esc to stop reviewing for the rest of this run.

Resumable: progress tracked in manifest.json; rerun to continue where you left off.
"""

import argparse
import concurrent.futures as cf
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import cv2
import numpy as np
import requests

# warp/ lives at the repo root, a level up from scripts/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from warp import FloorWarper, close_review_window, pick_corners, review_warp  # noqa: E402

# ----------------------------- config ---------------------------------------

API = "https://brettzone.nhrl.io/brettZone/api.php"
HEADERS = {"X-API-Key": "huey-yolo-dataset"}  # any value; identifies you politely

OUT_DIR = Path("frames")
MANIFEST = Path("manifest.json")

YEARS = {2025, 2026}
WEIGHT_CLASSES = {3}          # lbs; BrettZone files XP brackets under 3lb too
PUBLIC_ONLY = True            # unlisted brackets are mostly test/dup copies
CAMERA_REGEX = r"Overhead"    # e.g. r"Overhead|Ceiling" or r".*" for every angle
QUALITY = "proxy720"          # proxy720 | proxy360 | s3path (original)
FRAMES_PER_VIDEO = 4          # sampled evenly across the fight
SKIP_HEAD_SECONDS = 8         # skip the very start (bots parked in squares)
MAX_WORKERS = 6               # be polite to their CDN
TOURNAMENT_SKIP = re.compile(r"livestats|test|dummy|soccer", re.I)

WARPER = FloorWarper()

# Roboflow (only needed with --upload)
ROBOFLOW_API_KEY = "Y7v6MgucolBH3nV90OeP"
ROBOFLOW_WORKSPACE = "crc-autonomous"
ROBOFLOW_PROJECT = "nhrl-sampled-segmentation"
ROBOFLOW_BATCH = "50-huey-no-may"

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
        m = json.loads(MANIFEST.read_text())
        m.setdefault("corners", {})
        return m
    return {"done": {}, "uploaded": [], "corners": {}}


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


def warp_frame(path: Path, key: str) -> None:
    """Rectify an already-extracted frame in place to a top-down view.
    No-op (frame left as extracted) until key's camera is calibrated."""
    img = cv2.imread(str(path))
    if img is None:
        return
    cv2.imwrite(str(path), WARPER.warp(img, key))


def _prompt_and_store(key: str, url: str, preview_t: float, manifest: dict, title: str | None = None) -> bool:
    """Main-thread only: extracts a preview frame from url and shows the
    corner picker for it, caching the result (calibrated or skipped) under
    key in both WARPER and manifest["corners"]. Returns False if the user
    asked to stop calibrating for the rest of this run."""
    with tempfile.TemporaryDirectory() as tmpdir:
        preview_path = Path(tmpdir) / "preview.jpg"
        if not extract_frame(url, preview_t, preview_path):
            print(f"  ! couldn't fetch a preview frame for {key}; leaving unwarped")
            WARPER.skip(key)
            manifest["corners"][key] = None
            save_manifest(manifest)
            return True
        img = cv2.imread(str(preview_path))

    result = pick_corners(img, title or key)
    if isinstance(result, str):  # "abort"
        return False
    if result is None:
        WARPER.skip(key)
        manifest["corners"][key] = None
    else:
        WARPER.calibrate(key, result)
        manifest["corners"][key] = result.tolist()
    save_manifest(manifest)
    return True


def review_or_calibrate(tid: str, game_id: str, cam: str, url: str, preview_t: float, manifest: dict) -> bool:
    """Main-thread only, called for every match: if cam isn't calibrated
    yet for this tournament, prompts for its initial corners. If it is,
    shows this match's frame warped with the CURRENT calibration and asks
    to confirm or redo it -- a camera can drift or get bumped mid-tournament,
    so its calibration isn't assumed to keep holding. Redoing replaces cam's
    calibration going forward (used for this match and every later one on
    it, until reviewed again). Returns False if the user asked to stop
    reviewing for the rest of this run."""
    key = f"{tid}/{cam}"
    if not WARPER.has(key):
        return _prompt_and_store(key, url, preview_t, manifest, title=key)

    with tempfile.TemporaryDirectory() as tmpdir:
        preview_path = Path(tmpdir) / "preview.jpg"
        if not extract_frame(url, preview_t, preview_path):
            print(f"  ! couldn't fetch a preview frame for {tid}/{game_id}; "
                  f"using {key}'s current warp unchecked")
            return True
        img = cv2.imread(str(preview_path))

    decision = review_warp(WARPER.warp(img, key), title=f"{tid}/{game_id} on {cam}")
    if decision == "confirm":
        return True
    if decision == "abort":
        return False
    return _prompt_and_store(key, url, preview_t, manifest, title=f"{key} (redo)")  # decision == "redo"


def resolve_warp_key(tid: str, game_id: str, cam: str) -> str:
    """Prefer a match-specific override (set via --redo-match) over cam's
    general, tournament-wide calibration."""
    override = f"{tid}/{game_id}/{cam}"
    return override if WARPER.has(override) else f"{tid}/{cam}"


# ----------------------------- pipeline -------------------------------------


def get_tournaments(exclude_patterns: list[str] | None = None) -> list[dict]:
    ts = api_get("/tournaments")["tournaments"]
    extra_skip = [re.compile(p, re.I) for p in (exclude_patterns or [])]
    keep = []
    for t in ts:
        if year_of(t) not in YEARS:
            continue
        if t.get("WeightClass") not in WEIGHT_CLASSES:
            continue
        if PUBLIC_ONLY and t.get("privacy") != "public":
            continue
        haystack = t["tournamentID"] + t["tournamentName"]
        if TOURNAMENT_SKIP.search(haystack):
            continue
        if any(rx.search(haystack) for rx in extra_skip):
            continue
        keep.append(t)
    return keep


def fight_has_robot(fight: dict, robot: str) -> bool:
    """Case-insensitive substring match against either competitor's clean name."""
    robot = robot.lower()
    p1 = (fight.get("player1clean") or "").lower()
    p2 = (fight.get("player2clean") or "").lower()
    return robot in p1 or robot in p2


def iter_fights(tournament_ids: set[str], robot: str | None = None):
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
            if robot and not fight_has_robot(f, robot):
                continue
            yield f


def process_fight(tid: str, fight: dict, feed: dict, manifest: dict, dry: bool) -> list[Path]:
    game_id = fight.get("id")
    if not game_id:
        print(f"  ! skipping malformed fight record: {list(fight.keys())}")
        return []

    key = f"{tid}/{game_id}"
    if key in manifest["done"]:
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
        # offset itself: one frame from the match's start, before SKIP_HEAD_SECONDS
        # trims the bots-parked-in-squares opening out of the evenly sampled ones.
        for t in [offset, *sample_times(offset, match_len, FRAMES_PER_VIDEO)]:
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
                warp_frame(out, resolve_warp_key(tid, game_id, cam))
                new_files.append(out)
            else:
                print(f"  ! frame failed: {name}")
    if not dry:
        manifest["done"][key] = len(new_files)
    return new_files


def tags_for(f: Path) -> list[str]:
    """Tournament ID plus each robot's clean name, parsed from the
    filename ({tid}__{game_id}__{p1}-vs-{p2}__{cam}__{t}s.jpg) since
    that's all that's left by upload time -- p1/p2 aren't otherwise
    tracked past when the frame was written."""
    parts = f.name.split("__")
    tags = [parts[0]]
    if len(parts) > 2:
        tags += parts[2].split("-vs-")
    return tags


def upload_to_roboflow(files: list[Path], manifest: dict, batch_name: str = ROBOFLOW_BATCH) -> None:
    from roboflow import Roboflow
    rf = Roboflow(api_key=ROBOFLOW_API_KEY)
    project = rf.workspace(ROBOFLOW_WORKSPACE).project(ROBOFLOW_PROJECT)
    uploaded = set(manifest["uploaded"])
    todo = [f for f in files if f.name not in uploaded]
    print(f"Uploading {len(todo)} images to Roboflow (batch: {batch_name})…")
    for i, f in enumerate(todo, 1):
        try:
            project.upload(
                image_path=str(f),
                batch_name=batch_name,
                num_retry_uploads=3,
                tag_names=tags_for(f),
            )
            manifest["uploaded"].append(f.name)
        except Exception as e:
            print(f"  ! upload failed {f.name}: {e}")
        if i % 50 == 0:
            save_manifest(manifest)
            print(f"  {i}/{len(todo)}")
    save_manifest(manifest)


def delete_from_roboflow(names: set[str], tag: str) -> None:
    """Delete every image tagged tag whose filename is in names. Roboflow
    doesn't support looking images up by filename directly, so this pages
    through search(tag=...) (capped at 100 results per call) matching
    names against it."""
    from roboflow import Roboflow
    rf = Roboflow(api_key=ROBOFLOW_API_KEY)
    project = rf.workspace(ROBOFLOW_WORKSPACE).project(ROBOFLOW_PROJECT)

    remaining = set(names)
    ids = []
    offset, limit = 0, 100
    while remaining:
        try:
            results = project.search(tag=tag, fields=["id", "name"], limit=limit, offset=offset)
        except Exception as e:
            print(f"  ! Roboflow search failed: {e}")
            break
        if not results:
            break
        for r in results:
            if r["name"] in remaining:
                ids.append(r["id"])
                remaining.discard(r["name"])
        if len(results) < limit:
            break
        offset += limit

    if ids:
        try:
            project.delete_images(ids)
            print(f"  deleted {len(ids)} images from Roboflow")
        except Exception as e:
            print(f"  ! Roboflow deletion failed: {e}")
    if remaining:
        print(f"  ! {len(remaining)} previously-uploaded filenames weren't found "
              f"on Roboflow (already removed there?)")


def redo_camera(tid: str, cam: str, manifest: dict, dry: bool) -> None:
    """Wipe everything for one (tournament, camera): local frame files,
    their fight-level 'done' tracking, their Roboflow uploads, and the
    cached floor corners for that camera -- so the rest of this run
    re-prompts for it and reprocesses (and, with --upload, re-uploads)
    every match that used it. Only touches matches that already have
    local frames for cam; a match that never produced any (every
    extraction attempt failed) is left alone."""
    key = f"{tid}/{cam}"
    affected_files = []
    affected_game_ids = set()
    for p in sorted(OUT_DIR.glob(f"{tid}__*.jpg")):
        parts = p.stem.split("__")
        if len(parts) < 4 or parts[0] != tid or parts[3] != cam:
            continue
        affected_files.append(p)
        affected_game_ids.add(parts[1])

    if not affected_files:
        print(f"--redo {key}: no local frames found; nothing to wipe.")
        return

    uploaded_names = {p.name for p in affected_files if p.name in manifest["uploaded"]}
    print(f"--redo {key}: {len(affected_files)} frames across "
          f"{len(affected_game_ids)} matches ({len(uploaded_names)} on Roboflow)"
          f"{' [dry run, not wiping]' if dry else ''}")
    if dry:
        return

    if uploaded_names:
        delete_from_roboflow(uploaded_names, tag=tid)
        manifest["uploaded"] = [n for n in manifest["uploaded"] if n not in uploaded_names]
    for p in affected_files:
        p.unlink(missing_ok=True)
    for gid in affected_game_ids:
        manifest["done"].pop(f"{tid}/{gid}", None)
    manifest["corners"].pop(key, None)
    save_manifest(manifest)


def redo_match(tid: str, game_id: str, cam: str, manifest: dict, dry: bool) -> None:
    """Wipe local frames, Roboflow uploads, and done-tracking for ONE
    match+camera, then prompt for corners just for that match, stored as
    an override separate from cam's general calibration (see
    resolve_warp_key) -- e.g. for the one match where a camera moved
    mid-tournament, without disturbing every other match on that camera."""
    fight_key = f"{tid}/{game_id}"
    override_key = f"{tid}/{game_id}/{cam}"

    affected_files = []
    for p in sorted(OUT_DIR.glob(f"{tid}__*.jpg")):
        parts = p.stem.split("__")
        if len(parts) < 4 or parts[0] != tid or parts[1] != game_id or parts[3] != cam:
            continue
        affected_files.append(p)

    uploaded_names = {p.name for p in affected_files if p.name in manifest["uploaded"]}
    print(f"--redo-match {override_key}: {len(affected_files)} frames "
          f"({len(uploaded_names)} on Roboflow)"
          f"{' [dry run, not wiping]' if dry else ''}")
    if dry:
        return

    if uploaded_names:
        delete_from_roboflow(uploaded_names, tag=tid)
        manifest["uploaded"] = [n for n in manifest["uploaded"] if n not in uploaded_names]
    for p in affected_files:
        p.unlink(missing_ok=True)
    manifest["done"].pop(fight_key, None)
    manifest["corners"].pop(override_key, None)

    try:
        fights = api_get(f"/tournaments/{tid}/fights").get("fights", [])
        feed = api_get(f"/video-feeds/fight/{tid}/{game_id}")
    except Exception as e:
        print(f"  ! couldn't fetch match data for {override_key}: {e}")
        save_manifest(manifest)
        return
    fight = next((f for f in fights if f.get("id") == game_id), None)
    if fight is None:
        print(f"  ! {fight_key} not found in {tid}'s fight list")
        save_manifest(manifest)
        return

    rec = next((r for r in feed.get("recordings", []) if r.get("camera") == cam), None)
    url = rec and (rec.get(QUALITY) or rec.get("s3path"))
    if not url:
        print(f"  ! no {cam} recording found for {fight_key}")
        save_manifest(manifest)
        return

    offset = float(feed.get("fightStartOffset") or 10.0)
    match_len = float(fight.get("matchLength") or 180)
    preview_t = sample_times(offset, match_len, 1)[0]
    _prompt_and_store(override_key, url, preview_t, manifest, title=f"{override_key} (match override)")


def main() -> None:
    global FRAMES_PER_VIDEO
    ap = argparse.ArgumentParser()
    ap.add_argument("--upload", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit-fights", type=int, default=0,
                    help="stop after N fights (for testing)")
    ap.add_argument("--robot", metavar="NAME",
                    help="only pull frames from matches this robot competed in -- "
                         "case-insensitive substring match against player1clean/"
                         "player2clean, e.g. --robot huey")
    ap.add_argument("--exclude-tournament", metavar="PATTERN", action="append", default=[],
                    help="skip tournaments whose ID or name matches this regex "
                         "(case-insensitive); can be passed multiple times, e.g. "
                         "--exclude-tournament may excludes every May tournament")
    ap.add_argument("--frames-per-match", type=int, default=FRAMES_PER_VIDEO,
                    help="frames sampled per match, evenly spaced across the fight "
                         "(default: %(default)s)")
    ap.add_argument("--recalibrate", action="store_true",
                    help="forget cached floor corners and re-prompt for every camera")
    ap.add_argument("--redo", metavar="TOURNAMENT_ID/CAMERA",
                    help="wipe local frames, Roboflow uploads, done-tracking, and "
                         "cached corners for one tournament+camera, then reprocess "
                         "it as part of this run -- combine with --upload to "
                         "replace the bad images on Roboflow")
    ap.add_argument("--redo-match", metavar="TOURNAMENT_ID/GAME_ID/CAMERA",
                    help="wipe local frames, Roboflow uploads, and done-tracking "
                         "for ONE match, then prompt for corners just for that "
                         "match -- kept separate from the camera's general "
                         "calibration, for e.g. the one match where a camera "
                         "moved mid-tournament, without touching the rest of that "
                         "camera's matches. Combine with --upload to replace the "
                         "bad images on Roboflow")
    args = ap.parse_args()

    OUT_DIR.mkdir(exist_ok=True)
    manifest = load_manifest()

    FRAMES_PER_VIDEO = args.frames_per_match

    if args.redo:
        tid, _, cam = args.redo.partition("/")
        if not cam:
            ap.error("--redo expects TOURNAMENT_ID/CAMERA, e.g. nhrl_jun26_3lb/Cage-2-Overhead-High")
        redo_camera(tid, cam, manifest, args.dry_run)

    if args.redo_match:
        parts = args.redo_match.split("/")
        if len(parts) != 3:
            ap.error("--redo-match expects TOURNAMENT_ID/GAME_ID/CAMERA, e.g. "
                      "nhrl_apr26_3lb/EX-1675513be398446a/Cage-5-Overhead-High")
        redo_match(*parts, manifest, args.dry_run)

    if args.recalibrate:
        manifest["corners"] = {}
    for key, pts in manifest["corners"].items():
        if pts is None:
            WARPER.skip(key)
        else:
            WARPER.calibrate(key, np.array(pts, dtype=np.float32))

    tournaments = get_tournaments(args.exclude_tournament)
    print(f"{len(tournaments)} tournaments in {sorted(YEARS)}:")
    for t in tournaments:
        print(f"  {t['tournamentID']:30s} {t['tournamentName']}")

    tids = {t["tournamentID"] for t in tournaments}
    all_new: list[Path] = []
    n_fights = 0
    reviewing = not args.dry_run
    with cf.ThreadPoolExecutor(MAX_WORKERS) as pool:
        futures = []
        for f in iter_fights(tids, args.robot):
            if args.limit_fights and n_fights >= args.limit_fights:
                break
            tid = f["tournamentID"]
            game_id = f["id"]
            try:
                feed = api_get(f"/video-feeds/fight/{tid}/{game_id}")
            except Exception as e:
                print(f"  ! feed fetch failed {tid}/{game_id}: {e}")
                continue

            # Nothing new to review for a fight already processed -- skip
            # straight to (re-)submitting it, which process_fight itself
            # will short-circuit on via manifest["done"].
            if reviewing and f"{tid}/{game_id}" not in manifest["done"]:
                offset = float(feed.get("fightStartOffset") or 10.0)
                match_len = float(f.get("matchLength") or 180)
                preview_t = sample_times(offset, match_len, 1)[0]
                for rec in feed.get("recordings", []):
                    if not re.search(CAMERA_REGEX, rec.get("camera", "")):
                        continue
                    url = rec.get(QUALITY) or rec.get("s3path")
                    if not url:
                        continue
                    if not review_or_calibrate(tid, game_id, rec["camera"], url, preview_t, manifest):
                        reviewing = False
                        print("Stopped reviewing; any other matches this run "
                              "will use each camera's current warp unchecked.")
                        break

            futures.append(pool.submit(process_fight, tid, f, feed, manifest, args.dry_run))
            n_fights += 1
        for i, fut in enumerate(cf.as_completed(futures), 1):
            all_new.extend(fut.result())
            if i % 25 == 0:
                save_manifest(manifest)
    save_manifest(manifest)
    close_review_window()

    processed = n_fights if args.dry_run else len(manifest["done"])
    print(f"\nDone. {len(all_new)} frames in {OUT_DIR}/ "
          f"({processed} fights processed total, "
          f"{len(WARPER.calibrated_keys)} cameras calibrated).")

    if args.upload and not args.dry_run:
        # upload everything on disk not yet uploaded, not just this run's files
        upload_to_roboflow(sorted(OUT_DIR.glob("*.jpg")), manifest)


if __name__ == "__main__":
    main()
