# datatypes

Shared message dataclasses passed between pipeline stages: `Frame` (Camera), `Detection`/`DetectionResult` (ObjectDetector). Each type is produced by exactly one service and only read (never mutated) downstream.

Wired together with the other services by the root `main.py`.
