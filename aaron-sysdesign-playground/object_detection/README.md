# object_detection

Mock detector service: takes a `Frame` in and produces a `DetectionResult` out (real version wraps the Ultralytics predictor).

Hot-path method: `detect()`. Queryable state: `last_result`, `recent_bot_counts()`.

Wired together with the other services by the root `main.py`.
