from loguru import logger


def run():
    logger.debug("service_a: starting work")
    logger.trace("service_a: preparing inputs")
    logger.trace("service_a: raw input = [1, 2, 3]")
    logger.debug("service_a: work complete")
