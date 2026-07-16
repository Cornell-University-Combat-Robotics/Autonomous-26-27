from loguru import logger


def run():
    logger.debug("service_b: starting work")
    logger.trace("service_b: preparing inputs")
    logger.trace("service_b: raw input = [4, 5, 6]")
    logger.debug("service_b: work complete")
