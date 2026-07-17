# algorithm

Mock decision-maker service: consumes a `DetectionResult` and decides what to do (real version is Ram, producing a `MoveCommand` for Transmission).

Hot-path method: `decide()`. Queryable state: `decisions_made`.

Wired together with the other services by the root `main.py`.
