# logging_config -- the repo's logging package.
#
# STATUS: pseudocode skeleton. Nothing here executes yet; every line is a
# comment describing what the real implementation should do.
#
# ---------------------------------------------------------------------------
# WHAT THIS PACKAGE IS
# ---------------------------------------------------------------------------
# A folder-per-service package (CLAUDE.md, "Architecture") that owns:
#   - a custom TRACE level below DEBUG
#   - a logging.Logger subclass so `logger.trace(...)` is a real method
#   - call-site + in-scope-variable capture on TRACE records
#   - per-level / per-record log destinations resolved by a method call
#
# ---------------------------------------------------------------------------
# PUBLIC SURFACE (what the rest of the repo imports)
# ---------------------------------------------------------------------------
# from .config import configure_logging, parse_args, get_logger
# from .levels import TRACE
# from .logger import TraceLogger
#
# Nothing else in the repo calls logging.getLogger directly. Use
# get_logger(__name__): it is the only thing that guarantees the setup
# below has already run, and it is annotated as returning TraceLogger so
# type checkers can see .trace().
#
# ---------------------------------------------------------------------------
# IMPORT-ORDER CONTRACT (the thing that will silently break)
# ---------------------------------------------------------------------------
# logging.getLogger() caches loggers by name. Any logger created BEFORE
# logging.setLoggerClass(TraceLogger) runs stays a plain Logger forever
# and raises AttributeError on .trace().
#
#   1. Importing this package must, as an import-time side effect:
#        a. levels.register()             <- addLevelName, so "TRACE" renders
#        b. logging.setLoggerClass(...)   <- before ANY getLogger call
#      Do this HERE at import time, not inside configure_logging(): a
#      module can call get_logger(__name__) at import time, long before
#      main() ever runs configure_logging().
#
#   2. Both steps must be idempotent. This module gets imported many
#      times; re-registering must not raise or double-install.
#
#   3. The ROOT logger is built when the stdlib `logging` module is first
#      imported, which is always before us. It will NEVER be a
#      TraceLogger. Never call .trace() on logging.getLogger() with no
#      name, and never let get_logger() hand back the root logger.
