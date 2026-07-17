import argparse
import shutil
import sys
import tomllib
from pathlib import Path

from loguru import logger

# logging_config/ sits at the repo root, so the root is one level up.
REPO_ROOT = Path(__file__).resolve().parent.parent

# Log files always land at the repo root, regardless of which entry point
# is running or what the current working directory is.
LOG_DIR = REPO_ROOT / "logs"

CONSOLE_FORMAT = (
    "<green>{time:MM.DD.YY HH:mm:ss.SSS}</green> | <level>{level: <5}</level> | "
    "<cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)

LOGFILE_FORMAT = (
    "<green>{time:MM.DD.YY HH:mm:ss.SSS}</green> | <level>{level: <5}</level> | "
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

# Verbosity order, most verbose first. Used to pick a sink's floor level
# when several services (or the "" default) want different levels.
LEVEL_ORDER = ["TRACE", "DEBUG", "INFO"]

LEVEL_CHOICES = ["NONE", "INFO", "DEBUG", "TRACE"]


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--no-logs",
        action="store_true",
        help="Disable logging entirely: no console output, no log files.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Log at DEBUG in both the console and log files.",
    )
    parser.add_argument(
        "--trace",
        action="store_true",
        help="Log at TRACE in both the console and log files.",
    )
    parser.add_argument(
        "--console",
        choices=LEVEL_CHOICES,
        default=None,
        help="Set the console level explicitly. NONE disables console output.",
    )
    parser.add_argument(
        "--logfile",
        choices=LEVEL_CHOICES,
        default=None,
        help="Set the log file level explicitly. NONE disables all log files.",
    )
    parser.add_argument(
        "--clear-logs",
        action="store_true",
        help="Empty the logs directory before this run instead of appending to it. "
        "Can be combined with any other flag.",
    )
    parser.add_argument(
        "--simple-logs",
        action="store_true",
        help="Format every sink as just the raw message, skipping time/level/name/line formatting.",
    )
    args = parser.parse_args()

    # --no-logs / --debug / --trace / (--console and/or --logfile) are four
    # mutually exclusive ways of choosing what gets logged. --clear-logs and
    # --simple-logs are orthogonal and combine freely with any of them.
    modes_used = []
    if args.no_logs:
        modes_used.append("--no-logs")
    if args.debug:
        modes_used.append("--debug")
    if args.trace:
        modes_used.append("--trace")
    if args.console is not None or args.logfile is not None:
        modes_used.append("--console/--logfile")

    if len(modes_used) > 1:
        parser.error(
            f"{' and '.join(modes_used)} cannot be combined. Pick exactly one "
            "of: --no-logs, --debug, --trace, or --console/--logfile "
            "(--console and --logfile may be combined with each other)."
        )

    return args


def _read_service_config(service_dir: Path) -> dict | None:
    """Reads <service>/log_config.toml, or None if the service has no such file."""
    config_path = service_dir / "log_config.toml"
    if not config_path.exists():
        return None
    with config_path.open("rb") as f:
        data = tomllib.load(f)
    return {
        "console": data.get("console", "INFO"),
        "logfile": data.get("logfile", "INFO"),
    }


def _discover_services() -> dict[str, dict]:
    """Service folders that opt into logging via a log_config.toml file.

    Folders without one (e.g. datatypes/, which never logs) are skipped
    entirely, so they never get a pointless empty <service>.log.
    """
    services = {}
    for d in sorted(REPO_ROOT.iterdir()):
        if not d.is_dir():
            continue
        config = _read_service_config(d)
        if config is not None:
            services[d.name] = config
    return services


def _resolve_sink(cli_level: str | None, service_configs: dict, sink_key: str):
    """Determines a sink's (level, filter), or (None, None) to skip it entirely.

    cli_level: this sink's explicit CLI level ("NONE"/"TRACE"/"DEBUG"/"INFO"),
        or None if the CLI didn't touch it. A CLI level overrides every
        service's own configured level, applying uniformly to all of them.
    service_configs: {service_name: {"console": ..., "logfile": ...}}, as
        returned by _discover_services().
    sink_key: "console" or "logfile" — which half of each service's config
        file to read.
    """
    if cli_level == "NONE":
        return None, None
    if cli_level is not None:
        return cli_level, {"": cli_level}

    # No CLI override: each service uses its own configured level, "" covers
    # anything with no log_config.toml at all.
    filter_map = {"": "INFO"}
    for service, config in service_configs.items():
        filter_map[service] = config[sink_key]
    sink_level = min(filter_map.values(), key=LEVEL_ORDER.index)
    return sink_level, filter_map


def configure_logging(args):
    logger.remove()

    if args.clear_logs and LOG_DIR.exists():
        shutil.rmtree(LOG_DIR)

    if args.no_logs:
        return

    if args.debug:
        console_cli = logfile_cli = "DEBUG"
    elif args.trace:
        console_cli = logfile_cli = "TRACE"
    else:
        console_cli = args.console
        logfile_cli = args.logfile

    service_configs = _discover_services()

    console_level, console_filter = _resolve_sink(console_cli, service_configs, "console")
    logfile_level, logfile_filter = _resolve_sink(logfile_cli, service_configs, "logfile")

    console_format = SIMPLE_FORMAT if args.simple_logs else CONSOLE_FORMAT
    logfile_format = SIMPLE_FORMAT if args.simple_logs else LOGFILE_FORMAT

    if console_level is not None:
        logger.add(sys.stderr, level=console_level, filter=console_filter,
                   format=console_format, enqueue=ENQUEUE)

    if logfile_level is None:
        return

    # main.log: everything, filtered with the same level/filter as the log
    # files use overall, so it always matches what the per-service files add
    # up to.
    logger.add(
        LOG_DIR / "main.log",
        level=logfile_level,
        filter=logfile_filter,
        rotation="10 MB",
        retention="7 days",
        compression="zip",
        format=logfile_format,
        enqueue=ENQUEUE,
    )

    # <service>.log: one file per service that opted in via log_config.toml.
    for service in service_configs:
        service_level = logfile_filter.get(service, logfile_filter[""])
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
