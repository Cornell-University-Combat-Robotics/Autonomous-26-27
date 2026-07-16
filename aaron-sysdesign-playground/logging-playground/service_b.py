from loguru import logger


def run():
    logger.info("service_b: starting work")
    logger.debug("service_b: preparing inputs")
    logger.trace("service_b: raw input = [4, 5, 6]")
    logger.info("service_b: work complete")
