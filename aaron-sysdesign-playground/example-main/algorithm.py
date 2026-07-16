"""Algorithm service: consumes DetectionResult and decides what to do."""

from loguru import logger

from datatypes import DetectionResult


class Algorithm:
    """Mock decision-maker. Real version is Ram: DetectionResult (or the
    corner-detection output) in, MoveCommand out to Transmission.

    Hot-path method: decide()
    Queryable state:  decisions_made
    """

    def __init__(self):
        self._decisions_made = 0
        logger.info("algorithm: initialized")

    def decide(self, result: DetectionResult) -> None:
        """Act on one frame's detections.

        Mock behavior: just report the bot count. Real version would return a
        MoveCommand dataclass for the orchestrator to hand to Transmission.
        """
        logger.trace(f"algorithm: raw result={result}")
        self._decisions_made += 1
        logger.debug(f"algorithm: decisions_made={self._decisions_made}")
        logger.info(f"[frame {result.frame_id}] I see {len(result.bots)} robots")

    # ---- read-only state accessors -------------------------------------

    @property
    def decisions_made(self) -> int:
        """How many frames this algorithm has processed."""
        return self._decisions_made
