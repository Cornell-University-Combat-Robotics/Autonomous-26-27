"""Orchestrator: builds the services and runs the pipeline loop.

The orchestrator is the only place services are wired together. Services
never call each other directly — main hands each stage's output to the next.
That keeps every service testable alone: construct its input dataclass,
call its one hot-path method, check the output.
"""

from loguru import logger

from algorithm import Algorithm
from camera import Camera
from logging_config import configure_logging, parse_args
from object_detection import ObjectDetector

NUM_FRAMES = 3  # mock "match length"; real loop runs until stopped


def main():
    configure_logging(parse_args())

    # Construction phase: build every service once, up front. In the real
    # system this is also where a Settings object picks implementations
    # (live camera vs video file, real motors vs mock, etc.).
    camera = Camera(width=10, height=10)
    detector = ObjectDetector()
    algorithm = Algorithm()
    logger.debug("main: services constructed")

    # Hot loop: Camera -> ObjectDetector -> Algorithm.
    # Each arrow is one typed dataclass (Frame, then DetectionResult).
    for _ in range(NUM_FRAMES):
        logger.trace("main: starting loop iteration")
        frame = camera.read()
        detections = detector.detect(frame)
        algorithm.decide(detections)

    # After the loop, service state is available for logging / debugging.
    logger.info("----")
    logger.info("frames captured:   {}", camera.frames_captured)
    logger.info("recent bot counts: {}", detector.recent_bot_counts())
    logger.info("decisions made:    {}", algorithm.decisions_made)


if __name__ == "__main__":
    main()
