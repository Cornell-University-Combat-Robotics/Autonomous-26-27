# videos/

Testing videos, synced with the team's Box folder rather than committed to git (see [scripts/README.md](../scripts/README.md)).

Organized into subdirectories by category — currently `huey/` and `other/`. Add more by just making a new folder here (and in Box); the scripts pick it up automatically.

```
uv run scripts/download_videos.py            # pull every video from Box
uv run scripts/download_videos.py --dir huey # pull only huey/
uv run scripts/upload_videos.py               # push every new local video to Box
uv run scripts/upload_videos.py --dir huey    # push only huey/
```

Video files themselves are gitignored; the folder structure (this README, `huey/.gitkeep`, `other/.gitkeep`) is tracked.
