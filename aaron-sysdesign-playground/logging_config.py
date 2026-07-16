import argparse
import shutil
import sys
from pathlib import Path

from loguru import logger

CONSOLE_FORMAT = (
    "<green>{time:MM/DD/YY HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)

LOGFILE_FORMAT = (
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
    parser.add_argument(
        "--clean-logs",
        action="store_true",
        help="Empty the logs directory before this run instead of appending to it.",
    )
    return parser.parse_args()


def configure_logging(args, log_dir: Path):
    if args.clean_logs and log_dir.exists():
        shutil.rmtree(log_dir)

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

    # main.log: everything from every file in the entry script's directory.
    logger.add(
        log_dir / "main.log",
        level="TRACE",
        rotation="10 MB",
        retention="7 days",
        compression="zip",
        format=LOGFILE_FORMAT
    )

    # <module>.log: one file per sibling .py module, containing only that
    # module's logs. New files are picked up automatically since this scans
    # the directory rather than hardcoding module names. The entry script
    # itself is skipped since its logs are recorded under "__main__" (not
    # its filename) and main.log already captures everything anyway.
    entry_module = Path(sys.argv[0]).stem
    for py_file in sorted(log_dir.parent.glob("*.py")):
        module_name = py_file.stem
        if module_name == entry_module:
            continue
        logger.add(
            log_dir / f"{module_name}.log",
            level="TRACE",
            filter=lambda record, module_name=module_name: record["name"] == module_name,
            rotation="10 MB",
            retention="7 days",
            compression="zip",
            format=LOGFILE_FORMAT
        )
