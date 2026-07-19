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
