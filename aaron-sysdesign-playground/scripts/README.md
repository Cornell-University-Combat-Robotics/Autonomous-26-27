# scripts/

Utility scripts for the repo. Not part of the camera → object_detection → algorithm pipeline itself.

## Testing videos (Box sync)

Testing videos live in the team's Box folder, not in git — some of them are too large for the repo. `videos/` here is a local, gitignored copy.

Box Drive (the desktop app, https://box.com/drive) mounts the team's Box account as a normal folder on disk, so these scripts just copy files to/from it — no API credentials involved. They default to `Combat Robotics @ Cornell (CRC)/2026-2027/autonomous-videos` under wherever Box Drive is mounted. If that's not found (e.g. on Windows, or a nonstandard install), set `BOX_VIDEOS_DIR` to the full path of the Box videos folder yourself:

```
BOX_VIDEOS_DIR="/path/to/Box/autonomous-videos" uv run scripts/download_videos.py
```

Videos are organized into subdirectories by category (e.g. `huey/`, `other/`), mirrored between `videos/` and Box. Pull down every video currently in Box into `videos/`:

```
uv run scripts/download_videos.py
```

Or just one category, if you don't want everything (e.g. Box's `other/` has 50 videos you don't care about, but you want the 3 in `huey/`):

```
uv run scripts/download_videos.py --dir huey
```

Push up any video you've added to `videos/` locally that isn't in Box yet (also supports `--dir`):

```
uv run scripts/upload_videos.py
uv run scripts/upload_videos.py --dir huey
```

Both scripts compare by filename (and size, to warn on same-name-different-content) rather than re-copying everything every time, so they're safe to re-run.

## Warping a whole video

`warp_video.py` downloads one video from a URL, lets you click its 4 floor corners (see [warp/README.md](../warp/README.md)), warps every frame with those corners, and writes the result to `videos/<name>_warped.mp4`.

Set `VIDEO_URL` at the top of the script to the video you want, then run:

```
uv run scripts/warp_video.py
```

Unlike `brettzone_frames.py`, this doesn't cache corners across runs — it's for warping one video at a time, not a whole tournament's worth of cameras.
