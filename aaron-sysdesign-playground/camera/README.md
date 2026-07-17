# camera

Mock camera service: owns frame capture and produces `Frame` messages (real version wraps `cv2.VideoCapture` / `CameraStream`).

Hot-path method: `read()`. Queryable state: `frames_captured`, `last_frame`.

Wired together with the other services by the root `main.py`.
