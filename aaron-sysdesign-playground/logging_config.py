import argparse
import sys
from pathlib import Path

from loguru import logger

CONSOLE_FORMAT = (
    "<green>{time:MM/DD/YY HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--debug",
        nargs="*",
        metavar="MODULE",
        help="Log at DEBUG. With no MODULE given, applies to everything. "
        "With MODULE names (e.g. --debug service_a), applies only to those modules.",
    )
    parser.add_argument(
        "--trace",
        nargs="*",
        metavar="MODULE",
        help="Log at TRACE. With no MODULE given, applies to everything. "
        "With MODULE names (e.g. --trace service_a), applies only to those modules.",
    )
    return parser.parse_args()


def configure_logging(args, log_dir: Path):
    filter_map = {"": "INFO"}
    sink_level = "INFO"

    if args.debug is not None:
        sink_level = "DEBUG"
        if args.debug:
            for module in args.debug:
                filter_map[module] = "DEBUG"
        else:
            filter_map[""] = "DEBUG"

    if args.trace is not None:
        sink_level = "TRACE"
        if args.trace:
            for module in args.trace:
                filter_map[module] = "TRACE"
        else:
            filter_map[""] = "TRACE"

    logger.remove()
    logger.add(sys.stderr, level=sink_level,
               filter=filter_map, format=CONSOLE_FORMAT)
    logger.add(
        log_dir / "app.log",
        level="TRACE",
        rotation="10 MB",
        retention="7 days",
        compression="zip",
    )
