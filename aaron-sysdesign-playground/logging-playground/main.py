from loguru import logger

import service_a
import service_b
from logging_config import configure_logging, parse_args


def main():
    args = parse_args()
    configure_logging(args)

    logger.info("main: starting")
    service_a.run()
    service_b.run()
    logger.info("main: finished")


if __name__ == "__main__":
    main()
