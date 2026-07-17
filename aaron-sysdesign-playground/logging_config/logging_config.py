import argparse
import shutil
import sys
from pathlib import Path

from loguru import logger

# logging_config/ sits at the repo root, so the root is one level up.
REPO_ROOT = Path(__file__).resolve().parent.parent

# Log files always land at the repo root, regardless of which entry point
# is running or what the current working directory is.
LOG_DIR = REPO_ROOT / "logs"

CONSOLE_FORMAT = (
    "<green>{time:MM/DD/YY HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)

LOGFILE_FORMAT = (
    "<green>{time:MM/DD/YY HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)

# No time/level/name/line — cuts loguru's per-call datetime formatting and
# markup/color parsing down to just rendering {message} itself.
SIMPLE_FORMAT = "{message}"

# When True, every sink formats/writes on a background thread instead of the
# calling thread, so logger.*() calls just enqueue and return. Keeps logging
# off the hot path at the cost of possibly losing queued-but-unwritten
# records if the process is killed abruptly.
ENQUEUE = False


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--debug",
        nargs="*",
        metavar="SERVICE",
        help="Log at DEBUG. With no SERVICE given, applies to everything. "
        "With SERVICE names (e.g. --debug algorithm), applies only to those services.",
    )
    parser.add_argument(
        "--trace",
        nargs="*",
        metavar="SERVICE",
        help="Log at TRACE. With no SERVICE given, applies to everything. "
        "With SERVICE names (e.g. --trace algorithm camera), applies only to those services.",
    )
    parser.add_argument(
        "--clean-logs",
        action="store_true",
        help="Empty the logs directory before this run instead of appending to it.",
    )
    parser.add_argument(
        "--no-logs",
        action="store_true",
        help="Disable logging entirely: no console output, no log files.",
    )
    parser.add_argument(
        "--console-only",
        action="store_true",
        help="Log to the terminal only; skip writing any log files.",
    )
    parser.add_argument(
        "--simple-logs",
        action="store_true",
        help="Format every sink as just the raw message, skipping time/level/name/line formatting.",
    )
    return parser.parse_args()


def _service_packages():
    """Service folders at the repo root: any directory holding an __init__.py."""
    return sorted(
        d.name
        for d in REPO_ROOT.iterdir()
        if d.is_dir() and (d / "__init__.py").exists()
    )


def configure_logging(args):
    logger.remove()

    if args.no_logs:
        return

    if args.clean_logs and LOG_DIR.exists():
        shutil.rmtree(LOG_DIR)

    # Maps service name -> minimum level. Loguru resolves a record's module
    # (e.g. "algorithm.algorithm") to its closest parent in this dict, so a
    # bare service name governs every module inside that service's folder;
    # "" is the fallback for everything else.
    filter_map = {"": "INFO"}
    sink_level = "INFO"

    if args.debug is not None:
        sink_level = "DEBUG"
        if args.debug:
            for service in args.debug:
                filter_map[service] = "DEBUG"
        else:
            filter_map[""] = "DEBUG"

    if args.trace is not None:
        sink_level = "TRACE"
        if args.trace:
            for service in args.trace:
                filter_map[service] = "TRACE"
        else:
            filter_map[""] = "TRACE"

    console_format = SIMPLE_FORMAT if args.simple_logs else CONSOLE_FORMAT
    logfile_format = SIMPLE_FORMAT if args.simple_logs else LOGFILE_FORMAT

    logger.add(sys.stderr, level=sink_level,
               filter=filter_map, format=console_format, enqueue=ENQUEUE)

    if args.console_only:
        return

    # main.log: everything, filtered exactly like the console sink (same
    # level, same per-service overrides), so log files never contain more
    # than what's on screen.
    logger.add(
        LOG_DIR / "main.log",
        level=sink_level,
        filter=filter_map,
        rotation="10 MB",
        retention="7 days",
        compression="zip",
        format=logfile_format,
        enqueue=ENQUEUE,
    )

    # <service>.log: one file per service folder, containing only that
    # service's logs at whatever level the console shows for it. Services
    # are discovered by scanning the repo root, so a new service folder
    # gets its own log file automatically — no changes needed here.
    for service in _service_packages():
        service_level = filter_map.get(service, filter_map[""])
        logger.add(
            LOG_DIR / f"{service}.log",
            level=service_level,
            filter=lambda record, service=service: (
                record["name"] == service
                or record["name"].startswith(service + ".")
            ),
            rotation="10 MB",
            retention="7 days",
            compression="zip",
            format=logfile_format,
            enqueue=ENQUEUE,
        )
