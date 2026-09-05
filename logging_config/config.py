"""Logging setup, CLI flags, and the get_logger factory."""

# config.py -- wiring, CLI, and the get_logger factory.
#
# PSEUDOCODE SKELETON.
#
# ---------------------------------------------------------------------------
# get_logger(name) -> TraceLogger
# ---------------------------------------------------------------------------
# The ONLY sanctioned way to get a logger in this repo.
#   - returns logging.getLogger(name), annotated as TraceLogger so type
#     checkers can see .trace(). This is the main practical payoff of the
#     subclass over monkeypatching Logger.
#   - assert name is truthy. getLogger("") and getLogger(None) return the
#     ROOT logger, which is never a TraceLogger.
#   - callers pass __name__. Under the folder-per-service layout that
#     yields "camera.camera" with parent "camera", so per-service routing
#     and per-service levels fall out of the logger hierarchy for free.
#   - it should also assert isinstance(result, TraceLogger) and raise a
#     loud, explanatory error if not. That is the import-order bug from
#     __init__.py, and it must fail at import -- not at the first trace()
#     call three hours into a match.
#
# ---------------------------------------------------------------------------
# parse_args()
# ---------------------------------------------------------------------------
# Mirror the playground's CLI so both projects behave identically:
#     --no-logs  --debug  --trace  --console LEVEL  --logfile LEVEL
#     --clear-logs  --simple-logs
# First four are mutually exclusive; last two combine freely with any.
# See aaron-sysdesign-playground/logging_config/logging_config.py for the
# argparse.error() wording -- copy the BEHAVIOUR, not the loguru calls.
#
# ---------------------------------------------------------------------------
# configure_logging(args)
# ---------------------------------------------------------------------------
# Called exactly once, from the entry point, before anything logs.
#   1. resolve levels: CLI flag > per-service log_config.toml > default
#   2. discover services: scan the project root for folders containing a
#      log_config.toml, same convention as the playground, so adding a
#      service still requires no edit here
#   3. build handlers (handlers.py) and formatters (formatters.py)
#   4. attach them to the ROOT logger, not to each service logger.
#      Records propagate upward; one set of handlers at the root is the
#      entire point of the hierarchy. Set propagate=False only to
#      deliberately silence a noisy third-party logger.
#   5. set the root logger's level to the MINIMUM of everything wanted.
#      The logger level gates BEFORE handlers ever see a record, so a root
#      level of INFO silently kills every TRACE no matter how the handlers
#      are configured. Per-sink filtering then happens on the handlers.
#   6. start the QueueListener if used; register its shutdown.
#
# IDEMPOTENCY: calling it twice must not double every log line. Clear
# existing handlers first, or guard with a flag. Tests will call it
# repeatedly.
#
# ---------------------------------------------------------------------------
# PROGRAMMATIC vs dictConfig
# ---------------------------------------------------------------------------
# The removed root logging.py used logging.config.fileConfig -- the
# oldest and most limited of the three config APIs: no filters, no custom
# handler kwargs, and it disables existing loggers by default. If a
# declarative file is wanted, use dictConfig over a TOML source, never
# fileConfig.
# But dictConfig builds custom handlers from an import path plus string
# kwargs, which is awkward for a RoutingHandler whose policy is a METHOD.
# Programmatic construction here is probably simpler. Make the call
# deliberately and record it in the README.
#
# ---------------------------------------------------------------------------
# THIRD-PARTY LOGGERS
# ---------------------------------------------------------------------------
# cv2, roboflow, requests/urllib3 all log. Once handlers sit on the root
# logger, their output lands in our files too. Decide per library:
# silence it, or route it to a separate third_party.log. urllib3 at DEBUG
# is very loud and will bury the pipeline's own lines.
