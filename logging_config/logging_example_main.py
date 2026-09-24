import logging
import logging_config
from logging_example_service import log_service

# Importing logging_config is what installs the custom Logger class
logger = logging.getLogger("example_main")

logger.info("This is an info message from the main module.")

log_service()


def example_fn(x: int):
    return x + 1


error_example = True

def main():
    try:
        # Initialize camera
        logger.info("Initializing camera...")
        cam = 1

        # Run object detection
        logger.debug(f"Object detection found {cam} objects.")

        try:
            logger.debug("Entered Corner Block")
            if error_example:
                cam = 1 / 0

            # Example Loop
            logger.trace("Pre Loop")
            corners = 0
            for i in range(10):
                corners = example_fn(corners)
                logger.trace("in loop line 31, iteration")

            logger.trace("Exited corner loop")

        except Exception as e:
            logger.warning(f"Corner Errored Out with {e}")

        if error_example:
            # This should throw an error and be caught by the main try/except block
            cam = 1 / "hello"

    except Exception as e:
        logger.error(f"Main Errored out with {e}")


if __name__ == "__main__":
    main()
