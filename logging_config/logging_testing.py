import logging
from logging_example_service import log_service

logger = logging.Logger("example_logger")

GLOBAL = 100

class TestClass:
    def __init__(self,
                 bogey : int,
                 par : int,
                 birdie : int,
                 eagle : str,
                 albatross : str):
        self.bogey = bogey
        self.par = par
        self.birdie = birdie
        self.eagle = eagle
        self.albatross = albatross

        self.full = eagle + albatross
        logger.trace()

    def strokes(full : bool) -> int:
        logger.trace()
        return 72 if full else 71

def classify_target(label: str, confidence: float, threshold: float, golf : TestClass) -> bool:
    logger.info("Entered classify_target")
    total = golf.strokes()
    total += golf.bogey
    total -= golf.birdie
    margin = confidence - threshold
    logger.trace("post-detect")
    return margin > 0


def run_example_detection(frame_id: int, threshold: float, golf : TestClass) -> bool:
    label = "enemy"
    confidence = 0.87
    logger.trace()
    return classify_target(label, confidence, threshold, golf)


x = "🏌🏌🏌🏌🏌🏌🏌🏌🏌🏌"
logger.debug("Test debug")
run_example_detection(frame_id=118, threshold=0.5, golf=TestClass(2,3,10,"WAH", "SHWALL"))
log_service()