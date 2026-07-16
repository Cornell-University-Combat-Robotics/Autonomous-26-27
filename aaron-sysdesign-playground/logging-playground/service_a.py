from loguru import logger


def run():
    logger.info("service_a: starting work")
    logger.debug("service_a: preparing inputs")
    logger.trace("service_a: raw input = [1, 2, 3]")
    logger.info("service_a: work complete")
